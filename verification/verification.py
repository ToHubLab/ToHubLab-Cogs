"""Verification Cog — main entry point.

This file only contains the Cog class itself: commands, listeners,
and the orchestration logic that calls into the helper modules.
"""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord.ext import tasks
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

from .helpers import (
    # constants
    DEFAULT_VERIFICATION_EMOJI,
    SETUP_AUTO_DELETE_SECONDS,
    SYNC_INTERVAL_MINUTES,
    VERIFIED_PAGE_SIZE,
    CANCEL_AUTO_DELETE_SECONDS,
    DEFAULT_SECURITY_QUESTIONS,
    CREDIT_LINE,
    CREDIT_NAME,
    CREDIT_URL,
    # utils
    normalize_emoji,
    generate_challenge,
    # embeds
    status_embed,
    not_setup_embed,
    verification_embed,
    # data
    DataManager,
    # modals
    ChallengeModal,
    SecurityCheckModal,
    # views
    VerifyView,
    ChannelChallengeStartView,
    SecurityCheckStartView,
    VerifiedPaginatorView,
    # setup
    SetupWizard,
    NotSetupView,
    # menu
    VerificationMenuView,
)


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

        # Persistent view
        self.verify_view = VerifyView(self)

        # Data manager
        self.data = DataManager(cog_data_path(self))

    # ─── Convenience properties (used by views) ───
    @property
    def emoji_options(self):
        return self.data.emoji_options

    @property
    def text_challenges(self):
        return self.data.text_challenges

    @property
    def security_questions(self):
        return self.data.security_questions

    @property
    def config_file(self):
        return self.data.config_file

    @property
    def verified_file(self):
        return self.data.verified_file

    # ─── Cog lifecycle ───

    async def cog_load(self):
        self.data.ensure_dir()
        if not self.data.config_file.exists():
            self.data.write_defaults()
        self.data.read()

        # Register persistent view for button clicks across restarts
        try:
            self.bot.add_view(self.verify_view)
        except Exception:
            pass

        if not self._sync_loop.is_running():
            self._sync_loop.start()

    async def cog_unload(self):
        self.verify_view.stop()
        if self._sync_loop.is_running():
            self._sync_loop.cancel()

    # ─── Data helpers ───

    async def _read_data(self):
        self.data.read()

    async def _write_verified_users_file(self, guild: discord.Guild):
        conf = self.config.guild(guild)
        users = await conf.verified_users()
        self.data.write_verified_users(guild.id, users)

    # ─── Challenge generator (delegates to helper) ───

    def _generate_challenge(self) -> tuple[str, str, bool]:
        return generate_challenge(self.data.text_challenges)

    # ─── General helpers ───

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
            if normalize_emoji(reaction.emoji) == normalize_emoji(emoji):
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
        embed = status_embed(
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
                f"Loaded **{len(self.data.emoji_options)}** emoji options, "
                f"**{len(self.data.text_challenges)}** text challenges and "
                f"**{len(self.data.security_questions)}** security questions from "
                f"`{self.data.config_file.name}`." + CREDIT_LINE
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
                await ctx.send("ℹ️ No verified users stored for this server.", ephemeral=True)
            except TypeError:
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
                    f"**Total:** {total}\n\n" + "\n".join(lines) + CREDIT_LINE
                ),
                color=discord.Color.green(),
            )
            embed.set_footer(
                text=f"File: {self.data.verified_file.name} • "
                     f"Only you can see this • Page {page_num}/{total_pages}"
            )
            pages.append(embed)

        view = VerifiedPaginatorView(pages) if len(pages) > 1 else None

        try:
            await ctx.send(embed=pages[0], view=view, ephemeral=True)
        except TypeError:
            msg = await ctx.send(embed=pages[0], view=view)
            asyncio.create_task(self._delete_message_after(msg, 120))

    @commands.command(name="verifymenu")
    @commands.admin_or_permissions(manage_guild=True)
    async def verifymenu(self, ctx: commands.Context):
        """Opens the interactive verification menu."""
        if not await self._is_setup(ctx.guild):
            await ctx.send(embed=not_setup_embed(), view=NotSetupView(self, ctx))
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
        if normalize_emoji(payload.emoji) != normalize_emoji(stored_emoji):
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            return

        role_id = await conf.verification_role_id()
        verified_users = await conf.verified_users()
        has_role = self._user_has_verification_role(guild, member, role_id)

        if member.id in verified_users and has_role:
            return

        if member.id in verified_users and not has_role:
            await self._post_security_check_in_channel(guild, member)
            return

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
            pool = self.data.security_questions or [(q, a) for q, a in DEFAULT_SECURITY_QUESTIONS]
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