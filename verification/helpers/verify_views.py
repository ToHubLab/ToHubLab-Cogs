"""Views used during the user-facing verification flow."""

import asyncio
from datetime import datetime, timezone

import discord

from .constants import (
    CHALLENGE_TIMEOUT_SECONDS,
    DEFAULT_VERIFICATION_EMOJI,
    VERIFIED_PAGE_SIZE,
    DEFAULT_SECURITY_QUESTIONS,
    CREDIT_LINE,
    CREDIT_NAME,
    CREDIT_URL,
)
from .modals import ChallengeModal, SecurityCheckModal
from .utils import normalize_emoji


class VerifyView(discord.ui.View):
    """Persistent view with the verification button."""

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Verify", style=discord.ButtonStyle.success,
        custom_id="verification:start", emoji=DEFAULT_VERIFICATION_EMOJI,
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.start_verification(interaction)


class ChannelChallengeStartView(discord.ui.View):
    """Posted in the channel after a fresh reaction in reaction mode."""

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

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("❌ Not for you.", ephemeral=True)
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
        await self.cog._remove_verification_reaction(self.guild, self.member)
        try:
            if self.message:
                await self.message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


class SecurityCheckStartView(discord.ui.View):
    """Posted in the channel for users who lost their verification role."""

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
        pool = self.cog.security_questions or [(q, a) for q, a in DEFAULT_SECURITY_QUESTIONS]
        if len(pool) < 2:
            await interaction.response.send_message(
                "❌ Security questions are not configured correctly. "
                "Please contact an admin.", ephemeral=True,
            )
            return
        import random
        questions = random.sample(pool, 2)
        await interaction.response.send_modal(
            SecurityCheckModal(
                self.cog, self.member, self.guild, questions,
                mode="reaction", view_ref=self,
            )
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("❌ Not for you.", ephemeral=True)
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
        await self.cog._remove_verification_reaction(self.guild, self.member)
        try:
            if self.message:
                await self.message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


class ContinueChallengeView(discord.ui.View):
    """Button mode: shown after a passed security check."""

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


class VerifiedPaginatorView(discord.ui.View):
    """Prev/Next paginator for the verified users list."""

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