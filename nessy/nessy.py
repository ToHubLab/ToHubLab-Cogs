from __future__ import annotations

import asyncio
import random
import time
from typing import Optional

import discord
from discord.ext import tasks

from redbot.core import commands, Config, bank


# ---------------------------------------------------------------------------
# Boss fight view
# ---------------------------------------------------------------------------

BOSS_WEAPONS = [
    ("🪝", "Hook"),
    ("🥅", "Net"),
    ("🏹", "Harpoon"),
]


class NessyBossView(discord.ui.View):
    """Three-button team fight. Each weapon must be pressed by a distinct user."""

    def __init__(self, cog: "Nessy", emoji: str, guild_id: int, lifetime: int = 6):
        super().__init__(timeout=lifetime)
        self.cog = cog
        self.emoji = emoji
        self.guild_id = guild_id
        self.participants: dict[int, discord.Member] = {}
        self.completed = False
        self.message: Optional[discord.Message] = None
        self.buttons: dict[int, discord.ui.Button] = {}

        for bid, (we, label) in enumerate(BOSS_WEAPONS):
            btn = discord.ui.Button(
                label=label, emoji=we, style=discord.ButtonStyle.primary
            )
            btn.callback = self._make_callback(bid)
            self.add_item(btn)
            self.buttons[bid] = btn

    def _make_callback(self, bid: int):
        async def cb(interaction: discord.Interaction):
            if self.completed:
                await interaction.response.send_message(
                    "This boss fight is already over.", ephemeral=True
                )
                return
            if interaction.guild_id != self.guild_id:
                await interaction.response.send_message(
                    "Wrong server.", ephemeral=True
                )
                return
            if bid in self.participants:
                await interaction.response.send_message(
                    "Someone already used this weapon!", ephemeral=True
                )
                return
            if any(p.id == interaction.user.id for p in self.participants.values()):
                await interaction.response.send_message(
                    "You already joined this fight!", ephemeral=True
                )
                return

            self.participants[bid] = interaction.user
            self.buttons[bid].disabled = True
            name = getattr(interaction.user, "display_name", interaction.user.name)
            self.buttons[bid].label = name[:75]

            if len(self.participants) == 3:
                self.completed = True
                self.stop()
                await interaction.response.edit_message(view=self)
                self.cog._spawn_task(
                    self.cog._complete_boss(
                        self, interaction.guild, interaction.channel
                    )
                )
            else:
                await interaction.response.edit_message(view=self)

        return cb

    async def on_timeout(self):
        if self.completed:
            return
        self.completed = True
        if self.message is not None:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass


# ---------------------------------------------------------------------------
# Regular spawn view
# ---------------------------------------------------------------------------

class NessyView(discord.ui.View):
    """The interactive view attached to a regular Nessy spawn."""

    def __init__(self, cog: "Nessy", emoji: str, guild_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.claimed = False

        emoji_obj = None
        if emoji:
            try:
                emoji_obj = discord.PartialEmoji.from_str(emoji)
            except Exception:
                emoji_obj = emoji

        button = discord.ui.Button(
            label="Catch Nessy!",
            style=discord.ButtonStyle.success,
            emoji=emoji_obj,
        )
        button.callback = self._on_claim
        self.add_item(button)

    async def _on_claim(self, interaction: discord.Interaction):
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message(
                "This Nessy belongs to another server!", ephemeral=True
            )
            return

        if self.claimed:
            await interaction.response.send_message(
                "Someone already caught this Nessy!", ephemeral=True
            )
            return
        self.claimed = True

        guild_conf = self.cog.config.guild_from_id(self.guild_id)
        member_conf = self.cog.config.member_from_ids(
            self.guild_id, interaction.user.id
        )

        lifetime = await guild_conf.lifetime_seconds()
        age = (discord.utils.utcnow() - interaction.message.created_at).total_seconds()
        if age > lifetime:
            try:
                await interaction.message.delete()
            except discord.HTTPException:
                pass
            await interaction.response.send_message(
                "This Nessy already swam away...", ephemeral=True
            )
            return

        try:
            await interaction.message.delete()
        except discord.HTTPException:
            try:
                await interaction.message.edit(view=None)
            except discord.HTTPException:
                pass

        member = interaction.user  # type: ignore[assignment]
        guild = interaction.guild  # type: ignore[assignment]

        catches = await member_conf.catches()
        catches += 1
        await member_conf.catches.set(catches)

        last_catcher_id = await guild_conf.last_catcher_id()
        if last_catcher_id == member.id:
            streak = await member_conf.streak()
            streak += 1
        else:
            streak = 1
        await member_conf.streak.set(streak)
        await guild_conf.last_catcher_id.set(member.id)

        streak_cap = int(await guild_conf.streak_cap())
        bonus_min = int(await guild_conf.streak_bonus_min())
        bonus_max = int(await guild_conf.streak_bonus_max())
        if bonus_min > bonus_max:
            bonus_min, bonus_max = bonus_max, bonus_min

        streak_mult = min(streak, streak_cap) if streak_cap > 0 else streak

        over_cap_bonus = 0
        if streak_cap > 0 and streak > streak_cap:
            over_cap_bonus = random.randint(bonus_min, bonus_max)

        today = discord.utils.utcnow().date().isoformat()
        last_daily = await guild_conf.daily_first_date()
        is_daily_first = last_daily != today
        if is_daily_first:
            await guild_conf.daily_first_date.set(today)
        daily_mult = 2 if is_daily_first else 1

        threshold = int(await guild_conf.catches_required())

        role_rewarded: Optional[discord.Role] = None
        role_id = await guild_conf.reward_role_id()
        if role_id and catches >= threshold:
            role = guild.get_role(role_id)
            if role is not None and role not in member.roles:  # type: ignore[union-attr]
                try:
                    await member.add_roles(role, reason=f"Caught Nessy {catches}x!")
                    role_rewarded = role
                except discord.Forbidden:
                    self.cog.log.warning(
                        "Nessy: could not add role %s to %s", role, member
                    )

        min_c = int(await guild_conf.reward_credits_min())
        max_c = int(await guild_conf.reward_credits_max())
        if min_c > max_c:
            min_c, max_c = max_c, min_c
        base_credits = random.randint(min_c, max_c) if max_c > 0 else 0
        total_mult = streak_mult * daily_mult
        credits = (base_credits * total_mult) + over_cap_bonus

        credits_granted = False
        if credits > 0:
            try:
                await bank.deposit_credits(member, credits)
                credits_granted = True
            except Exception as exc:
                self.cog.log.warning("Nessy: could not deposit credits: %s", exc)

        lines = [f"🎉 {member.mention} caught Nessy!"]
        if is_daily_first:
            lines.append("🌟 **First catch of the day!** Bonus ×2")

        if streak > 1:
            fire_count = min(streak, streak_cap) if streak_cap > 0 else streak
            fires = "🔥" * max(1, min(fire_count, 3))
            if streak_cap > 0 and streak > streak_cap:
                lines.append(
                    f"{fires} Streak: **{streak}** (+{over_cap_bonus} extra)"
                )
            else:
                lines.append(f"{fires} Streak: **{streak}** (×{streak_mult})")

        if role_rewarded:
            lines.append(f"🏅 Won the **{role_rewarded.name}** role!")
        elif role_id and catches < threshold:
            remaining = threshold - catches
            lines.append(
                f"🎯 Progress: **{catches}/{threshold}** — "
                f"{remaining} more for the role"
            )

        if credits_granted:
            currency = await bank.get_currency_name(guild)
            lines.append(f"💰 Won **{credits}** {currency}")

        content = "\n".join(lines)

        await interaction.response.send_message(content)

        try:
            announcement = await interaction.original_response()
            delay = int(await guild_conf.announcement_delete_delay())
            self.cog._spawn_task(self.cog._auto_delete(announcement, delay))
        except discord.HTTPException:
            pass


# ---------------------------------------------------------------------------
# Confirmation views
# ---------------------------------------------------------------------------

class ResetConfirmView(discord.ui.View):
    """Second confirmation step for a reset."""

    def __init__(self, cog: "Nessy", guild: discord.Guild, parent: "NessyAdminView"):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild = guild
        self.parent = parent

        yes = discord.ui.Button(
            label="Yes, reset everything", style=discord.ButtonStyle.danger
        )
        yes.callback = self._confirm

        no = discord.ui.Button(
            label="Cancel", style=discord.ButtonStyle.secondary
        )
        no.callback = self._cancel

        self.add_item(yes)
        self.add_item(no)

    async def _confirm(self, interaction: discord.Interaction):
        conf = self.cog.config.guild(self.guild)
        defaults = {
            "enabled": True,
            "excluded_channels": [],
            "reward_role_id": None,
            "reward_credits_min": 1,
            "reward_credits_max": 100,
            "nessy_emoji": "🦕",
            "lifetime_seconds": 3,
            "catches_required": 5,
            "announcement_delete_delay": 10,
            "last_catcher_id": 0,
            "daily_first_date": "",
            "boss_chance": 1,
            "boss_reward_credits_min": 100,
            "boss_reward_credits_max": 500,
            "streak_cap": 3,
            "streak_bonus_min": 5,
            "streak_bonus_max": 15,
        }
        await conf.set(defaults)
        await interaction.response.edit_message(
            content="✅ Configuration has been reset to defaults.",
            embed=None,
            view=None,
        )

    async def _cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="❌ Reset cancelled.", embed=None, view=None
        )


class ResetFirstConfirmView(discord.ui.View):
    """First confirmation step for a reset."""

    def __init__(self, cog: "Nessy", guild: discord.Guild, parent: "NessyAdminView"):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild = guild
        self.parent = parent

        cont = discord.ui.Button(
            label="Continue", style=discord.ButtonStyle.danger
        )
        cont.callback = self._continue

        cancel = discord.ui.Button(
            label="Cancel", style=discord.ButtonStyle.secondary
        )
        cancel.callback = self._cancel

        self.add_item(cont)
        self.add_item(cancel)

    async def _continue(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ Are you absolutely sure?",
            description=(
                "This will reset **all Nessy settings** for this server "
                "(role, credits, boss settings, streak settings, emoji, "
                "lifetime, excluded channels, daily bonus, etc.). "
                "This cannot be undone.\n\n"
                "Click **Yes, reset everything** to confirm."
            ),
            color=0xED4245,
        )
        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=ResetConfirmView(self.cog, self.guild, self.parent),
        )

    async def _cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="❌ Reset cancelled.", embed=None, view=None
        )


# ---------------------------------------------------------------------------
# Modals
# ---------------------------------------------------------------------------

class CreditsModal(discord.ui.Modal, title="Set Reward Credits (Range)"):
    min_c = discord.ui.TextInput(
        label="Minimum credits", placeholder="e.g. 1", required=True, max_length=10
    )
    max_c = discord.ui.TextInput(
        label="Maximum credits", placeholder="e.g. 100", required=True, max_length=10
    )

    def __init__(self, cog: "Nessy", guild: discord.Guild, parent: "NessyAdminView"):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.parent = parent

    async def on_submit(self, interaction: discord.Interaction):
        try:
            lo = int(self.min_c.value)
            hi = int(self.max_c.value)
            if lo < 0 or hi < 0:
                raise ValueError
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "Please enter valid non-negative integers.", ephemeral=True
            )
            return
        if lo > hi:
            lo, hi = hi, lo
        conf = self.cog.config.guild(self.guild)
        await conf.reward_credits_min.set(lo)
        await conf.reward_credits_max.set(hi)
        await interaction.response.edit_message(
            embed=await self.parent.build_embed(), view=self.parent
        )


class LifetimeModal(discord.ui.Modal, title="Set Nessy Lifetime"):
    seconds = discord.ui.TextInput(
        label="Seconds before Nessy disappears", required=True, max_length=6
    )

    def __init__(self, cog: "Nessy", guild: discord.Guild, parent: "NessyAdminView"):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.parent = parent
        self._conf = cog.config.guild(guild)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = int(self.seconds.value)
            if value < 1 or value > 3600:
                raise ValueError
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "Please enter a value between 1 and 3600 seconds.", ephemeral=True
            )
            return
        await self._conf.lifetime_seconds.set(value)
        await interaction.response.edit_message(
            embed=await self.parent.build_embed(), view=self.parent
        )


class EmojiModal(discord.ui.Modal, title="Set Nessy Emoji"):
    emoji = discord.ui.TextInput(
        label="Emoji (use <:name:id> for custom)",
        placeholder="e.g. 🦕 or <:nessy:123456789012345678>",
        required=True, max_length=64,
    )

    def __init__(self, cog: "Nessy", guild: discord.Guild, parent: "NessyAdminView"):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.parent = parent
        self._conf = cog.config.guild(guild)

    async def on_submit(self, interaction: discord.Interaction):
        await self._conf.nessy_emoji.set(self.emoji.value)
        await interaction.response.edit_message(
            embed=await self.parent.build_embed(), view=self.parent
        )


class ThresholdModal(discord.ui.Modal, title="Set Catches Required"):
    amount = discord.ui.TextInput(
        label="Catches needed for the role", placeholder="e.g. 5",
        required=True, max_length=4,
    )

    def __init__(self, cog: "Nessy", guild: discord.Guild, parent: "NessyAdminView"):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.parent = parent

    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = int(self.amount.value)
            if value < 1:
                raise ValueError
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "Please enter a positive integer.", ephemeral=True
            )
            return
        await self.cog.config.guild(self.guild).catches_required.set(value)
        await interaction.response.edit_message(
            embed=await self.parent.build_embed(), view=self.parent
        )


class RoleIdModal(discord.ui.Modal, title="Set Reward Role by ID"):
    role_id = discord.ui.TextInput(
        label="Role ID", placeholder="Right-click role → Copy ID",
        required=True, max_length=25,
    )

    def __init__(self, cog: "Nessy", guild: discord.Guild, parent: "NessyAdminView"):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.parent = parent

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rid = int(self.role_id.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "That is not a valid role ID.", ephemeral=True
            )
            return
        role = self.guild.get_role(rid)
        if role is None:
            await interaction.response.send_message(
                "No role with that ID found on this server.", ephemeral=True
            )
            return
        await self.cog.config.guild(self.guild).reward_role_id.set(rid)
        await interaction.response.edit_message(
            embed=await self.parent.build_embed(), view=self.parent
        )


class DeleteDelayModal(discord.ui.Modal, title="Set Announcement Delete Delay"):
    seconds = discord.ui.TextInput(
        label="Seconds before announcement is deleted", required=True, max_length=5
    )

    def __init__(self, cog: "Nessy", guild: discord.Guild, parent: "NessyAdminView"):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.parent = parent

    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = int(self.seconds.value)
            if value < 1 or value > 3600:
                raise ValueError
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "Please enter a value between 1 and 3600 seconds.", ephemeral=True
            )
            return
        await self.cog.config.guild(self.guild).announcement_delete_delay.set(value)
        await interaction.response.edit_message(
            embed=await self.parent.build_embed(), view=self.parent
        )


class BossSettingsModal(discord.ui.Modal, title="Set Boss Settings"):
    chance = discord.ui.TextInput(
        label="Boss chance (0–100 %)", placeholder="e.g. 1",
        required=True, max_length=3,
    )
    min_c = discord.ui.TextInput(
        label="Min boss credits (per winner)", placeholder="e.g. 100",
        required=True, max_length=10,
    )
    max_c = discord.ui.TextInput(
        label="Max boss credits (per winner)", placeholder="e.g. 500",
        required=True, max_length=10,
    )

    def __init__(self, cog: "Nessy", guild: discord.Guild, parent: "NessyAdminView"):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.parent = parent

    async def on_submit(self, interaction: discord.Interaction):
        try:
            c = int(self.chance.value)
            lo = int(self.min_c.value)
            hi = int(self.max_c.value)
            if not (0 <= c <= 100) or lo < 0 or hi < 0:
                raise ValueError
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "Chance must be 0–100, credits must be ≥ 0.", ephemeral=True
            )
            return
        if lo > hi:
            lo, hi = hi, lo
        conf = self.cog.config.guild(self.guild)
        await conf.boss_chance.set(c)
        await conf.boss_reward_credits_min.set(lo)
        await conf.boss_reward_credits_max.set(hi)
        await interaction.response.edit_message(
            embed=await self.parent.build_embed(), view=self.parent
        )


class StreakSettingsModal(discord.ui.Modal, title="Set Streak Settings"):
    cap = discord.ui.TextInput(
        label="Streak cap (max multiplier)", placeholder="e.g. 3",
        required=True, max_length=3,
    )
    bonus_min = discord.ui.TextInput(
        label="Min over-cap bonus (credits)", placeholder="e.g. 5",
        required=True, max_length=6,
    )
    bonus_max = discord.ui.TextInput(
        label="Max over-cap bonus (credits)", placeholder="e.g. 15",
        required=True, max_length=6,
    )

    def __init__(self, cog: "Nessy", guild: discord.Guild, parent: "NessyAdminView"):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.parent = parent

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cap = int(self.cap.value)
            lo = int(self.bonus_min.value)
            hi = int(self.bonus_max.value)
            if cap < 1 or cap > 100 or lo < 0 or hi < 0:
                raise ValueError
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "Cap must be 1–100, bonus values must be ≥ 0.", ephemeral=True
            )
            return
        if lo > hi:
            lo, hi = hi, lo
        conf = self.cog.config.guild(self.guild)
        await conf.streak_cap.set(cap)
        await conf.streak_bonus_min.set(lo)
        await conf.streak_bonus_max.set(hi)
        await interaction.response.edit_message(
            embed=await self.parent.build_embed(), view=self.parent
        )


# ---------------------------------------------------------------------------
# Admin menu
# ---------------------------------------------------------------------------

class NessyAdminView(discord.ui.View):
    def __init__(
        self,
        cog: "Nessy",
        guild: discord.Guild,
        excluded: Optional[list[int]] = None,
    ):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        # Track the currently excluded channel IDs so the select can pre-check them
        self._excluded: list[int] = list(excluded) if excluded else []
        self._build()

    async def build_embed(self) -> discord.Embed:
        conf = self.cog.config.guild(self.guild)
        enabled = await conf.enabled()
        role_id = await conf.reward_role_id()
        min_c = await conf.reward_credits_min()
        max_c = await conf.reward_credits_max()
        lifetime = await conf.lifetime_seconds()
        emoji = await conf.nessy_emoji()
        threshold = await conf.catches_required()
        delete_delay = await conf.announcement_delete_delay()
        boss_chance = await conf.boss_chance()
        boss_min = await conf.boss_reward_credits_min()
        boss_max = await conf.boss_reward_credits_max()
        streak_cap = await conf.streak_cap()
        bonus_min = await conf.streak_bonus_min()
        bonus_max = await conf.streak_bonus_max()

        role = self.guild.get_role(role_id) if role_id else None

        embed = discord.Embed(
            title="🌊 Nessy Configuration",
            description="Use the controls below to configure Nessy for this server.",
            color=0x1ABC9C,
        )
        embed.add_field(name="Enabled", value="✅ Yes" if enabled else "❌ No")
        embed.add_field(name="Reward role", value=role.mention if role else "None")
        embed.add_field(name="Catches for role", value=str(threshold))
        embed.add_field(name="Credits range", value=f"{min_c} – {max_c}")
        embed.add_field(name="Lifetime", value=f"{lifetime}s")
        embed.add_field(name="Emoji", value=emoji)
        embed.add_field(name="Announcement deletes in", value=f"{delete_delay}s")
        embed.add_field(
            name="Streak",
            value=f"×2…×{streak_cap} (beyond: +{bonus_min}–{bonus_max} bonus)",
        )
        embed.add_field(name="Boss chance", value=f"{boss_chance}%")
        embed.add_field(
            name="Boss credits", value=f"{boss_min} – {boss_max} per winner"
        )

        if self._excluded:
            names = []
            for cid in self._excluded[:10]:
                ch = self.guild.get_channel(cid)
                names.append(ch.mention if ch else f"<#{cid}>")
            value = ", ".join(names)
            if len(self._excluded) > 10:
                value += f" (+{len(self._excluded) - 10} more)"
        else:
            value = "None"
        embed.add_field(name="Excluded channels", value=value, inline=False)
        return embed

    def _build(self):
        toggle = discord.ui.Button(label="Toggle Enabled", style=discord.ButtonStyle.primary)
        toggle.callback = self._toggle
        self.add_item(toggle)

        role_id_btn = discord.ui.Button(label="Set Role by ID", style=discord.ButtonStyle.primary)
        role_id_btn.callback = self._open_role_id_modal
        self.add_item(role_id_btn)

        threshold_btn = discord.ui.Button(label="Set Catches Needed", style=discord.ButtonStyle.primary)
        threshold_btn.callback = self._open_threshold
        self.add_item(threshold_btn)

        credits_btn = discord.ui.Button(label="Set Credits Range", style=discord.ButtonStyle.primary)
        credits_btn.callback = self._open_credits
        self.add_item(credits_btn)

        streak_btn = discord.ui.Button(label="Set Streak Settings", style=discord.ButtonStyle.primary)
        streak_btn.callback = self._open_streak
        self.add_item(streak_btn)

        lifetime_btn = discord.ui.Button(label="Set Lifetime", style=discord.ButtonStyle.primary)
        lifetime_btn.callback = self._open_lifetime
        self.add_item(lifetime_btn)

        emoji_btn = discord.ui.Button(label="Set Emoji", style=discord.ButtonStyle.primary)
        emoji_btn.callback = self._open_emoji
        self.add_item(emoji_btn)

        delete_btn = discord.ui.Button(label="Set Delete Delay", style=discord.ButtonStyle.primary)
        delete_btn.callback = self._open_delete_delay
        self.add_item(delete_btn)

        boss_btn = discord.ui.Button(label="Set Boss Settings", style=discord.ButtonStyle.primary)
        boss_btn.callback = self._open_boss
        self.add_item(boss_btn)

        spawn_btn = discord.ui.Button(label="Spawn Now", style=discord.ButtonStyle.success)
        spawn_btn.callback = self._spawn_now
        self.add_item(spawn_btn)

        boss_spawn_btn = discord.ui.Button(
            label="Spawn Boss Now", style=discord.ButtonStyle.danger
        )
        boss_spawn_btn.callback = self._spawn_boss_now
        self.add_item(boss_spawn_btn)

        reset_btn = discord.ui.Button(label="Reset", style=discord.ButtonStyle.danger)
        reset_btn.callback = self._reset
        self.add_item(reset_btn)

        # Pre-select currently excluded channels so they persist when adding new ones
        defaults = [
            discord.Object(id=cid)
            for cid in self._excluded
            if self.guild.get_channel(cid) is not None
        ]

        select: discord.ui.ChannelSelect = discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            placeholder="Exclude channels Nessy should NOT appear in",
            min_values=0,
            max_values=25,
            default_values=defaults,
        )
        select.callback = self._on_channel_select
        self.add_item(select)

    # ---- callbacks ----

    async def _toggle(self, interaction: discord.Interaction):
        conf = self.cog.config.guild(self.guild)
        current = await conf.enabled()
        await conf.enabled.set(not current)
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    async def _open_role_id_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RoleIdModal(self.cog, self.guild, self))

    async def _open_threshold(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ThresholdModal(self.cog, self.guild, self))

    async def _open_credits(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreditsModal(self.cog, self.guild, self))

    async def _open_streak(self, interaction: discord.Interaction):
        await interaction.response.send_modal(StreakSettingsModal(self.cog, self.guild, self))

    async def _open_lifetime(self, interaction: discord.Interaction):
        await interaction.response.send_modal(LifetimeModal(self.cog, self.guild, self))

    async def _open_emoji(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EmojiModal(self.cog, self.guild, self))

    async def _open_delete_delay(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DeleteDelayModal(self.cog, self.guild, self))

    async def _open_boss(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BossSettingsModal(self.cog, self.guild, self))

    async def _spawn_now(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ok = await self.cog.spawn_nessy(self.guild, force_boss=False)
        if ok:
            await interaction.followup.send("Nessy has been released!", ephemeral=True)
        else:
            await interaction.followup.send(
                "Could not spawn Nessy — no eligible channels.", ephemeral=True
            )

    async def _spawn_boss_now(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ok = await self.cog.spawn_nessy(self.guild, force_boss=True)
        if ok:
            await interaction.followup.send("Boss Nessy has appeared!", ephemeral=True)
        else:
            await interaction.followup.send(
                "Could not spawn Boss Nessy — no eligible channels.", ephemeral=True
            )

    async def _reset(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ Reset Nessy configuration?",
            description=(
                "You are about to reset all Nessy settings for this server "
                "back to their defaults.\n\n"
                "This is the **first** confirmation. You will be asked once more.\n\n"
                "Click **Continue** to proceed, or **Cancel** to abort."
            ),
            color=0xF1C40F,
        )
        await interaction.response.send_message(
            embed=embed,
            view=ResetFirstConfirmView(self.cog, self.guild, self),
            ephemeral=True,
        )

    async def _on_channel_select(self, interaction: discord.Interaction):
        select = next(c for c in self.children if isinstance(c, discord.ui.ChannelSelect))
        excluded = [c.id for c in select.values]
        await self.cog.config.guild(self.guild).excluded_channels.set(excluded)

        # Rebuild the view so the select's default_values reflect the new state
        new_view = NessyAdminView(self.cog, self.guild, excluded)
        await interaction.response.edit_message(
            embed=await new_view.build_embed(), view=new_view
        )


# ---------------------------------------------------------------------------
# The Cog
# ---------------------------------------------------------------------------

class Nessy(commands.Cog):
    """Random Nessy spawns with a first-to-click reward system."""

    def __init__(self, bot):
        self.bot = bot
        self.log = getattr(bot, "log", None) or __import__("logging").getLogger("red.nessy")
        self.config = Config.get_conf(
            self, identifier=0x4E6573737900, force_registration=True
        )
        self.config.register_guild(
            enabled=True,
            excluded_channels=[],
            reward_role_id=None,
            reward_credits_min=1,
            reward_credits_max=100,
            nessy_emoji="🦕",
            lifetime_seconds=3,
            catches_required=5,
            announcement_delete_delay=10,
            last_catcher_id=0,
            daily_first_date="",
            boss_chance=1,
            boss_reward_credits_min=100,
            boss_reward_credits_max=500,
            streak_cap=3,
            streak_bonus_min=5,
            streak_bonus_max=15,
        )
        self.config.register_member(catches=0, streak=0)

        self.next_spawn: dict[int, float] = {}
        self._background_tasks: set[asyncio.Task] = set()

        self.spawn_loop.start()

    def cog_unload(self):
        self.spawn_loop.cancel()
        for task in list(self._background_tasks):
            task.cancel()

    # ---------- task helper ----------

    def _spawn_task(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def _auto_delete(self, message: discord.Message, delay: int):
        try:
            await asyncio.sleep(delay)
            await message.delete()
        except discord.HTTPException:
            pass
        except asyncio.CancelledError:
            raise

    # ---------- random timing ----------

    @staticmethod
    def _first_delay() -> float:
        return random.uniform(2 * 60, 5 * 60)

    @staticmethod
    def _random_delay() -> float:
        return random.uniform(15 * 60, 3 * 60 * 60)

    # ---------- spawning ----------

    @tasks.loop(seconds=15)
    async def spawn_loop(self):
        now = time.time()
        for guild in list(self.bot.guilds):
            try:
                conf = self.config.guild(guild)
                if not await conf.enabled():
                    continue

                nxt = self.next_spawn.get(guild.id)
                if nxt is None:
                    self.next_spawn[guild.id] = now + self._first_delay()
                    self.log.info(
                        "Nessy: first spawn for guild %s in ~%.0f min",
                        guild.id, (self.next_spawn[guild.id] - now) / 60,
                    )
                    continue

                if now >= nxt:
                    self.next_spawn[guild.id] = now + self._random_delay()
                    self.log.info(
                        "Nessy: spawning in guild %s (next in ~%.0f min)",
                        guild.id, (self.next_spawn[guild.id] - now) / 60,
                    )
                    await self.spawn_nessy(guild)
            except Exception as exc:
                self.log.exception("Nessy: spawn loop error for guild %s: %s", guild.id, exc)

    @spawn_loop.before_loop
    async def _before_spawn(self):
        await self.bot.wait_until_ready()

    async def spawn_nessy(self, guild: discord.Guild, force_boss: bool = False) -> bool:
        conf = self.config.guild(guild)
        excluded = set(await conf.excluded_channels())

        candidates = []
        for channel in guild.text_channels:
            if channel.id in excluded:
                continue
            perms = channel.permissions_for(guild.me)
            if perms.view_channel and perms.send_messages and perms.manage_messages:
                candidates.append(channel)

        if not candidates:
            self.log.warning(
                "Nessy: no eligible channel in guild %s", guild.id
            )
            return False

        channel = random.choice(candidates)
        emoji = await conf.nessy_emoji()
        lifetime = int(await conf.lifetime_seconds())

        boss_chance = int(await conf.boss_chance())
        is_boss = force_boss or (boss_chance > 0 and random.randint(1, 100) <= boss_chance)

        if is_boss:
            boss_lifetime = 6
            view = NessyBossView(self, emoji, guild.id, lifetime=boss_lifetime)
            text = (
                f"⚔️ {emoji} **BOSS NESSY!** "
                f"{boss_lifetime}s — 3 users, 3 weapons!"
            )
            try:
                message = await channel.send(text, view=view)
            except discord.HTTPException as exc:
                self.log.warning("Nessy boss: failed to spawn: %s", exc)
                return False
            view.message = message
            self.log.info("Nessy BOSS spawned in #%s (guild %s)", channel.name, guild.id)
            return True

        view = NessyView(self, emoji, guild.id)
        try:
            message = await channel.send(emoji, view=view)
        except discord.HTTPException as exc:
            self.log.warning("Nessy: failed to spawn in #%s: %s", channel, exc)
            return False

        self.log.info("Nessy: spawned in #%s (guild %s)", channel.name, guild.id)
        self._spawn_task(self._expire(message, view, lifetime))
        return True

    async def _expire(self, message: discord.Message, view: NessyView, delay: int):
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        if view.claimed:
            return
        view.claimed = True
        try:
            await message.delete()
        except discord.HTTPException:
            try:
                await message.edit(view=None)
            except discord.HTTPException:
                pass

    # ---------- boss completion ----------

    async def _complete_boss(
        self,
        view: NessyBossView,
        guild: Optional[discord.Guild],
        channel: Optional[discord.abc.Messageable],
    ):
        if guild is None or channel is None:
            return
        conf = self.config.guild(guild)
        b_min = int(await conf.boss_reward_credits_min())
        b_max = int(await conf.boss_reward_credits_max())
        if b_min > b_max:
            b_min, b_max = b_max, b_min
        role_id = await conf.reward_role_id()
        threshold = int(await conf.catches_required())
        delete_delay = int(await conf.announcement_delete_delay())

        if view.message is not None:
            try:
                await view.message.delete()
            except discord.HTTPException:
                pass

        await conf.last_catcher_id.set(0)

        winners = list(view.participants.values())

        rewards: dict[int, int] = {}

        for member in winners:
            member_conf = self.config.member(member)
            catches = await member_conf.catches()
            catches += 1
            await member_conf.catches.set(catches)
            await member_conf.streak.set(0)

            amount = random.randint(b_min, b_max) if b_max > 0 else 0
            rewards[member.id] = amount

            if amount > 0:
                try:
                    await bank.deposit_credits(member, amount)
                except Exception as exc:
                    self.log.warning(
                        "Nessy: boss credits failed for %s: %s", member, exc
                    )

            if role_id and catches >= threshold:
                role = guild.get_role(role_id)
                if role is not None and role not in member.roles:
                    try:
                        await member.add_roles(role, reason="Boss Nessy defeated!")
                    except discord.Forbidden:
                        pass

        currency = await bank.get_currency_name(guild)
        lines = ["⚔️ **BOSS NESSY DEFEATED!**"]
        for m in winners:
            lines.append(f"• {m.mention} won **{rewards[m.id]}** {currency}")

        try:
            msg = await channel.send("\n".join(lines))
            self._spawn_task(self._auto_delete(msg, delete_delay))
        except discord.HTTPException:
            pass

    # ---------- commands ----------

    @commands.group(name="nessy", invoke_without_command=True)
    @commands.guild_only()
    async def nessy_group(self, ctx: commands.Context):
        """Nessy administration commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @nessy_group.command(name="menu")
    @commands.admin_or_permissions(administrator=True)
    async def nessy_menu(self, ctx: commands.Context):
        """Open the interactive Nessy admin menu."""
        excluded = await self.config.guild(ctx.guild).excluded_channels()
        view = NessyAdminView(self, ctx.guild, excluded)
        await ctx.send(embed=await view.build_embed(), view=view)

    @nessy_group.command(name="spawn")
    @commands.admin_or_permissions(administrator=True)
    async def nessy_spawn(self, ctx: commands.Context):
        """Force a regular Nessy spawn for testing."""
        async with ctx.typing():
            ok = await self.spawn_nessy(ctx.guild, force_boss=False)
        if ok:
            await ctx.tick()
        else:
            await ctx.send("Could not spawn Nessy — no eligible channels.")

    @nessy_group.command(name="boss")
    @commands.admin_or_permissions(administrator=True)
    async def nessy_boss(self, ctx: commands.Context):
        """Force a Boss Nessy spawn for testing."""
        async with ctx.typing():
            ok = await self.spawn_nessy(ctx.guild, force_boss=True)
        if ok:
            await ctx.tick()
        else:
            await ctx.send("Could not spawn Boss Nessy — no eligible channels.")

    @nessy_group.command(name="role")
    @commands.admin_or_permissions(administrator=True)
    async def nessy_role(self, ctx: commands.Context, *, role: discord.Role):
        """Set the reward role by mention, name or ID."""
        await self.config.guild(ctx.guild).reward_role_id.set(role.id)
        await ctx.send(f"Reward role set to {role.mention}.")

    @nessy_group.command(name="when")
    @commands.admin_or_permissions(administrator=True)
    async def nessy_when(self, ctx: commands.Context):
        """Show when the next Nessy spawn is scheduled."""
        nxt = self.next_spawn.get(ctx.guild.id)
        if nxt is None:
            await ctx.send("Not scheduled yet — will be set within the next loop tick.")
            return
        remaining = max(0, int(nxt - time.time()))
        minutes = remaining // 60
        seconds = remaining % 60
        await ctx.send(
            f"Next Nessy spawn in **{minutes}m {seconds}s** (<t:{int(nxt)}:R>)."
        )

    @nessy_group.command(name="status")
    @commands.admin_or_permissions(administrator=True)
    async def nessy_status(self, ctx: commands.Context):
        """Show the Nessy status for this server."""
        conf = self.config.guild(ctx.guild)
        enabled = await conf.enabled()
        role_id = await conf.reward_role_id()
        min_c = await conf.reward_credits_min()
        max_c = await conf.reward_credits_max()
        lifetime = await conf.lifetime_seconds()
        excluded = await conf.excluded_channels()
        threshold = await conf.catches_required()
        delete_delay = await conf.announcement_delete_delay()
        boss_chance = await conf.boss_chance()
        boss_min = await conf.boss_reward_credits_min()
        boss_max = await conf.boss_reward_credits_max()
        streak_cap = await conf.streak_cap()
        bonus_min = await conf.streak_bonus_min()
        bonus_max = await conf.streak_bonus_max()
        role = ctx.guild.get_role(role_id) if role_id else None

        nxt = self.next_spawn.get(ctx.guild.id)
        next_str = f"<t:{int(nxt)}:R>" if nxt else "not scheduled yet"

        embed = discord.Embed(title="Nessy Status", color=0x2ECC71)
        embed.add_field(name="Enabled", value="Yes" if enabled else "No")
        embed.add_field(name="Next spawn", value=next_str)
        embed.add_field(name="Reward role", value=role.mention if role else "None")
        embed.add_field(name="Catches for role", value=str(threshold))
        embed.add_field(name="Credits range", value=f"{min_c} – {max_c}")
        embed.add_field(name="Excluded channels", value=str(len(excluded)))
        embed.add_field(name="Lifetime", value=f"{lifetime}s")
        embed.add_field(name="Announcement deletes in", value=f"{delete_delay}s")
        embed.add_field(
            name="Streak",
            value=f"×2…×{streak_cap} (beyond: +{bonus_min}–{bonus_max})",
        )
        embed.add_field(name="Boss chance", value=f"{boss_chance}%")
        embed.add_field(name="Boss credits", value=f"{boss_min} – {boss_max} per winner")
        await ctx.send(embed=embed)

    @nessy_group.command(name="catches")
    @commands.admin_or_permissions(administrator=True)
    async def nessy_catches(self, ctx: commands.Context, member: discord.Member):
        """Show how many times a member has caught Nessy and their streak."""
        member_conf = self.config.member(member)
        count = await member_conf.catches()
        streak = await member_conf.streak()
        threshold = await self.config.guild(ctx.guild).catches_required()
        await ctx.send(
            f"{member.mention}: **{count}** catch(es), current streak **{streak}**. "
            f"(Role at {threshold})"
        )

    @nessy_group.command(name="resetuser")
    @commands.admin_or_permissions(administrator=True)
    async def nessy_resetuser(self, ctx: commands.Context, member: discord.Member):
        """Reset a member's Nessy counter and streak."""
        await self.config.member(member).catches.set(0)
        await self.config.member(member).streak.set(0)
        await ctx.send(f"Reset {member.mention}'s Nessy data.")

    @nessy_group.command(name="resetall")
    @commands.admin_or_permissions(administrator=True)
    async def nessy_resetall(self, ctx: commands.Context):
        """Reset the Nessy counters and streaks for every member in this guild."""
        for member in ctx.guild.members:
            await self.config.member(member).catches.set(0)
            await self.config.member(member).streak.set(0)
        await self.config.guild(ctx.guild).last_catcher_id.set(0)
        await ctx.send("Reset all Nessy counters in this guild.")
