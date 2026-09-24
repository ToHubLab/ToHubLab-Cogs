import asyncio
import json
import logging
import random
import time
from pathlib import Path
from typing import Optional, List, Dict

import discord
from discord.ext import tasks
from redbot.core import commands, Config, bank, checks

log = logging.getLogger("red.counting")

LOCALES_DIR = Path(__file__).parent / "locales"
MAIN_LANGUAGE = "en"


class Counting(commands.Cog):
    """ToHubLab Counting Game — a server-wide counting game with saves system."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7845123690)
        self.config.register_global(version="1.1.0")

        default_guild = {
            "language": MAIN_LANGUAGE,
            "counting_channel": None,
            "current_count": 0,
            "saves": 3,
            "save_price": 1000,
            "last_counter": None,
            "total_counts": 0,
            "total_mistakes": 0,
            "current_streak": 0,
            "best_streak": 0,
            "leaderboard": {},
            "buysave_enabled": True,
        }
        self.config.register_guild(**default_guild)
        self.config.register_member(
            counts=0,
            mistakes=0,
            achievements=[],
            last_count_time=0,
        )

        self.locales: Dict[str, dict] = {}
        self._load_locales()
        self._active_menus: Dict[tuple, dict] = {}

    # ── Response helper ───────────────────────────────────────

    async def respond(self, ctx, content=None, embed=None,
                      ephemeral=True, view=None, **kwargs):
        """
        Smart response handler:
        - Slash → true ephemeral
        - Prefix → try DM; if that fails, send in channel + auto-delete
        """
        # ── Slash: echtes Ephemeral ──────────────────────
        if ctx.interaction is not None:
            try:
                if not ctx.interaction.response.is_done():
                    await ctx.interaction.response.send_message(
                        content=content, embed=embed, view=view,
                        ephemeral=ephemeral,
                    )
                else:
                    await ctx.interaction.followup.send(
                        content=content, embed=embed, view=view,
                        ephemeral=ephemeral,
                    )
                return
            except discord.HTTPException as e:
                log.error(f"[Counting] interaction respond failed: {e}")
                # fall through

        # ── Prefix: Nutzer-Nachricht löschen (falls möglich) ──
        try:
            if ctx.guild is not None and not ctx.channel.permissions_for(
                    ctx.guild.me).manage_messages:
                pass
            else:
                await ctx.message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

        # ── Prefix + ephemeral gewünscht → DM-Versuch ─────
        if ephemeral:
            try:
                dm_kwargs = {}
                if content is not None:
                    dm_kwargs["content"] = content
                if embed is not None:
                    dm_kwargs["embed"] = embed
                if dm_kwargs:
                    await ctx.author.send(**dm_kwargs)
                # Optional: kurze Bestätigung im Channel
                try:
                    hint = await ctx.send(
                        f"📬 {ctx.author.mention}, ich habe dir eine DM geschickt.",
                        delete_after=8,
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass
                return
            except (discord.Forbidden, discord.HTTPException):
                # DMs disabled → fall back to channel + auto-delete
                pass

        # ── Fallback: normale Antwort + Auto-Delete ──────
        try:
            await ctx.send(
                content=content, embed=embed, view=view,
                delete_after=20,
            )
        except discord.HTTPException as e:
            log.error(f"[Counting] ctx.send failed: {e}")

    # ── Locales ───────────────────────────────────────────────

    def _load_locales(self):
        self.locales = {}
        if not LOCALES_DIR.is_dir():
            log.error(f"Locales folder missing: {LOCALES_DIR}")
            return
        for f in sorted(LOCALES_DIR.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                code = data.get("language_code") or f.stem
                self.locales[code] = data
                log.info(f"Loaded locale '{code}' from {f.name}")
            except Exception as e:
                log.error(f"Failed to load locale {f.name}: {e}")
        if MAIN_LANGUAGE not in self.locales:
            log.error(f"Main language '{MAIN_LANGUAGE}' not found!")

    def available_languages(self) -> List[str]:
        return list(self.locales.keys())

    def language_name(self, code: str) -> str:
        entry = self.locales.get(code)
        if entry:
            return entry.get("language_name", code)
        return code

    def tr_sync(self, lang, key, **kw):
        if lang not in self.locales:
            lang = MAIN_LANGUAGE
        entry = self.locales.get(lang, {})
        translations = entry.get("translations", {})
        text = translations.get(key)
        if text is None and lang != MAIN_LANGUAGE:
            main = self.locales.get(MAIN_LANGUAGE, {}).get("translations", {})
            text = main.get(key)
        if text is None:
            text = key
        try:
            return text.format(**kw) if kw else text
        except Exception:
            return text

    async def _(self, guild, key, **kw):
        if guild is None:
            return self.tr_sync(MAIN_LANGUAGE, key, **kw)
        lang = await self.config.guild(guild).language()
        return self.tr_sync(lang, key, **kw)

    def get_achievements(self, lang: str) -> dict:
        if lang not in self.locales:
            lang = MAIN_LANGUAGE
        ach = self.locales.get(lang, {}).get("achievements")
        if not ach:
            ach = self.locales.get(MAIN_LANGUAGE, {}).get("achievements", {})
        return ach or {}

    # ── Channel check ─────────────────────────────────────────

    async def is_counting_channel(self, guild, channel) -> bool:
        ch_id = await self.config.guild(guild).counting_channel()
        return ch_id == channel.id

    # ── Achievements ──────────────────────────────────────────

    async def check_counting_achievements(self, member, channel=None):
        guild = member.guild
        lang = await self.config.guild(guild).language()
        if lang not in self.locales:
            lang = MAIN_LANGUAGE

        unlocked = set(await self.config.member(member).achievements())
        counts = await self.config.member(member).counts()
        streak = await self.config.guild(guild).current_streak()
        ach_dict = self.get_achievements(lang)

        new_ones = []
        def check(key, cond):
            if key not in unlocked and cond:
                unlocked.add(key)
                new_ones.append(key)

        check("first_count", counts >= 1)
        check("count_100", counts >= 100)
        check("count_1000", counts >= 1000)
        check("streak_10", streak >= 10)
        check("streak_50", streak >= 50)

        if new_ones:
            await self.config.member(member).achievements.set(list(unlocked))
            target = channel or guild.system_channel
            if target is None and guild.text_channels:
                target = guild.text_channels[0]
            for key in new_ones:
                a = ach_dict.get(key, {})
                if target:
                    try:
                        await target.send(
                            f"{member.mention} 🏆 **{a.get('name', key)}** — *{a.get('desc','')}*"
                        )
                    except Exception:
                        pass

    # ── Counting logic ────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not isinstance(message.author, discord.Member):
            return

        if not hasattr(self, "_processed_ids"):
            self._processed_ids = set()
        if message.id in self._processed_ids:
            return
        self._processed_ids.add(message.id)
        if len(self._processed_ids) > 500:
            self._processed_ids = set(list(self._processed_ids)[-250:])

        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return
        if not await self.is_counting_channel(message.guild, message.channel):
            return

        content = message.content.strip()
        if not content.isdigit():
            return

        number = int(content)
        conf = self.config.guild(message.guild)
        expected = await conf.current_count() + 1

        last_counter = await conf.last_counter()
        if last_counter == message.author.id:
            await message.channel.send(
                await self._(message.guild, "cant_count_twice", mention=message.author.mention)
            )
            return

        if number == expected:
            await conf.current_count.set(expected)
            await conf.last_counter.set(message.author.id)

            total = await conf.total_counts()
            await conf.total_counts.set(total + 1)
            streak = await conf.current_streak()
            new_streak = streak + 1
            await conf.current_streak.set(new_streak)
            best = await conf.best_streak()
            if new_streak > best:
                await conf.best_streak.set(new_streak)

            m_counts = await self.config.member(message.author).counts()
            await self.config.member(message.author).counts.set(m_counts + 1)
            await self.config.member(message.author).last_count_time.set(time.time())

            lb = await conf.leaderboard()
            uid = str(message.author.id)
            lb[uid] = lb.get(uid, 0) + 1
            await conf.leaderboard.set(lb)

            try:
                await message.add_reaction("✅")
            except Exception:
                pass

            await self.check_counting_achievements(message.author, channel=message.channel)

        else:
            saves = await conf.saves()
            mistakes = await conf.total_mistakes()
            await conf.total_mistakes.set(mistakes + 1)
            await conf.current_streak.set(0)

            m_mistakes = await self.config.member(message.author).mistakes()
            await self.config.member(message.author).mistakes.set(m_mistakes + 1)

            if saves > 1:
                new_saves = saves - 1
                await conf.saves.set(new_saves)
                await message.channel.send(
                    await self._(message.guild, "wrong_number", saves=new_saves)
                )
            else:
                reset_saves = 3
                await conf.current_count.set(0)
                await conf.saves.set(reset_saves)
                await conf.last_counter.set(None)
                await conf.current_streak.set(0)
                await message.channel.send(
                    await self._(message.guild, "no_saves_left", saves=reset_saves)
                )

    # ═════════════════════════════════════════════════════════
    #  USER COMMANDS
    # ═════════════════════════════════════════════════════════

    @commands.hybrid_command(name="countstatus", aliases=["cstatus"])
    @commands.guild_only()
    async def countstatus(self, ctx):
        """Show the current counting status."""
        g = ctx.guild
        conf = self.config.guild(g)
        ch_id = await conf.counting_channel()
        ch = g.get_channel(ch_id) if ch_id else None
        last_id = await conf.last_counter()
        last_member = g.get_member(last_id) if last_id else None

        embed = discord.Embed(
            title=await self._(g, "status_title"),
            color=discord.Color.green(),
        )
        embed.add_field(name=await self._(g, "status_count"),
                        value=f"`{await conf.current_count()}`", inline=True)
        embed.add_field(name=await self._(g, "status_saves"),
                        value=f"`{await conf.saves()}`", inline=True)
        embed.add_field(name=await self._(g, "status_price"),
                        value=f"`{await conf.save_price():,}`", inline=True)
        embed.add_field(name=await self._(g, "status_channel"),
                        value=ch.mention if ch else await self._(g, "status_not_set"),
                        inline=False)
        embed.add_field(name=await self._(g, "status_last"),
                        value=last_member.mention if last_member else "—", inline=True)
        embed.add_field(name=await self._(g, "status_total"),
                        value=f"`{await conf.total_counts():,}`", inline=True)
        embed.add_field(name=await self._(g, "status_mistakes"),
                        value=f"`{await conf.total_mistakes():,}`", inline=True)
        await self.respond(ctx, embed=embed, ephemeral=True)

    @commands.hybrid_command(name="countleaderboard", aliases=["clb", "counttop"])
    @commands.guild_only()
    async def countleaderboard(self, ctx):
        """Show the counting leaderboard."""
        g = ctx.guild
        lb = await self.config.guild(g).leaderboard()
        if not lb:
            await self.respond(ctx, await self._(g, "leaderboard_empty"),
                               ephemeral=True)
            return

        sorted_lb = sorted(lb.items(), key=lambda x: x[1], reverse=True)[:20]
        embed = discord.Embed(
            title=await self._(g, "leaderboard_title"),
            color=discord.Color.gold(),
        )
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, count) in enumerate(sorted_lb, start=1):
            member = g.get_member(int(uid))
            name = member.mention if member else f"<@{uid}>"
            prefix = medals[i - 1] if i <= 3 else f"**#{i}**"
            lines.append(f"{prefix} {name} — {count:,} counts")
        embed.description = "\n".join(lines)
        await self.respond(ctx, embed=embed, ephemeral=True)

    @commands.hybrid_command(name="buysave", aliases=["countbuysave"])
    @commands.guild_only()
    async def buysave(self, ctx):
        """Buy an extra save with your coins."""
        g = ctx.guild
        conf = self.config.guild(g)
        if not await conf.buysave_enabled():
            await self.respond(ctx, await self._(g, "buysave_disabled"),
                               ephemeral=True)
            return

        price = await conf.save_price()
        balance = await bank.get_balance(ctx.author)
        if balance < price:
            await self.respond(ctx,
                               await self._(g, "buysave_insufficient",
                                            price=price, balance=balance,
                                            currency=await bank.get_currency_name(g)),
                               ephemeral=True)
            return

        await bank.withdraw_credits(ctx.author, price)
        saves = await conf.saves()
        new_saves = saves + 1
        await conf.saves.set(new_saves)
        await self.respond(ctx,
                           await self._(g, "buysave_success",
                                        price=price,
                                        currency=await bank.get_currency_name(g),
                                        total=new_saves),
                           ephemeral=True)

    @commands.hybrid_command(name="tohublabcountinfo",
                             aliases=["thlcinfo", "tohubLabcountinfo"])
    @commands.guild_only()
    async def tohub_lab_count_info(self, ctx):
        """Show info about the ToHubLab Counting cog."""
        g = ctx.guild if ctx.guild else None
        lang = (await self.config.guild(g).language()) if g else MAIN_LANGUAGE
        embed = discord.Embed(
            title="ToHubLab Counting",
            description="A server-wide counting game with saves system and leaderboard.",
            color=discord.Color.purple(),
        )
        embed.add_field(name="Author", value="ToHubLab", inline=True)
        embed.add_field(name="Version", value=await self.config.version(), inline=True)
        embed.add_field(name="Language", value=self.language_name(lang), inline=True)
        langs = ", ".join(f"`{c}`" for c in self.available_languages())
        embed.add_field(name="Available languages", value=langs or "—", inline=False)
        embed.add_field(
            name="User commands",
            value="`.countstatus`, `.countleaderboard`, `.buysave`",
            inline=False,
        )
        embed.add_field(
            name="Admin",
            value="`.countset` → interactive setup menu",
            inline=False,
        )
        await self.respond(ctx, embed=embed, ephemeral=True)

    # ═════════════════════════════════════════════════════════
    #  ADMIN: SETUP MENU
    # ═════════════════════════════════════════════════════════

    @commands.group(name="countset", aliases=["countingset"], invoke_without_command=True)
    @checks.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    async def countset(self, ctx):
        """Open the interactive counting setup menu."""
        if ctx.invoked_subcommand is None:
            await self.render_main_menu(None, ctx, initial=True)

    async def build_main_embed(self, guild, lang=None):
        if lang is None:
            lang = await self.config.guild(guild).language()
        conf = self.config.guild(guild)
        t = lambda k, **kw: self.tr_sync(lang, k, **kw)

        ch_id = await conf.counting_channel()
        ch = guild.get_channel(ch_id) if ch_id else None
        last_id = await conf.last_counter()
        last_member = guild.get_member(last_id) if last_id else None

        embed = discord.Embed(
            title=t("menu_title"),
            description=t("menu_desc"),
            color=discord.Color.blurple(),
        )
        embed.add_field(name=f"🌐 {t('ov_language')}",
                        value=self.language_name(await conf.language()), inline=True)
        embed.add_field(name=f"📺 {t('ov_channel')}",
                        value=ch.mention if ch else t("status_not_set"), inline=True)
        embed.add_field(name=f"🔢 {t('ov_current_count')}",
                        value=f"`{await conf.current_count()}`", inline=True)
        embed.add_field(name=f"💾 {t('ov_saves')}",
                        value=f"`{await conf.saves()}`", inline=True)
        embed.add_field(name=f"💰 {t('ov_price')}",
                        value=f"`{await conf.save_price():,}`", inline=True)
        embed.add_field(name=f"👤 {t('ov_last_counter')}",
                        value=last_member.mention if last_member else "—", inline=True)
        embed.add_field(name=f"📊 {t('ov_total_counts')}",
                        value=f"`{await conf.total_counts():,}`", inline=True)
        embed.add_field(name=f"❌ {t('ov_total_mistakes')}",
                        value=f"`{await conf.total_mistakes():,}`", inline=True)
        return embed

    def build_category_view(self, ctx, category, lang):
        view = discord.ui.View(timeout=600)
        view.add_item(CategorySelect(self, ctx, lang=lang, current=category))
        view.add_item(BackButton(self, ctx, lang=lang))
        if category in ("language", "channel", "saves", "price"):
            view.add_item(EditButton(self, ctx, category, lang=lang))
        if category == "reset":
            view.add_item(ResetConfirmButton(self, ctx, lang=lang))
        return view

    async def render_main_menu(self, interaction, ctx, initial=False, lang=None):
        if lang is None:
            lang = await self.config.guild(ctx.guild).language()
        if lang not in self.locales:
            lang = MAIN_LANGUAGE

        embed = await self.build_main_embed(ctx.guild, lang)
        view = SetupMainView(self, ctx, lang=lang)

        if initial:
            msg = await ctx.send(embed=embed, view=view)
            self._active_menus[(ctx.author.id, ctx.guild.id)] = {
                "message": msg, "ctx": ctx, "category": None,
            }
        else:
            await interaction.response.edit_message(embed=embed, view=view)
            self._active_menus[(ctx.author.id, ctx.guild.id)] = {
                "message": interaction.message, "ctx": ctx, "category": None,
            }

    async def render_category(self, interaction, ctx, category, followup=False, lang=None):
        if lang is None:
            lang = await self.config.guild(ctx.guild).language()
        if lang not in self.locales:
            lang = MAIN_LANGUAGE

        if category is None:
            embed = await self.build_main_embed(ctx.guild, lang)
            view = SetupMainView(self, ctx, lang=lang)
            if followup:
                await interaction.message.edit(embed=embed, view=view)
            else:
                await interaction.response.edit_message(embed=embed, view=view)
            return

        embed = await self.build_category_embed(ctx.guild, category, lang)
        view = self.build_category_view(ctx, category, lang)

        if followup:
            await interaction.message.edit(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)

        entry = self._active_menus.get((ctx.author.id, ctx.guild.id))
        if entry:
            entry["category"] = category
        else:
            self._active_menus[(ctx.author.id, ctx.guild.id)] = {
                "message": interaction.message, "ctx": ctx, "category": category,
            }

    async def build_category_embed(self, guild, category, lang):
        conf = self.config.guild(guild)
        t = lambda k, **kw: self.tr_sync(lang, k, **kw)
        embed = discord.Embed(title=t(f"menu_{category}"), color=discord.Color.blurple())

        if category == "language":
            embed.add_field(name=t("ov_language"),
                            value=self.language_name(await conf.language()), inline=True)
            langs = ", ".join(f"`{c}`" for c in self.available_languages())
            embed.add_field(name="Available", value=langs or "—", inline=False)
        elif category == "channel":
            ch_id = await conf.counting_channel()
            ch = guild.get_channel(ch_id) if ch_id else None
            embed.add_field(name=t("ov_channel"),
                            value=ch.mention if ch else t("status_not_set"), inline=True)
        elif category == "saves":
            embed.add_field(name=t("ov_saves"),
                            value=f"`{await conf.saves()}`", inline=True)
        elif category == "price":
            embed.add_field(name=t("ov_price"),
                            value=f"`{await conf.save_price():,}`", inline=True)
        elif category == "reset":
            embed.description = (
                t("reset_confirm1") + "\n\n*" + t("reset_confirm1_hint") + "*"
            )
        return embed

    async def get_modal_fields(self, guild, category, lang):
        conf = self.config.guild(guild)
        t = lambda k: self.tr_sync(lang, k)
        if category == "language":
            return [("language", t("modal_language"), await conf.language())]
        if category == "channel":
            ch_id = await conf.counting_channel()
            return [("channel_id", "Channel ID (0 to clear)", ch_id or 0)]
        if category == "saves":
            return [("saves", "Saves (min 1)", await conf.saves())]
        if category == "price":
            return [("price", "Save price", await conf.save_price())]
        return []

    async def apply_modal_values(self, interaction, ctx, category, values):
        conf = self.config.guild(ctx.guild)
        try:
            if category == "language":
                lang_val = values.get("language", "").strip().lower()
                if lang_val not in self.locales:
                    raise ValueError(f"unknown language: {lang_val}")
                await conf.language.set(lang_val)
            elif category == "channel":
                v = int(values.get("channel_id") or 0)
                if v == 0:
                    await conf.counting_channel.set(None)
                else:
                    ch = ctx.guild.get_channel(v)
                    if not ch:
                        raise ValueError("channel not found")
                    await conf.counting_channel.set(v)
            elif category == "saves":
                v = int(values["saves"])
                if v < 1:
                    raise ValueError("min 1")
                await conf.saves.set(v)
            elif category == "price":
                await conf.save_price.set(int(values["price"]))
        except Exception as e:
            lang_now = await conf.language()
            if lang_now not in self.locales:
                lang_now = MAIN_LANGUAGE
            await interaction.response.send_message(
                self.tr_sync(lang_now, "menu_invalid_value", value=str(e)), ephemeral=True)
            return

        new_lang = await conf.language()
        if new_lang not in self.locales:
            new_lang = MAIN_LANGUAGE
        await interaction.response.send_message(
            self.tr_sync(new_lang, "menu_saved"), ephemeral=True)

        entry = self._active_menus.get((ctx.author.id, ctx.guild.id))
        if entry is not None:
            try:
                msg = entry["message"]
                cat = entry.get("category")
                if cat is None:
                    embed = await self.build_main_embed(ctx.guild, new_lang)
                    view = SetupMainView(self, ctx, lang=new_lang)
                else:
                    embed = await self.build_category_embed(ctx.guild, cat, new_lang)
                    view = self.build_category_view(ctx, cat, new_lang)
                await msg.edit(embed=embed, view=view)
            except Exception:
                pass

    # ── Reset ─────────────────────────────────────────────────

    @countset.command(name="resetguild")
    async def reset_guild(self, ctx):
        """Reset the counting game for this server."""
        conf = self.config.guild(ctx.guild)
        await conf.current_count.set(0)
        await conf.saves.set(3)
        await conf.last_counter.set(None)
        await conf.current_streak.set(0)
        await conf.best_streak.set(0)
        await conf.total_counts.set(0)
        await conf.total_mistakes.set(0)
        await conf.leaderboard.set({})
        await ctx.send(await self._(ctx.guild, "reset_success_msg"))

    # ── Legacy subcommands ────────────────────────────────────

    @countset.command(name="channel")
    async def set_channel(self, ctx, channel: discord.TextChannel = None):
        """Set or clear the counting channel."""
        if channel is None:
            await self.config.guild(ctx.guild).counting_channel.set(None)
            await ctx.send(await self._(ctx.guild, "channel_cleared"))
        else:
            await self.config.guild(ctx.guild).counting_channel.set(channel.id)
            await ctx.send(await self._(ctx.guild, "channel_set", channel=channel.mention))

    @countset.command(name="saves")
    async def set_saves(self, ctx, saves: int):
        """Set the number of saves."""
        if saves < 1:
            await ctx.send(await self._(ctx.guild, "saves_invalid"))
            return
        await self.config.guild(ctx.guild).saves.set(saves)
        await ctx.send(await self._(ctx.guild, "saves_set", saves=saves))

    @countset.command(name="price")
    async def set_price(self, ctx, price: int):
        """Set the save price."""
        await self.config.guild(ctx.guild).save_price.set(price)
        await ctx.send(await self._(ctx.guild, "price_set",
                                    price=price,
                                    currency=await bank.get_currency_name(ctx.guild)))

    @countset.command(name="language")
    async def set_language(self, ctx, lang: str):
        """Set the language by code (e.g. `en`, `de`)."""
        lang = lang.lower()
        if lang not in self.locales:
            available = ", ".join(f"`{c}`" for c in self.available_languages())
            await ctx.send(self.tr_sync(
                await self.config.guild(ctx.guild).language(),
                "language_invalid", available=available))
            return
        await self.config.guild(ctx.guild).language.set(lang)
        await ctx.send(await self._(ctx.guild, "language_set",
                                    name=self.language_name(lang)))


# ═════════════════════════════════════════════════════════════
#  UI VIEWS
# ═════════════════════════════════════════════════════════════
class EditModal(discord.ui.Modal):
    def __init__(self, cog, ctx, category, fields, lang="en"):
        super().__init__(title=f"Edit: {category}"[:45])
        self.cog = cog
        self.ctx = ctx
        self.category = category
        self.lang = lang
        self.inputs = {}
        for key, label, default in fields[:5]:
            inp = discord.ui.TextInput(
                label=label[:45],
                default=str(default)[:100] if default is not None else "",
                required=False, max_length=100,
            )
            self.add_item(inp)
            self.inputs[key] = inp

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                self.cog.tr_sync(self.lang, "menu_only_author"), ephemeral=True)
            return
        values = {k: v.value for k, v in self.inputs.items()}
        await self.cog.apply_modal_values(interaction, self.ctx, self.category, values)


class CategorySelect(discord.ui.Select):
    def __init__(self, cog, ctx, lang="en", current=None):
        self.cog = cog
        self.ctx = ctx
        self.lang = lang
        opts = [
            discord.SelectOption(label=cog.tr_sync(lang, "menu_language"), value="language"),
            discord.SelectOption(label=cog.tr_sync(lang, "menu_channel"), value="channel"),
            discord.SelectOption(label=cog.tr_sync(lang, "menu_saves"), value="saves"),
            discord.SelectOption(label=cog.tr_sync(lang, "menu_price"), value="price"),
            discord.SelectOption(label=cog.tr_sync(lang, "menu_reset"), value="reset"),
        ]
        for o in opts:
            if o.value == current:
                o.default = True
        super().__init__(
            placeholder=cog.tr_sync(lang, "menu_select_placeholder"),
            options=opts, row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                self.cog.tr_sync(self.lang, "menu_only_author"), ephemeral=True)
            return
        await self.cog.render_category(interaction, self.ctx, self.values[0], lang=self.lang)


class BackButton(discord.ui.Button):
    def __init__(self, cog, ctx, lang="en"):
        super().__init__(label=cog.tr_sync(lang, "menu_back"),
                         style=discord.ButtonStyle.secondary, row=1)
        self.cog = cog
        self.ctx = ctx
        self.lang = lang

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return
        await self.cog.render_main_menu(interaction, self.ctx, lang=self.lang)


class EditButton(discord.ui.Button):
    def __init__(self, cog, ctx, category, lang="en"):
        super().__init__(label=cog.tr_sync(lang, "menu_edit"),
                         style=discord.ButtonStyle.primary, row=1)
        self.cog = cog
        self.ctx = ctx
        self.category = category
        self.lang = lang

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return
        fields = await self.cog.get_modal_fields(self.ctx.guild, self.category, self.lang)
        if not fields:
            return
        await interaction.response.send_modal(
            EditModal(self.cog, self.ctx, self.category, fields, self.lang))


class ResetConfirmButton(discord.ui.Button):
    def __init__(self, cog, ctx, lang="en"):
        super().__init__(label=cog.tr_sync(lang, "menu_reset"),
                         style=discord.ButtonStyle.danger, row=1)
        self.cog = cog
        self.ctx = ctx
        self.lang = lang

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return
        embed = discord.Embed(
            title=self.cog.tr_sync(self.lang, "menu_reset"),
            description=(
                self.cog.tr_sync(self.lang, "reset_confirm1")
                + "\n\n*" + self.cog.tr_sync(self.lang, "reset_confirm1_hint") + "*"
            ),
            color=discord.Color.orange(),
        )
        view = ResetStep2View(self.cog, self.ctx, self.lang)
        await interaction.response.edit_message(embed=embed, view=view)


class ResetStep2View(discord.ui.View):
    def __init__(self, cog, ctx, lang):
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx
        self.lang = lang
        btn = discord.ui.Button(
            label=cog.tr_sync(lang, "reset_btn1"),
            style=discord.ButtonStyle.danger, row=0)
        btn.callback = self._step2
        self.add_item(btn)
        cancel = discord.ui.Button(
            label=cog.tr_sync(lang, "reset_cancel"),
            style=discord.ButtonStyle.secondary, row=0)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return
        await interaction.response.edit_message(
            content=self.cog.tr_sync(self.lang, "reset_cancelled"),
            embed=None, view=None,
        )

    async def _step2(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return
        embed = discord.Embed(
            title=self.cog.tr_sync(self.lang, "menu_reset"),
            description=(
                self.cog.tr_sync(self.lang, "reset_confirm2")
                + "\n\n*" + self.cog.tr_sync(self.lang, "reset_confirm2_hint") + "*"
            ),
            color=discord.Color.dark_red(),
        )
        view = ResetFinalView(self.cog, self.ctx, self.lang)
        await interaction.response.edit_message(embed=embed, view=view)


class ResetFinalView(discord.ui.View):
    def __init__(self, cog, ctx, lang):
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx
        self.lang = lang
        btn = discord.ui.Button(
            label=cog.tr_sync(lang, "reset_btn2"),
            style=discord.ButtonStyle.danger, row=0)
        btn.callback = self._final
        self.add_item(btn)
        cancel = discord.ui.Button(
            label=cog.tr_sync(lang, "reset_cancel"),
            style=discord.ButtonStyle.secondary, row=0)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return
        await interaction.response.edit_message(
            content=self.cog.tr_sync(self.lang, "reset_cancelled"),
            embed=None, view=None,
        )

    async def _final(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return
        conf = self.cog.config.guild(self.ctx.guild)
        await conf.current_count.set(0)
        await conf.saves.set(3)
        await conf.last_counter.set(None)
        await conf.current_streak.set(0)
        await conf.best_streak.set(0)
        await conf.total_counts.set(0)
        await conf.total_mistakes.set(0)
        await conf.leaderboard.set({})

        embed = await self.cog.build_main_embed(self.ctx.guild, self.lang)
        view = SetupMainView(self.cog, self.ctx, lang=self.lang)
        await interaction.response.edit_message(
            content=self.cog.tr_sync(self.lang, "reset_success_msg"),
            embed=embed, view=view,
        )


class SetupMainView(discord.ui.View):
    def __init__(self, cog, ctx, lang="en"):
        super().__init__(timeout=600)
        self.add_item(CategorySelect(cog, ctx, lang=lang))
