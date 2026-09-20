"""Setup wizard and its views."""

import asyncio

import discord

from .constants import (
    SETUP_AUTO_DELETE_SECONDS,
    CANCEL_AUTO_DELETE_SECONDS,
    DEFAULT_VERIFICATION_EMOJI,
)
from .embeds import (
    step1_embed, step2_embed, step3_embed, step4_embed,
    success_embed, error_embed, cancel_embed, verification_embed,
)
from .modals import MessageIDModal
from .utils import normalize_emoji


# ─────────────────────────────────────────────────────
#  Wizard state manager
# ─────────────────────────────────────────────────────

class SetupWizard:
    def __init__(self, cog, ctx):
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
        self.message = await self.ctx.send(
            embed=step1_embed(), view=SetupChannelView(self)
        )

    async def show_step2(self, interaction):
        await interaction.response.edit_message(
            embed=step2_embed(self.channel), view=SetupRoleView(self)
        )

    async def show_step3(self, interaction):
        await interaction.response.edit_message(
            embed=step3_embed(self.channel, self.role), view=SetupModeView(self)
        )

    async def show_step4_button(self, interaction):
        self.mode = "button"
        self.message_id = None
        self.emoji = DEFAULT_VERIFICATION_EMOJI
        await interaction.response.edit_message(
            embed=step4_embed(self.channel, self.role, "button", None, self.emoji),
            view=SetupConfirmView(self),
        )

    async def show_step4_reaction(self, interaction):
        self.mode = "reaction"
        await interaction.response.edit_message(
            embed=step4_embed(self.channel, self.role, "reaction", self.message_id, self.emoji),
            view=ReactionSetupView(self),
        )

    async def update_reaction_summary(self, interaction):
        await interaction.response.edit_message(
            embed=step4_embed(self.channel, self.role, "reaction", self.message_id, self.emoji),
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
                msg = await self.channel.send(
                    embed=verification_embed(), view=self.cog.verify_view
                )
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
                embed=success_embed(desc, self.role, self.channel, self.mode, self.emoji)
            )
        except discord.Forbidden:
            await interaction.edit_original_response(
                embed=error_embed(
                    "I am missing permissions. Please ensure I have:\n"
                    "• Send Messages & Embed Links\n"
                    "• Add Reactions & Read Message History\n"
                    "• Manage Roles (with the verification role below my highest role)"
                )
            )
            return
        except Exception as e:
            await interaction.edit_original_response(
                embed=error_embed(
                    f"An unexpected error occurred:\n```\n{type(e).__name__}: {e}\n```"
                )
            )
            return

        self._deletion_task = asyncio.create_task(
            self._delete_message_after(SETUP_AUTO_DELETE_SECONDS)
        )

    async def cancel(self, interaction):
        try:
            await interaction.response.edit_message(embed=cancel_embed(), view=None)
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


# ─────────────────────────────────────────────────────
#  Wizard views
# ─────────────────────────────────────────────────────

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
            embed=step1_embed(), view=SetupChannelView(self.wizard)
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
        await interaction.response.send_modal(MessageIDModal(self.wizard))
        self.stop()

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction, button):
        await interaction.response.edit_message(
            embed=step2_embed(self.wizard.channel), view=SetupRoleView(self.wizard)
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
            embed=step3_embed(self.wizard.channel, self.wizard.role),
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
                default=(normalize_emoji(emoji) == normalize_emoji(wizard.emoji)),
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
            embed=step3_embed(self.wizard.channel, self.wizard.role),
            view=SetupModeView(self.wizard),
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(self, interaction, button):
        await self.wizard.cancel(interaction)
        self.stop()


class NotSetupView(discord.ui.View):
    """Shown by .verifymenu when nothing is configured yet."""

    def __init__(self, cog, ctx):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx

    @discord.ui.button(label="Start Setup", style=discord.ButtonStyle.success, emoji="🚀")
    async def start_setup_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        wizard = SetupWizard(self.cog, self.ctx)
        wizard.message = interaction.message
        try:
            await interaction.response.edit_message(
                embed=step1_embed(), view=SetupChannelView(wizard)
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