"""Views for the .verifymenu command."""

import asyncio

import discord

from .constants import (
    MENU_TIMEOUT_SECONDS,
    SETUP_AUTO_DELETE_SECONDS,
    DEFAULT_VERIFICATION_EMOJI,
    CREDIT_LINE,
)
from .embeds import status_embed, verification_embed
from .modals import ChangeMessageModal
from .utils import normalize_emoji


class VerificationMenuView(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__(timeout=MENU_TIMEOUT_SECONDS)
        self.cog = cog
        self.guild = guild
        self.message = None

    async def build_embed(self) -> discord.Embed:
        conf = self.cog.config.guild(self.guild)
        return status_embed(
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
            new_msg = await channel.send(embed=verification_embed(), view=self.cog.verify_view)
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
        await interaction.followup.send(f"🔄 **Sync complete.**\n{result}", ephemeral=True)

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
                label=str(name)[:100], value=str(emoji)[:100], emoji=str(emoji),
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

        if normalize_emoji(new_emoji) == normalize_emoji(old_emoji):
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