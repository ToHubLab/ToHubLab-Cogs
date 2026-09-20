import asyncio
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord.ext import tasks
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path


DEFAULT_VERIFICATION_EMOJI = "✅"
VERIFICATION_EMBED_TITLE = "🔐 Server Verification"
SETUP_AUTO_DELETE_SECONDS = 8
CANCEL_AUTO_DELETE_SECONDS = 3
MENU_TIMEOUT_SECONDS = 180
SYNC_INTERVAL_MINUTES = 5
CHALLENGE_TIMEOUT_SECONDS = 300
VERIFIED_PAGE_SIZE = 5

CREDIT_NAME = "ToHubLab"
CREDIT_URL = "https://github.com/ToHubLab"
CREDIT_LINE = f"\n\n-# Made by [{CREDIT_NAME}]({CREDIT_URL})"

DATA_FILE_NAME = "verification_data.json"
VERIFIED_FILE_NAME = "verified_users.json"


_DEFAULT_EMOJI_OPTIONS = [
    ["✅", "Check Mark Button"], ["✔️", "Check Mark"], ["☑️", "Check Box with Check"],
    ["👍", "Thumbs Up"], ["👋", "Waving Hand"], ["🙌", "Raising Hands"],
    ["🤝", "Handshake"], ["🟢", "Green Circle"], ["🔵", "Blue Circle"],
    ["🟡", "Yellow Circle"], ["🟣", "Purple Circle"], ["🟠", "Orange Circle"],
    ["🔴", "Red Circle"], ["⚪", "White Circle"], ["⚫", "Black Circle"],
    ["🔒", "Locked"], ["🔓", "Unlocked"], ["🎉", "Party Popper"],
    ["⭐", "Star"], ["🌟", "Glowing Star"], ["💫", "Dizzy"],
    ["🚀", "Rocket"], ["🎯", "Direct Hit"], ["🛡️", "Shield"],
]

_DEFAULT_TEXT_CHALLENGES = [
    ["Write 'Color' to verify", "color"], ["Type 'Verify' to verify", "verify"],
    ["Write 'Human' to verify", "human"], ["Type 'ToHubLab' to verify", "tohublab"],
    ["Write 'Blue' to verify", "blue"], ["Type 'Hello' to verify", "hello"],
    ["Write 'Purple' to verify", "purple"], ["Type 'Apple' to verify", "apple"],
    ["Write 'Yes' to verify", "yes"], ["Type 'Ready' to verify", "ready"],
    ["Write 'Discord' to verify", "discord"], ["Type 'Welcome' to verify", "welcome"],
]

_DEFAULT_SECURITY_QUESTIONS = [
    ["How many letters are in the word 'verify'?", "6"],
    ["What color is the sky on a clear day?", "blue"],
    ["What is 2 + 2?", "4"],
    ["Type the word 'confirm'", "confirm"],
    ["What color is grass?", "green"],
    ["Type the number seven", "7"],
    ["How many days are in a week?", "7"],
    ["What color is snow?", "white"],
]


def _normalize_emoji(e) -> str:
    if e is None:
        return ""
    s = str(e).strip()
    if s.startswith("<") and s.endswith(">"):
        return s
    return s.replace("\ufe0f", "")


# ──────────────────────────────────────────────
#  Embed builders
# ──────────────────────────────────────────────

def _verification_embed() -> discord.Embed:
    return discord.Embed(
        title=VERIFICATION_EMBED_TITLE,
        description=(
            "To gain access to the server, you need to verify yourself.\n\n"
            "**How it works:**\n"
            "1️⃣ Click the **Verify** button below\n"
            "2️⃣ A short challenge will open – solve it\n"
            "3️⃣ Solve it correctly to receive the verification role\n\n"
            "⚠️ After 3 wrong answers you will be locked out for 10 minutes."
            + CREDIT_LINE
        ),
        color=discord.Color.blue(),
    )


def _step1_embed() -> discord.Embed:
    return discord.Embed(
        title="🔧 Verification Setup – Step 1/4",
        description=(
            "Welcome to the setup wizard!\n\n"
            "**Please select the channel** where verification should take place."
            + CREDIT_LINE
        ),
        color=discord.Color.blue(),
    )


def _step2_embed(channel) -> discord.Embed:
    return discord.Embed(
        title="🔧 Verification Setup – Step 2/4",
        description=(
            f"**Channel selected:** {channel.mention}\n\n"
            "**Now select the role** that will be granted to verified users."
            + CREDIT_LINE
        ),
        color=discord.Color.blue(),
    )


def _step3_embed(channel, role) -> discord.Embed:
    return discord.Embed(
        title="🔧 Verification Setup – Step 3/4",
        description=(
            f"**Channel:** {channel.mention}\n"
            f"**Role:** {role.mention}\n\n"
            "**How should users trigger verification?**"
            + CREDIT_LINE
        ),
        color=discord.Color.blue(),
    )


def _step4_embed(channel, role, mode: str, message_id, emoji: str) -> discord.Embed:
    if mode == "button":
        mode_line = "⚙️ **Mode:** Send a new verification message with a button"
        message_line = ""
        hint = "Click **Confirm & Create** to finish."
    else:
        mode_line = "⚙️ **Mode:** Use existing message (reaction-based)"
        message_line = f"\n💬 **Message ID:** `{message_id}`"
        hint = "Choose an emoji above, then click **Confirm & Create**."

    return discord.Embed(
        title="🔧 Verification Setup – Step 4/4",
        description=(
            "**Summary:**\n\n"
            f"📢 **Channel:** {channel.mention}\n"
            f"🎭 **Role:** {role.mention}\n"
            f"{mode_line}"
            f"{message_line}\n"
            f"😀 **Emoji:** {emoji}\n\n"
            f"{hint}"
            + CREDIT_LINE
        ),
        color=discord.Color.blue(),
    )


def _success_embed(description, role, channel, mode, emoji) -> discord.Embed:
    return discord.Embed(
        title="✅ Setup Complete!",
        description=(
            f"{description}\n\n"
            f"🎭 **Role:** {role.mention}\n"
            f"📢 **Channel:** {channel.mention}\n"
            f"⚙️ **Mode:** {'Button' if mode == 'button' else 'Reaction'}\n"
            f"😀 **Emoji:** {emoji}\n\n"
            f"⏳ This message will self-destruct in {SETUP_AUTO_DELETE_SECONDS} seconds."
            + CREDIT_LINE
        ),
        color=discord.Color.green(),
    )


def _error_embed(description: str) -> discord.Embed:
    return discord.Embed(
        title="❌ Setup Failed",
        description=description + CREDIT_LINE,
        color=discord.Color.red(),
    )


def _cancel_embed() -> discord.Embed:
    return discord.Embed(
        title="❌ Setup Cancelled",
        description=(
            "The setup process was cancelled. This message will disappear in a moment."
            + CREDIT_LINE
        ),
        color=discord.Color.red(),
    )


def _status_embed(channel_id, message_id, role_id, mode, emoji, *, title="📊 Verification Status") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=(
            f"**Channel:** {f'<#{channel_id}>' if channel_id else '❌ Not set'}\n"
            f"**Message:** {f'`{message_id}`' if message_id else '❌ Not set'}\n"
            f"**Role:** {f'<@&{role_id}>' if role_id else '❌ Not set'}\n"
            f"**Mode:** {f'`{mode}`' if mode else '❌ Not set'}\n"
            f"**Emoji:** {emoji or '❌ Not set'}"
            + CREDIT_LINE
        ),
        color=discord.Color.blue(),
    )


def _not_setup_embed() -> discord.Embed:
    return discord.Embed(
        title="⚙️ Verification Not Set Up",
        description=(
            "The verification system has **not been configured** on this server yet.\n\n"
            "Would you like to start the setup wizard now?\n\n"
            "Click **Start Setup** below to begin."
            + CREDIT_LINE
        ),
        color=discord.Color.orange(),
    )


# ──────────────────────────────────────────────
#  Persistent verify button
# ──────────────────────────────────────────────

class VerifyView(discord.ui.View):
    def __init__(self, cog: "Verification"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Verify", style=discord.ButtonStyle.success,
        custom_id="verification:start", emoji=DEFAULT_VERIFICATION_EMOJI,
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.start_verification(interaction)


# ──────────────────────────────────────────────
#  Challenge modal (with view tracking)
# ──────────────────────────────────────────────

class ChallengeModal(discord.ui.Modal, title="Verification Challenge"):
    answer_input = discord.ui.TextInput(
        label="Your answer", placeholder="Enter your answer here...",
        required=True, max_length=50,
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
        # Mark the challenge view as completed BEFORE checking
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


# ──────────────────────────────────────────────
#  Security check modal (with view tracking)
# ──────────────────────────────────────────────

class SecurityCheckModal(discord.ui.Modal, title="Security Check"):
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
        # Mark the security view as completed
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
            # Failed security check → remove reaction so they can retry from scratch
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
            view = ContinueChallengeView(self.cog, self.member, self.guild)
            await interaction.response.send_message(
                "✅ **Security check passed!**\n\n"
                "You can now continue with verification. "
                "Click the button below to open the challenge.",
                view=view,
                ephemeral=True,
            )
        else:
            # Keep their reaction! Do NOT remove it - the challenge is now posted
            await self.cog._post_challenge_in_channel(self.guild, self.member)
            await interaction.response.send_message(
                "✅ **Security check passed!**\n\n"
                "The verification challenge has been posted in the channel.",
                ephemeral=True,
            )


# ──────────────────────────────────────────────
#  Continue verification (button mode after security check)
# ──────────────────────────────────────────────

class ContinueChallengeView(discord.ui.View):
    def __init__(self, cog, member, guild):
        super().__init__(timeout=180)
        self.cog = cog
        self.member = member
        self.guild = guild

    @discord.ui.button(label="Open Challenge", style=discord.ButtonStyle.success, emoji="✏️")
    async def open_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("❌ Not for you.", ephemeral=True)
            return

        conf = self.cog.config.guild(self.guild)
        failed_attempts = await conf.failed_attempts()
        user_data = failed_attempts.get(str(self.member.id))
        if user_data and user_data.get("locked_until"):
            locked_until = datetime.fromisoformat(user_data["locked_until"])
            if datetime.now(timezone.utc) < locked_until:
                remaining = (locked_until - datetime.now(timezone.utc)).total_seconds()
                progress = max(0, min(20, int((1 - remaining / 600) * 20)))
                bar = "█" * progress + "░" * (20 - progress)
                minutes, seconds = int(remaining // 60), int(remaining % 60)
                await interaction.response.send_message(
                    f"⏳ **You are still locked out.**\n`[{bar}]`\n"
                    f"**{minutes}:{seconds:02d}** minutes remaining.",
                    ephemeral=True,
                )
                return

        prompt, correct_answer, is_math = self.cog._generate_challenge()
        await interaction.response.send_modal(
            ChallengeModal(self.cog, prompt, correct_answer, self.member, self.guild, is_math)
        )
        self.stop()


# ──────────────────────────────────────────────
#  Security check start view (reaction mode)
# ──────────────────────────────────────────────

class SecurityCheckStartView(discord.ui.View):
    """
    Posted in the channel when a previously-verified user lost their role.
    On cancel/timeout without completing the security check, the reaction is
    removed so the counter stays correct.
    """

    def __init__(self, cog, member, guild):
        super().__init__(timeout=CHALLENGE_TIMEOUT_SECONDS)
        self.cog = cog
        self.member = member
        self.guild = guild
        self.message = None
        self._completed = False
        self._cancelled = False

    @discord.ui.button(label="Start Security Check", style=discord.ButtonStyle.primary, emoji="🔐")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ This security check is not for you.", ephemeral=True
            )
            return
        pool = self.cog.security_questions or [(q, a) for q, a in _DEFAULT_SECURITY_QUESTIONS]
        if len(pool) < 2:
            await interaction.response.send_message(
                "❌ Security questions are not configured correctly. "
                "Please contact an admin.", ephemeral=True,
            )
            return
        questions = random.sample(pool, 2)
        # Pass view_ref so the modal can mark us as completed
        await interaction.response.send_modal(
            SecurityCheckModal(
                self.cog, self.member, self.guild, questions,
                mode="reaction", view_ref=self,
            )
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Not for you.", ephemeral=True
            )
            return
        self._cancelled = True
        await self.cog._remove_verification_reaction(self.guild, self.member)
        await interaction.response.edit_message(
            content=(
                f"{self.member.mention} ❌ Security check cancelled. "
                "Your reaction has been removed."
            ),
            embed=None, view=None,
        )
        self.stop()
        try:
            if self.message:
                await asyncio.sleep(5)
                await self.message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    async def on_timeout(self):
        if self._completed or self._cancelled:
            return
        # Timed out without finishing → remove the reaction
        await self.cog._remove_verification_reaction(self.guild, self.member)
        try:
            if self.message:
                await self.message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


# ──────────────────────────────────────────────
#  Channel challenge view (reaction mode)
# ──────────────────────────────────────────────

class ChannelChallengeStartView(discord.ui.View):
    """
    Posted in the channel after a fresh reaction.
    On cancel/timeout without completing the challenge, the reaction is removed.
    """

    def __init__(self, cog, prompt, correct_answer, member, guild, is_math):
        super().__init__(timeout=CHALLENGE_TIMEOUT_SECONDS)
        self.cog = cog
        self.prompt = prompt
        self.correct_answer = correct_answer
        self.member = member
        self.guild = guild
        self.is_math = is_math
        self.message = None
        self._completed = False
        self._cancelled = False

    @discord.ui.button(label="Enter Answer", style=discord.ButtonStyle.primary, emoji="✏️")
    async def enter_answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ This verification prompt is not for you.", ephemeral=True
            )
            return
        modal = ChallengeModal(
            self.cog, self.prompt, self.correct_answer,
            self.member, self.guild, self.is_math,
            view_ref=self,
        )
        await interaction.response.send_modal(modal)
        # Do NOT stop the view here - the modal's on_submit will mark us completed

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ Not for you.", ephemeral=True
            )
            return
        self._cancelled = True
        await self.cog._remove_verification_reaction(self.guild, self.member)
        await interaction.response.edit_message(
            content=(
                f"{self.member.mention} ❌ Verification cancelled. "
                "Your reaction has been removed."
            ),
            embed=None, view=None,
        )
        self.stop()
        try:
            if self.message:
                await asyncio.sleep(5)
                await self.message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    async def on_timeout(self):
        if self._completed or self._cancelled:
            return
        # Timed out without finishing → remove the reaction
        await self.cog._remove_verification_reaction(self.guild, self.member)
        try:
            if self.message:
                await self.message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


# ──────────────────────────────────────────────
#  Setup Wizard
# ──────────────────────────────────────────────

class SetupWizard:
    def __init__(self, cog: "Verification", ctx: commands.Context):
        self.cog = cog
        self.ctx = ctx
        self.message = None
        self.channel = None
        self.role = None
        self.mode = None
        self.message_id = None
        self.emoji = DEFAULT_VERIFICATION_EMOJI
        self._deletion_task = None

    async def start(self):
        self.message = await self.ctx.send(embed=_step1_embed(), view=SetupChannelView(self))

    async def show_step2(self, interaction):
        await interaction.response.edit_message(
            embed=_step2_embed(self.channel), view=SetupRoleView(self)
        )

    async def show_step3(self, interaction):
        await interaction.response.edit_message(
            embed=_step3_embed(self.channel, self.role), view=SetupModeView(self)
        )

    async def show_step4_button(self, interaction):
        self.mode = "button"
        self.message_id = None
        self.emoji = DEFAULT_VERIFICATION_EMOJI
        await interaction.response.edit_message(
            embed=_step4_embed(self.channel, self.role, "button", None, self.emoji),
            view=SetupConfirmView(self),
        )

    async def show_step4_reaction(self, interaction):
        self.mode = "reaction"
        await interaction.response.edit_message(
            embed=_step4_embed(self.channel, self.role, "reaction", self.message_id, self.emoji),
            view=ReactionSetupView(self),
        )

    async def update_reaction_summary(self, interaction):
        await interaction.response.edit_message(
            embed=_step4_embed(self.channel, self.role, "reaction", self.message_id, self.emoji),
            view=ReactionSetupView(self),
        )

    async def finalize(self, interaction):
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="⏳ Finalizing setup...",
                description="Please wait a moment.",
                color=discord.Color.blue(),
            ),
            view=None,
        )

        try:
            conf = self.cog.config.guild(self.ctx.guild)

            if self.mode == "button":
                await conf.verification_role_id.set(self.role.id)
                await conf.verification_channel_id.set(self.channel.id)
                await conf.verification_mode.set(self.mode)
                await conf.verification_emoji.set(self.emoji)
                msg = await self.channel.send(embed=_verification_embed(), view=self.cog.verify_view)
                await conf.verification_message_id.set(msg.id)
                desc = f"✅ A new verification message has been created in {self.channel.mention}."
            else:
                message = await self.channel.fetch_message(self.message_id)
                try:
                    await message.add_reaction(self.emoji)
                except (discord.HTTPException, discord.Forbidden):
                    raise RuntimeError(
                        f"Could not add reaction `{self.emoji}`. "
                        "Please check the **Add Reactions** permission."
                    )
                await conf.verification_role_id.set(self.role.id)
                await conf.verification_channel_id.set(self.channel.id)
                await conf.verification_mode.set(self.mode)
                await conf.verification_emoji.set(self.emoji)
                await conf.verification_message_id.set(message.id)
                desc = f"✅ The reaction {self.emoji} has been added to the [message]({message.jump_url})."

            await interaction.edit_original_response(
                embed=_success_embed(desc, self.role, self.channel, self.mode, self.emoji)
            )
        except discord.Forbidden:
            await interaction.edit_original_response(
                embed=_error_embed(
                    "I am missing permissions. Please ensure I have:\n"
                    "• Send Messages & Embed Links\n"
                    "• Add Reactions & Read Message History\n"
                    "• Manage Roles (with the verification role below my highest role)"
                )
            )
            return
        except Exception as e:
            await interaction.edit_original_response(
                embed=_error_embed(f"An unexpected error occurred:\n```\n{type(e).__name__}: {e}\n```")
            )
            return

        self._deletion_task = asyncio.create_task(
            self._delete_message_after(SETUP_AUTO_DELETE_SECONDS)
        )

    async def cancel(self, interaction):
        try:
            await interaction.response.edit_message(embed=_cancel_embed(), view=None)
        except Exception:
            return
        self._deletion_task = asyncio.create_task(
            self._delete_message_after(CANCEL_AUTO_DELETE_SECONDS)
        )

    async def _delete_message_after(self, seconds):
        await asyncio.sleep(seconds)
        try:
            if self.message:
                await self.message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


# ──────────────────────────────────────────────
#  Wizard views
# ──────────────────────────────────────────────

class SetupChannelView(discord.ui.View):
    def __init__(self, wizard):
        super().__init__(timeout=300)
        self.wizard = wizard

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Step 1/4: Select the verification channel...",
        channel_types=[discord.ChannelType.text],
        min_values=1, max_values=1,
    )
    async def channel_select(self, interaction, select):
        raw = select.values[0]
        channel = interaction.guild.get_channel(raw.id)
        if channel is None or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Could not resolve the selected channel. Please try again.", ephemeral=True
            )
            return
        self.wizard.channel = channel
        await self.wizard.show_step2(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(self, interaction, button):
        await self.wizard.cancel(interaction)
        self.stop()


class SetupRoleView(discord.ui.View):
    def __init__(self, wizard):
        super().__init__(timeout=300)
        self.wizard = wizard

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Step 2/4: Select the verification role...",
        min_values=1, max_values=1,
    )
    async def role_select(self, interaction, select):
        raw = select.values[0]
        role = interaction.guild.get_role(raw.id)
        if role is None:
            await interaction.response.send_message(
                "❌ Could not resolve the selected role. Please try again.", ephemeral=True
            )
            return
        self.wizard.role = role
        await self.wizard.show_step3(interaction)
        self.stop()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction, button):
        await interaction.response.edit_message(
            embed=_step1_embed(), view=SetupChannelView(self.wizard)
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(self, interaction, button):
        await self.wizard.cancel(interaction)
        self.stop()


class SetupModeView(discord.ui.View):
    def __init__(self, wizard):
        super().__init__(timeout=300)
        self.wizard = wizard

    @discord.ui.button(label="Send new message", style=discord.ButtonStyle.primary, emoji="📝")
    async def new_message_button(self, interaction, button):
        await self.wizard.show_step4_button(interaction)
        self.stop()

    @discord.ui.button(label="Use existing message", style=discord.ButtonStyle.secondary, emoji="💬")
    async def existing_message_button(self, interaction, button):
        modal = MessageIDModal(self.wizard)
        await interaction.response.send_modal(modal)
        self.stop()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction, button):
        await interaction.response.edit_message(
            embed=_step2_embed(self.wizard.channel), view=SetupRoleView(self.wizard)
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(self, interaction, button):
        await self.wizard.cancel(interaction)
        self.stop()


class SetupConfirmView(discord.ui.View):
    def __init__(self, wizard):
        super().__init__(timeout=300)
        self.wizard = wizard

    @discord.ui.button(label="Confirm & Create", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction, button):
        await self.wizard.finalize(interaction)
        self.stop()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction, button):
        await interaction.response.edit_message(
            embed=_step3_embed(self.wizard.channel, self.wizard.role),
            view=SetupModeView(self.wizard),
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction, button):
        await self.wizard.cancel(interaction)
        self.stop()


class ReactionSetupView(discord.ui.View):
    def __init__(self, wizard):
        super().__init__(timeout=300)
        self.wizard = wizard

        emoji_options = list(wizard.cog.emoji_options) or [
            (DEFAULT_VERIFICATION_EMOJI, "Check Mark Button")
        ]
        options = [
            discord.SelectOption(
                label=str(name)[:100],
                value=str(emoji)[:100],
                emoji=str(emoji),
                default=(_normalize_emoji(emoji) == _normalize_emoji(wizard.emoji)),
            )
            for emoji, name in emoji_options[:25]
        ]

        select = discord.ui.Select(
            placeholder="Choose a reaction emoji...",
            min_values=1, max_values=1, options=options,
        )
        select.callback = self._on_emoji_select
        self.add_item(select)

    async def _on_emoji_select(self, interaction: discord.Interaction):
        try:
            new_emoji = interaction.data["values"][0]
        except (KeyError, TypeError, IndexError):
            return
        self.wizard.emoji = new_emoji
        await self.wizard.update_reaction_summary(interaction)

    @discord.ui.button(label="Confirm & Create", style=discord.ButtonStyle.success, row=1)
    async def confirm_button(self, interaction, button):
        await self.wizard.finalize(interaction)
        self.stop()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction, button):
        await interaction.response.edit_message(
            embed=_step3_embed(self.wizard.channel, self.wizard.role),
            view=SetupModeView(self.wizard),
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(self, interaction, button):
        await self.wizard.cancel(interaction)
        self.stop()


class MessageIDModal(discord.ui.Modal, title="Existing Message ID"):
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


# ──────────────────────────────────────────────
#  "Not set up" view
# ──────────────────────────────────────────────

class NotSetupView(discord.ui.View):
    def __init__(self, cog: "Verification", ctx: commands.Context):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx

    @discord.ui.button(label="Start Setup", style=discord.ButtonStyle.success, emoji="🚀")
    async def start_setup_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        wizard = SetupWizard(self.cog, self.ctx)
        wizard.message = interaction.message
        try:
            await interaction.response.edit_message(
                embed=_step1_embed(), view=SetupChannelView(wizard)
            )
        except discord.HTTPException:
            return
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.message.delete()
        except Exception:
            pass
        self.stop()


# ──────────────────────────────────────────────
#  Verified users paginator view
# ──────────────────────────────────────────────

class VerifiedPaginatorView(discord.ui.View):
    """Simple Prev/Next paginator for the verified users list."""

    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=180)
        self.pages = pages
        self.index = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.index == 0
        self.next_btn.disabled = self.index >= len(self.pages) - 1

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.pages) - 1:
            self.index += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)


# ──────────────────────────────────────────────
#  Verify Menu views
# ──────────────────────────────────────────────

class VerificationMenuView(discord.ui.View):
    def __init__(self, cog: "Verification", guild: discord.Guild):
        super().__init__(timeout=MENU_TIMEOUT_SECONDS)
        self.cog = cog
        self.guild = guild
        self.message = None

    async def build_embed(self) -> discord.Embed:
        conf = self.cog.config.guild(self.guild)
        return _status_embed(
            await conf.verification_channel_id(),
            await conf.verification_message_id(),
            await conf.verification_role_id(),
            await conf.verification_mode(),
            await conf.verification_emoji(),
            title="⚙️ Verification Menu",
        )

    @discord.ui.button(label="Change Emoji", style=discord.ButtonStyle.primary, emoji="😀")
    async def change_emoji_button(self, interaction, button):
        conf = self.cog.config.guild(self.guild)
        if await conf.verification_mode() != "reaction":
            await interaction.response.send_message(
                "❌ Changing the emoji is only available in **reaction** mode. "
                "The button mode always uses ✅.",
                ephemeral=True,
            )
            return
        view = EmojiChangeView(self.cog, self.guild, self)
        embed = discord.Embed(
            title="😀 Change Reaction Emoji",
            description=(
                "Select a new emoji for the verification message.\n"
                "The old reaction will be removed and the new one added automatically."
                + CREDIT_LINE
            ),
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Change Message", style=discord.ButtonStyle.primary, emoji="💬")
    async def change_message_button(self, interaction, button):
        conf = self.cog.config.guild(self.guild)
        mode = await conf.verification_mode()
        channel_id = await conf.verification_channel_id()
        if not channel_id:
            await interaction.response.send_message(
                "❌ No verification channel configured. Run `.verifysetup start` first.",
                ephemeral=True,
            )
            return
        channel = self.guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.cog.bot.fetch_channel(channel_id)
            except Exception:
                channel = None
        if channel is None:
            await interaction.response.send_message(
                "❌ The configured channel no longer exists.", ephemeral=True
            )
            return
        if mode == "reaction":
            await interaction.response.send_modal(
                ChangeMessageModal(self.cog, self.guild, self, channel)
            )
        else:
            await interaction.response.defer(ephemeral=True)
            message_id = await conf.verification_message_id()
            deleted_old = False
            if message_id:
                try:
                    old = await channel.fetch_message(message_id)
                    await old.delete()
                    deleted_old = True
                except Exception:
                    pass
            new_msg = await channel.send(embed=_verification_embed(), view=self.cog.verify_view)
            await conf.verification_message_id.set(new_msg.id)
            await interaction.followup.send(
                f"✅ {'Deleted the old message and ' if deleted_old else ''}"
                f"posted a new verification message in {channel.mention}.",
                ephemeral=True,
            )

    @discord.ui.button(label="Reset Setup", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def reset_button(self, interaction, button):
        view = ConfirmResetView(self.cog, self.guild, self)
        embed = discord.Embed(
            title="⚠️ Confirm Reset",
            description=(
                "Are you sure you want to reset the verification setup?\n\n"
                "This will:\n"
                "• Delete / remove the verification message or reaction\n"
                "• Clear all stored settings for this server\n\n"
                "**This cannot be undone.**"
                + CREDIT_LINE
            ),
            color=discord.Color.orange(),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Sync Now", style=discord.ButtonStyle.primary, emoji="🔄")
    async def sync_button(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        result = await self.cog._sync_guild(self.guild)
        await interaction.followup.send(
            f"🔄 **Sync complete.**\n{result}", ephemeral=True
        )

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def close_button(self, interaction, button):
        try:
            await interaction.message.delete()
        except Exception:
            pass
        self.stop()


class EmojiChangeView(discord.ui.View):
    def __init__(self, cog, guild, parent):
        super().__init__(timeout=MENU_TIMEOUT_SECONDS)
        self.cog = cog
        self.guild = guild
        self.parent = parent

        emoji_options = list(cog.emoji_options) or [
            (DEFAULT_VERIFICATION_EMOJI, "Check Mark Button")
        ]
        options = [
            discord.SelectOption(
                label=str(name)[:100],
                value=str(emoji)[:100],
                emoji=str(emoji),
            )
            for emoji, name in emoji_options[:25]
        ]
        select = discord.ui.Select(
            placeholder="Choose a new reaction emoji...",
            min_values=1, max_values=1, options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        try:
            new_emoji = interaction.data["values"][0]
        except (KeyError, TypeError, IndexError):
            return

        conf = self.cog.config.guild(self.guild)
        old_emoji = await conf.verification_emoji() or DEFAULT_VERIFICATION_EMOJI

        if _normalize_emoji(new_emoji) == _normalize_emoji(old_emoji):
            await self._back_to_menu(interaction)
            return

        channel_id = await conf.verification_channel_id()
        message_id = await conf.verification_message_id()
        swap_note = ""

        if channel_id and message_id:
            channel = self.guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.cog.bot.fetch_channel(channel_id)
                except Exception:
                    channel = None
            if channel is not None:
                try:
                    message = await channel.fetch_message(message_id)
                except Exception:
                    await interaction.response.edit_message(
                        embed=discord.Embed(
                            title="⚠️ Emoji Change Failed",
                            description=(
                                "Could not access the configured verification message.\n"
                                "The emoji was **not changed**." + CREDIT_LINE
                            ),
                            color=discord.Color.red(),
                        ),
                        view=self.parent,
                    )
                    return

                try:
                    await message.add_reaction(new_emoji)
                except Exception:
                    await interaction.response.edit_message(
                        embed=discord.Embed(
                            title="⚠️ Emoji Change Failed",
                            description=(
                                f"Could not add the new reaction `{new_emoji}`.\n"
                                "Please check my **Add Reactions** permission.\n"
                                "The emoji was **not changed**." + CREDIT_LINE
                            ),
                            color=discord.Color.red(),
                        ),
                        view=self.parent,
                    )
                    return

                try:
                    await message.clear_reaction(old_emoji)
                except Exception:
                    pass

                swap_note = f"\n\n✅ Reaction on the [message]({message.jump_url}) updated."

        await conf.verification_emoji.set(new_emoji)
        await self._back_to_menu(interaction, note=swap_note)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction, button):
        await self._back_to_menu(interaction)

    async def _back_to_menu(self, interaction, note: str = ""):
        embed = await self.parent.build_embed()
        if note:
            embed.description = (embed.description or "") + note
        await interaction.response.edit_message(embed=embed, view=self.parent)


class ConfirmResetView(discord.ui.View):
    def __init__(self, cog, guild, parent):
        super().__init__(timeout=MENU_TIMEOUT_SECONDS)
        self.cog = cog
        self.guild = guild
        self.parent = parent

    @discord.ui.button(label="Yes, reset", style=discord.ButtonStyle.danger)
    async def yes_button(self, interaction, button):
        await interaction.response.defer(ephemeral=False)
        cleanup = await self.cog._do_reset(self.guild)
        embed = discord.Embed(
            title="✅ Reset Complete",
            description=(
                "The verification setup has been reset for this server.\n\n"
                "**Cleanup:**\n" + "\n".join(cleanup) + CREDIT_LINE
            ),
            color=discord.Color.green(),
        )
        await interaction.edit_original_response(embed=embed, view=None)
        try:
            msg = await interaction.original_response()
            asyncio.create_task(self.cog._delete_message_after(msg, SETUP_AUTO_DELETE_SECONDS))
        except Exception:
            pass
        self.parent.stop()

    @discord.ui.button(label="No, go back", style=discord.ButtonStyle.secondary)
    async def no_button(self, interaction, button):
        embed = await self.parent.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent)


class ChangeMessageModal(discord.ui.Modal, title="Change Verification Message"):
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
        emoji = await conf.verification_emoji() or DEFAULT_VERIFICATION_EMOJI

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


# ──────────────────────────────────────────────
#  Main Cog
# ──────────────────────────────────────────────

class Verification(commands.Cog):
    """Cog for user verification with math or text challenges."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=9876543210, force_registration=True)
        self.config.register_guild(
            verification_channel_id=None,
            verification_message_id=None,
            verification_role_id=None,
            verification_mode="button",
            verification_emoji=DEFAULT_VERIFICATION_EMOJI,
            verified_users=[],
            failed_attempts={},
        )
        self.verify_view = VerifyView(self)
        self.data_path: Path = cog_data_path(self)
        self.config_file: Path = self.data_path / DATA_FILE_NAME
        self.verified_file: Path = self.data_path / VERIFIED_FILE_NAME
        self.emoji_options: list[tuple[str, str]] = []
        self.text_challenges: list[tuple[str, str]] = []
        self.security_questions: list[tuple[str, str]] = []

    async def cog_load(self):
        try:
            self.data_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        if not self.config_file.exists():
            await self._write_default_data()
        await self._read_data()

        if not self._sync_loop.is_running():
            self._sync_loop.start()

    async def cog_unload(self):
        self.verify_view.stop()
        if self._sync_loop.is_running():
            self._sync_loop.cancel()

    # ─── Data file ───

    async def _write_default_data(self):
        default_data = {
            "emoji_options": _DEFAULT_EMOJI_OPTIONS,
            "text_challenges": _DEFAULT_TEXT_CHALLENGES,
            "security_questions": _DEFAULT_SECURITY_QUESTIONS,
        }
        try:
            self.config_file.write_text(
                json.dumps(default_data, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    async def _read_data(self):
        try:
            data = json.loads(self.config_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}

        emoji_list = data.get("emoji_options") or _DEFAULT_EMOJI_OPTIONS
        text_list = data.get("text_challenges") or _DEFAULT_TEXT_CHALLENGES
        sec_list = data.get("security_questions") or _DEFAULT_SECURITY_QUESTIONS

        self.emoji_options = [
            (str(p[0]), str(p[1])) for p in emoji_list
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]
        self.text_challenges = [
            (str(p[0]), str(p[1])) for p in text_list
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]
        self.security_questions = [
            (str(p[0]), str(p[1])) for p in sec_list
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]

        if not self.emoji_options:
            self.emoji_options = [(a, b) for a, b in _DEFAULT_EMOJI_OPTIONS]
        if not self.text_challenges:
            self.text_challenges = [(a, b) for a, b in _DEFAULT_TEXT_CHALLENGES]
        if not self.security_questions:
            self.security_questions = [(a, b) for a, b in _DEFAULT_SECURITY_QUESTIONS]

    async def _write_verified_users_file(self, guild: discord.Guild):
        conf = self.config.guild(guild)
        users = await conf.verified_users()
        try:
            raw = self.verified_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        data[str(guild.id)] = users
        try:
            self.verified_file.write_text(
                json.dumps(data, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _generate_challenge(self) -> tuple[str, str, bool]:
        if random.random() < 0.5:
            op = random.choice(["+", "-", "*"])
            if op == "+":
                a, b = random.randint(1, 20), random.randint(1, 20)
                answer = a + b
            elif op == "-":
                a, b = random.randint(1, 20), random.randint(1, 20)
                if a < b:
                    a, b = b, a
                answer = a - b
            else:
                a, b = random.randint(1, 10), random.randint(1, 10)
                answer = a * b
            return (f"What is {a} {op} {b}?", str(answer), True)
        else:
            pool = self.text_challenges or [(p, a) for p, a in _DEFAULT_TEXT_CHALLENGES]
            prompt, answer = random.choice(pool)
            return (prompt, answer, False)

    # ─── Helpers ───

    async def _delete_message_after(self, message: discord.Message, seconds: float):
        await asyncio.sleep(seconds)
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    async def _is_setup(self, guild: discord.Guild) -> bool:
        conf = self.config.guild(guild)
        return any([
            await conf.verification_channel_id(),
            await conf.verification_message_id(),
            await conf.verification_role_id(),
        ])

    def _user_has_verification_role(self, guild, member, role_id) -> bool:
        if not role_id:
            return False
        role = guild.get_role(role_id)
        if role is None:
            return False
        return role in member.roles

    async def _remove_verification_reaction(self, guild, member):
        conf = self.config.guild(guild)
        channel_id = await conf.verification_channel_id()
        message_id = await conf.verification_message_id()
        emoji = await conf.verification_emoji() or DEFAULT_VERIFICATION_EMOJI
        if not channel_id or not message_id:
            return
        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                return
        try:
            message = await channel.fetch_message(message_id)
            await message.remove_reaction(emoji, member)
        except Exception:
            pass

    async def _cleanup_channel(self, channel, log) -> int:
        deleted = 0
        try:
            async for message in channel.history(limit=500):
                if message.author.id != self.bot.user.id or not message.embeds:
                    continue
                if "Server Verification" in (message.embeds[0].title or ""):
                    try:
                        await message.delete()
                        deleted += 1
                    except (discord.Forbidden, discord.NotFound):
                        log.append(f"⚠️ Could not delete a message in {channel.mention}")
                    except discord.HTTPException:
                        pass
        except discord.Forbidden:
            log.append(f"⚠️ Missing 'Read Message History' in {channel.mention}")
        except Exception as e:
            log.append(f"⚠️ Scan error in {channel.mention}: `{type(e).__name__}: {e}`")
        return deleted

    async def _do_reset(self, guild) -> list[str]:
        conf = self.config.guild(guild)
        channel_id = await conf.verification_channel_id()
        message_id = await conf.verification_message_id()
        mode = await conf.verification_mode()
        emoji = await conf.verification_emoji() or DEFAULT_VERIFICATION_EMOJI

        cleanup_lines: list[str] = []
        deleted_total = 0

        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    channel = None
            if channel is not None:
                if message_id:
                    try:
                        message = await channel.fetch_message(message_id)
                        if mode == "button":
                            try:
                                await message.delete()
                                deleted_total += 1
                            except Exception:
                                pass
                        elif mode == "reaction":
                            try:
                                await message.clear_reaction(emoji)
                                cleanup_lines.append(f"🧹 Removed {emoji} reactions")
                            except Exception:
                                pass
                    except Exception:
                        pass
                deleted_total += await self._cleanup_channel(channel, cleanup_lines)
            else:
                cleanup_lines.append("⚠️ Stored channel no longer exists")

        await self.config.guild(guild).clear()

        cleanup_lines.append(
            f"🗑️ Deleted {deleted_total} verification message(s)" if deleted_total
            else "ℹ️ No verification messages found to delete"
        )
        return cleanup_lines

    async def _post_security_check_in_channel(self, guild, member):
        conf = self.config.guild(guild)
        channel_id = await conf.verification_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if channel is None:
            return
        view = SecurityCheckStartView(self, member, guild)
        try:
            msg = await channel.send(
                content=(
                    f"{member.mention}\n"
                    f"🔐 **Security Check**\n\n"
                    f"You were previously verified but no longer have the verification role.\n"
                    f"Please complete a short security check to verify again.\n\n"
                    f"-# If you don't want to verify, click Cancel or wait – "
                    f"your reaction will be removed automatically."
                ),
                view=view,
            )
            view.message = msg
        except discord.Forbidden:
            pass

    async def _post_challenge_in_channel(self, guild, member):
        conf = self.config.guild(guild)
        channel_id = await conf.verification_channel_id()
        channel = guild.get_channel(channel_id) if channel_id else None
        if channel is None:
            return
        prompt, correct_answer, is_math = self._generate_challenge()
        view = ChannelChallengeStartView(self, prompt, correct_answer, member, guild, is_math)
        try:
            msg = await channel.send(
                content=(
                    f"{member.mention}\n"
                    f"🔐 **Verification**\n\n"
                    f"**{prompt}**\n\n"
                    f"Click the button below to enter your answer.\n\n"
                    f"-# Made by [{CREDIT_NAME}]({CREDIT_URL})"
                ),
                view=view,
            )
            view.message = msg
        except discord.Forbidden:
            pass

    # ─── Background sync ───

    @tasks.loop(minutes=SYNC_INTERVAL_MINUTES)
    async def _sync_loop(self):
        for guild in self.bot.guilds:
            try:
                await self._sync_guild(guild)
            except Exception:
                continue

    @_sync_loop.before_loop
    async def _before_sync(self):
        await self.bot.wait_until_ready()

    async def _sync_guild(self, guild) -> str:
        conf = self.config.guild(guild)
        if await conf.verification_mode() != "reaction":
            return "Skipped (not in reaction mode)."

        role_id = await conf.verification_role_id()
        channel_id = await conf.verification_channel_id()
        message_id = await conf.verification_message_id()
        if not role_id or not channel_id or not message_id:
            return "Skipped (incomplete configuration)."

        role = guild.get_role(role_id)
        if role is None:
            return "Skipped (role not found)."

        emoji = await conf.verification_emoji() or DEFAULT_VERIFICATION_EMOJI
        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                return "Skipped (channel unavailable)."
        try:
            message = await channel.fetch_message(message_id)
        except Exception:
            return "Skipped (message unavailable)."

        reacted_ids: set[int] = set()
        for reaction in message.reactions:
            if _normalize_emoji(reaction.emoji) == _normalize_emoji(emoji):
                try:
                    async for user in reaction.users():
                        if not user.bot:
                            reacted_ids.add(user.id)
                except Exception:
                    pass
                break

        role_member_ids = {m.id for m in role.members if not m.bot}
        verified_users = set(await conf.verified_users())

        roles_removed = 0
        reactions_removed = 0

        # 1. Has role but no reaction AND in verified_users → remove role
        for member in list(role.members):
            if member.bot or member.id in reacted_ids:
                continue
            if member.id not in verified_users:
                continue
            try:
                await member.remove_roles(role, reason="Verification reaction removed")
                roles_removed += 1
            except Exception:
                pass

        # 2. Has reaction but no role AND in verified_users → remove reaction
        for user_id in list(reacted_ids):
            if user_id in role_member_ids:
                continue
            member = guild.get_member(user_id)
            if member is None:
                continue
            if user_id in verified_users:
                try:
                    await message.remove_reaction(emoji, member)
                    reactions_removed += 1
                except Exception:
                    pass

        if roles_removed == 0 and reactions_removed == 0:
            return "✅ Everything is in sync."
        return (
            f"🔧 Removed **{roles_removed}** role(s) (no reaction) and "
            f"**{reactions_removed}** reaction(s) (no role)."
        )

    # ─── Commands ───

    @commands.group()
    @commands.admin_or_permissions(manage_guild=True)
    async def verifysetup(self, ctx: commands.Context):
        """Setup process for the verification system."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @verifysetup.command(name="start")
    async def verifysetup_start(self, ctx: commands.Context):
        """Starts the interactive setup wizard."""
        await SetupWizard(self, ctx).start()

    @verifysetup.command(name="status")
    async def verifysetup_status(self, ctx: commands.Context):
        """Shows the current status (auto-deletes after 8s)."""
        conf = self.config.guild(ctx.guild)
        embed = _status_embed(
            await conf.verification_channel_id(),
            await conf.verification_message_id(),
            await conf.verification_role_id(),
            await conf.verification_mode(),
            await conf.verification_emoji(),
        )
        msg = await ctx.send(embed=embed)
        asyncio.create_task(self._delete_message_after(msg, SETUP_AUTO_DELETE_SECONDS))

    @verifysetup.command(name="reset")
    async def verifysetup_reset(self, ctx: commands.Context):
        """Resets the setup and cleans up everything (auto-deletes after 8s)."""
        cleanup = await self._do_reset(ctx.guild)
        embed = discord.Embed(
            title="✅ Reset Complete",
            description=(
                "The verification setup has been reset for this server.\n\n"
                "**Cleanup:**\n" + "\n".join(cleanup) + CREDIT_LINE
            ),
            color=discord.Color.green(),
        )
        msg = await ctx.send(embed=embed)
        asyncio.create_task(self._delete_message_after(msg, SETUP_AUTO_DELETE_SECONDS))

    @verifysetup.command(name="cleanup")
    async def verifysetup_cleanup(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Scans a channel for leftover verification messages and deletes them."""
        if channel is None:
            channel_id = await self.config.guild(ctx.guild).verification_channel_id()
            if not channel_id:
                await ctx.send("❌ No channel provided and none configured.")
                return
            channel = ctx.guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    await ctx.send("❌ The configured channel no longer exists.")
                    return
        log: list[str] = []
        deleted = await self._cleanup_channel(channel, log)
        embed = discord.Embed(
            title="🧹 Cleanup Complete",
            description=(
                f"**Channel:** {channel.mention if hasattr(channel, 'mention') else channel.id}\n"
                f"**Result:** " + (
                    f"🗑️ Deleted {deleted} verification message(s)" if deleted
                    else "ℹ️ No verification messages found"
                )
                + (("\n\n**Notes:**\n" + "\n".join(log)) if log else "")
                + CREDIT_LINE
            ),
            color=discord.Color.green() if deleted else discord.Color.blue(),
        )
        msg = await ctx.send(embed=embed)
        asyncio.create_task(self._delete_message_after(msg, SETUP_AUTO_DELETE_SECONDS))

    @verifysetup.command(name="reloaddata")
    async def verifysetup_reloaddata(self, ctx: commands.Context):
        """Reloads the emoji/text/security data file from disk."""
        await self._read_data()
        embed = discord.Embed(
            title="🔄 Data Reloaded",
            description=(
                f"Loaded **{len(self.emoji_options)}** emoji options, "
                f"**{len(self.text_challenges)}** text challenges and "
                f"**{len(self.security_questions)}** security questions from "
                f"`{self.config_file.name}`." + CREDIT_LINE
            ),
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @verifysetup.command(name="sync")
    async def verifysetup_sync(self, ctx: commands.Context):
        """Manually runs the reaction/role sync for this server."""
        result = await self._sync_guild(ctx.guild)
        embed = discord.Embed(
            title="🔄 Sync Complete",
            description=result + CREDIT_LINE,
            color=discord.Color.green(),
        )
        msg = await ctx.send(embed=embed)
        asyncio.create_task(self._delete_message_after(msg, SETUP_AUTO_DELETE_SECONDS))

    @verifysetup.command(name="verified")
    async def verifysetup_verified(self, ctx: commands.Context):
        """
        Shows the list of verified users (ephemeral, paginated, 5 per page).
        Only visible to you.
        """
        conf = self.config.guild(ctx.guild)
        users = await conf.verified_users()

        if not users:
            try:
                await ctx.send(
                    "ℹ️ No verified users stored for this server.",
                    ephemeral=True,
                )
            except TypeError:
                # Fallback if ephemeral isn't supported
                msg = await ctx.send("ℹ️ No verified users stored for this server.")
                asyncio.create_task(self._delete_message_after(msg, SETUP_AUTO_DELETE_SECONDS))
            return

        total = len(users)
        total_pages = (total + VERIFIED_PAGE_SIZE - 1) // VERIFIED_PAGE_SIZE

        pages: list[discord.Embed] = []
        for i in range(0, total, VERIFIED_PAGE_SIZE):
            chunk = users[i:i + VERIFIED_PAGE_SIZE]
            page_num = (i // VERIFIED_PAGE_SIZE) + 1
            lines = []
            for uid in chunk:
                member = ctx.guild.get_member(uid)
                if member is not None:
                    lines.append(f"• {member.mention} — `{uid}`")
                else:
                    lines.append(f"• <@{uid}> (not on server) — `{uid}`")

            embed = discord.Embed(
                title=f"✅ Verified Users — Page {page_num}/{total_pages}",
                description=(
                    f"**Total:** {total}\n\n"
                    + "\n".join(lines)
                    + CREDIT_LINE
                ),
                color=discord.Color.green(),
            )
            embed.set_footer(
                text=f"File: {self.verified_file.name} • Only you can see this • "
                     f"Page {page_num}/{total_pages}"
            )
            pages.append(embed)

        view = VerifiedPaginatorView(pages) if len(pages) > 1 else None

        try:
            await ctx.send(embed=pages[0], view=view, ephemeral=True)
        except TypeError:
            # Fallback: send normally and auto-delete
            msg = await ctx.send(embed=pages[0], view=view)
            asyncio.create_task(self._delete_message_after(msg, 120))

    @commands.command(name="verifymenu")
    @commands.admin_or_permissions(manage_guild=True)
    async def verifymenu(self, ctx: commands.Context):
        """Opens the interactive verification menu."""
        if not await self._is_setup(ctx.guild):
            await ctx.send(embed=_not_setup_embed(), view=NotSetupView(self, ctx))
            return
        view = VerificationMenuView(self, ctx.guild)
        view.message = await ctx.send(embed=await view.build_embed(), view=view)

    # ─── Reaction listener ───

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id or payload.guild_id is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        conf = self.config.guild(guild)
        if await conf.verification_mode() != "reaction":
            return
        if await conf.verification_message_id() != payload.message_id:
            return
        stored_emoji = await conf.verification_emoji() or DEFAULT_VERIFICATION_EMOJI
        if _normalize_emoji(payload.emoji) != _normalize_emoji(stored_emoji):
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            return

        role_id = await conf.verification_role_id()
        verified_users = await conf.verified_users()
        has_role = self._user_has_verification_role(guild, member, role_id)

        # Case 1: On verified list AND still has role → nothing to do
        if member.id in verified_users and has_role:
            return

        # Case 2: On verified list but LOST role → post security check, keep reaction
        if member.id in verified_users and not has_role:
            await self._post_security_check_in_channel(guild, member)
            return

        # Case 3: Not on verified list → check lockout
        failed_attempts = await conf.failed_attempts()
        user_data = failed_attempts.get(str(member.id))
        if user_data and user_data.get("locked_until"):
            locked_until = datetime.fromisoformat(user_data["locked_until"])
            if datetime.now(timezone.utc) < locked_until:
                await self._remove_verification_reaction(guild, member)
                remaining = (locked_until - datetime.now(timezone.utc)).total_seconds()
                progress = max(0, min(20, int((1 - remaining / 600) * 20)))
                bar = "█" * progress + "░" * (20 - progress)
                minutes, seconds = int(remaining // 60), int(remaining % 60)
                channel_id = await conf.verification_channel_id()
                channel = guild.get_channel(channel_id) if channel_id else None
                if channel:
                    try:
                        await channel.send(
                            f"{member.mention} ⏳ You are still locked out.\n"
                            f"`[{bar}]` **{minutes}:{seconds:02d}** minutes remaining.",
                            delete_after=15,
                        )
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                return

        if not role_id:
            return

        await self._post_challenge_in_channel(guild, member)

    # ─── Button mode entry ───

    async def start_verification(self, interaction: discord.Interaction):
        member = interaction.user
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("❌ This only works on a server.", ephemeral=True)
            return

        conf = self.config.guild(guild)
        role_id = await conf.verification_role_id()
        verified_users = await conf.verified_users()
        has_role = self._user_has_verification_role(guild, member, role_id)

        if member.id in verified_users and has_role:
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return

        if member.id in verified_users and not has_role:
            pool = self.security_questions or [(q, a) for q, a in _DEFAULT_SECURITY_QUESTIONS]
            if len(pool) < 2:
                await interaction.response.send_message(
                    "⚠️ Security questions are not configured properly. "
                    "Please contact an admin.", ephemeral=True,
                )
                return
            questions = random.sample(pool, 2)
            await interaction.response.send_modal(
                SecurityCheckModal(self, member, guild, questions, mode="button")
            )
            return

        failed_attempts = await conf.failed_attempts()
        user_data = failed_attempts.get(str(member.id))
        if user_data and user_data.get("locked_until"):
            locked_until = datetime.fromisoformat(user_data["locked_until"])
            if datetime.now(timezone.utc) < locked_until:
                await self._show_lockout_ephemeral(interaction, locked_until)
                return

        if not role_id:
            await interaction.response.send_message(
                "❌ No verification role configured. Please contact an admin.", ephemeral=True
            )
            return

        prompt, correct_answer, is_math = self._generate_challenge()
        await interaction.response.send_modal(
            ChallengeModal(self, prompt, correct_answer, member, guild, is_math)
        )

    # ─── Answer check ───

    async def check_answer(self, interaction, answer_str, correct_answer, guild, is_math):
        member = interaction.user
        conf = self.config.guild(guild)

        if is_math:
            try:
                is_correct = int(answer_str.strip()) == int(correct_answer)
            except ValueError:
                is_correct = False
        else:
            is_correct = answer_str.strip().lower() == correct_answer.strip().lower()

        if is_correct:
            role_id = await conf.verification_role_id()
            role = guild.get_role(role_id) if role_id else None
            if role is None:
                await interaction.response.send_message(
                    "❌ The verification role is no longer available. Please contact an admin.",
                    ephemeral=True,
                )
                return
            try:
                gm = guild.get_member(member.id) or await guild.fetch_member(member.id)
                await gm.add_roles(role, reason="Verification successful")
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to assign the role. Please contact an admin.",
                    ephemeral=True,
                )
                return
            except discord.NotFound:
                await interaction.response.send_message(
                    "❌ Could not find you on the server.", ephemeral=True
                )
                return
            async with conf.verified_users() as verified:
                if member.id not in verified:
                    verified.append(member.id)
            async with conf.failed_attempts() as attempts:
                attempts.pop(str(member.id), None)

            await self._write_verified_users_file(guild)

            embed = discord.Embed(
                title="✅ Verified!",
                description="You have been successfully verified and received the role!" + CREDIT_LINE,
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # Remove the user's reaction so they can retry
            await self._remove_verification_reaction(guild, member)

            async with conf.failed_attempts() as attempts:
                user_data = attempts.get(str(member.id), {"count": 0, "locked_until": None})
                user_data["count"] += 1
                count = user_data["count"]
                if count >= 3:
                    locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
                    user_data["locked_until"] = locked_until.isoformat()
                    user_data["count"] = 0
                    attempts[str(member.id)] = user_data
                    await interaction.response.send_message(
                        "❌ **Wrong!** You have reached 3 failed attempts.\n"
                        "You are locked out for **10 minutes**.",
                        ephemeral=True,
                    )
                else:
                    attempts[str(member.id)] = user_data
                    await interaction.response.send_message(
                        f"❌ **Wrong!** The correct answer was **{correct_answer}**.\n"
                        f"You have **{3 - count}** attempt(s) left.",
                        ephemeral=True,
                    )

    async def _show_lockout_ephemeral(self, interaction, locked_until):
        remaining = (locked_until - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            await interaction.response.send_message(
                "✅ Your lockout has expired. You can now verify again!", ephemeral=True
            )
            return
        progress = max(0, min(20, int((1 - remaining / 600) * 20)))
        bar = "█" * progress + "░" * (20 - progress)
        minutes, seconds = int(remaining // 60), int(remaining % 60)
        await interaction.response.send_message(
            f"⏳ **You are still locked out.**\n`[{bar}]`\n**{minutes}:{seconds:02d}** minutes remaining.",
            ephemeral=True,
        )