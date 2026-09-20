"""All modals used by the cog."""

import random

import discord

from .constants import (
    CHALLENGE_TIMEOUT_SECONDS,
    DEFAULT_SECURITY_QUESTIONS,
)


class ChallengeModal(discord.ui.Modal, title="Verification Challenge"):
    """Math or text challenge modal."""

    answer_input = discord.ui.TextInput(
        label="Your answer",
        placeholder="Enter your answer here...",
        required=True,
        max_length=50,
    )

    def __init__(self, cog, prompt, correct_answer, member, guild, is_math, view_ref=None):
        super().__init__(timeout=CHALLENGE_TIMEOUT_SECONDS)
        self.cog = cog
        self.correct_answer = correct_answer
        self.member = member
        self.guild = guild
        self.is_math = is_math
        self.view_ref = view_ref
        self.answer_input.label = prompt[:45]

    async def on_submit(self, interaction: discord.Interaction):
        if self.view_ref is not None:
            self.view_ref._completed = True
            self.view_ref.stop()
            try:
                if self.view_ref.message:
                    await self.view_ref.message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        await self.cog.check_answer(
            interaction, self.answer_input.value,
            self.correct_answer, self.guild, self.is_math,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        try:
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.", ephemeral=True
            )
        except Exception:
            pass


class SecurityCheckModal(discord.ui.Modal, title="Security Check"):
    """Two-question security check used when a verified user lost their role."""

    def __init__(self, cog, member, guild, questions, mode: str, view_ref=None):
        super().__init__(timeout=CHALLENGE_TIMEOUT_SECONDS)
        self.cog = cog
        self.member = member
        self.guild = guild
        self.questions = questions
        self.mode = mode
        self.view_ref = view_ref
        self.inputs: list[discord.ui.TextInput] = []

        for q, _a in questions:
            ti = discord.ui.TextInput(
                label=q[:45], placeholder="Your answer...",
                required=True, max_length=50,
            )
            self.add_item(ti)
            self.inputs.append(ti)

    async def on_submit(self, interaction: discord.Interaction):
        if self.view_ref is not None:
            self.view_ref._completed = True
            self.view_ref.stop()
            try:
                if self.view_ref.message:
                    await self.view_ref.message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        all_ok = True
        for ti, (_, expected) in zip(self.inputs, self.questions):
            if ti.value.strip().lower() != str(expected).strip().lower():
                all_ok = False
                break

        if not all_ok:
            await self.cog._remove_verification_reaction(self.guild, self.member)
            await interaction.response.send_message(
                "❌ **Security check failed.** One or more answers were wrong.\n"
                "Your reaction has been removed. React again to retry.",
                ephemeral=True,
            )
            return

        conf = self.cog.config.guild(self.guild)
        async with conf.verified_users() as vu:
            if self.member.id in vu:
                vu.remove(self.member.id)
        await self.cog._write_verified_users_file(self.guild)

        if self.mode == "button":
            # Import here to avoid circular dependency at module load
            from .verify_views import ContinueChallengeView
            view = ContinueChallengeView(self.cog, self.member, self.guild)
            await interaction.response.send_message(
                "✅ **Security check passed!**\n\n"
                "You can now continue with verification. "
                "Click the button below to open the challenge.",
                view=view,
                ephemeral=True,
            )
        else:
            await self.cog._post_challenge_in_channel(self.guild, self.member)
            await interaction.response.send_message(
                "✅ **Security check passed!**\n\n"
                "The verification challenge has been posted in the channel.",
                ephemeral=True,
            )


class MessageIDModal(discord.ui.Modal, title="Existing Message ID"):
    """Modal for entering a message ID during the setup wizard."""

    message_input = discord.ui.TextInput(
        label="Message ID or link",
        placeholder="Paste the message ID or a Discord message link...",
        required=True, max_length=200,
    )

    def __init__(self, wizard):
        super().__init__(timeout=300)
        self.wizard = wizard

    async def on_submit(self, interaction):
        raw = self.message_input.value.strip()
        message_id_str = raw.split("/")[-1]
        if not message_id_str.isdigit():
            await interaction.response.send_message(
                "❌ Invalid message ID or link. Please try again.", ephemeral=True
            )
            return
        message_id = int(message_id_str)
        try:
            await self.wizard.channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.response.send_message(
                f"❌ No message with ID `{message_id}` found in {self.wizard.channel.mention}.",
                ephemeral=True,
            )
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to read messages in that channel.", ephemeral=True
            )
            return
        self.wizard.message_id = message_id
        await self.wizard.show_step4_reaction(interaction)


class ChangeMessageModal(discord.ui.Modal, title="Change Verification Message"):
    """Modal for changing the target message from the menu."""

    message_input = discord.ui.TextInput(
        label="Message ID or link",
        placeholder="Paste the message ID or a Discord message link...",
        required=True, max_length=200,
    )

    def __init__(self, cog, guild, parent, channel):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.parent = parent
        self.channel = channel

    async def on_submit(self, interaction):
        raw = self.message_input.value.strip()
        message_id_str = raw.split("/")[-1]
        if not message_id_str.isdigit():
            await interaction.response.send_message("❌ Invalid message ID or link.", ephemeral=True)
            return
        new_id = int(message_id_str)
        try:
            new_message = await self.channel.fetch_message(new_id)
        except discord.NotFound:
            await interaction.response.send_message(
                f"❌ No message with ID `{new_id}` found in {self.channel.mention}.", ephemeral=True
            )
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to read messages in that channel.", ephemeral=True
            )
            return

        conf = self.cog.config.guild(self.guild)
        old_id = await conf.verification_message_id()
        emoji = await conf.verification_emoji() or "✅"

        try:
            await new_message.add_reaction(emoji)
        except Exception:
            await interaction.response.send_message(
                "❌ Could not add the reaction to the new message. "
                "Please check my **Add Reactions** permission. "
                "The message was **not changed**.",
                ephemeral=True,
            )
            return

        await conf.verification_message_id.set(new_id)

        if old_id and old_id != new_id:
            try:
                old = await self.channel.fetch_message(old_id)
                try:
                    await old.clear_reaction(emoji)
                except Exception:
                    pass
            except Exception:
                pass

        embed = await self.parent.build_embed()
        embed.description = (embed.description or "") + f"\n\n✅ Added {emoji} to the new message"
        await interaction.response.edit_message(embed=embed, view=self.parent)