import asyncio
import contextlib
import time

import discord
from discord.ext import commands

from redbot.core import Config, commands as red_commands
from redbot.core.bot import Red
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

DEBOUNCE_SECONDS = 10
DEFAULT_LANG = "en"

LANG_DISPLAY = {"de": "Deutsch", "en": "English"}

# ============================================================
# Übersetzungen (direkt eingebettet – kein .po/.mo nötig)
# ============================================================
TRANSLATIONS = {
    "en": {
        # Embed-Titel / Beschreibungen
        "info_title": "C – Cleaner",
        "info_desc": "A simple cleaner cog that counts deleted messages and provides cleanup commands.",
        "stats_title": "C – Statistics",
        "commands_title": "C – Commands",
        "commands_desc": "List of all commands provided by this cog.",
        # Feldnamen
        "field_deleted": "Deleted messages",
        "field_deleted_server": "Deleted messages (this server)",
        "field_server": "Server",
        "field_author": "Author",
        "field_repository": "Repository",
        "field_debug": "Debug mode",
        "debug_on": "🟢 on",
        "debug_off": "🔴 off",
        # Bestätigung
        "confirm_prompt": "⚠️ Are you sure? React with ✅ to confirm.",
        "confirm_timeout": "❌ Timed out. Aborted.",
        # Fehler
        "no_perm_delete": "❌ I don't have permission to delete messages.",
        "invalid_number": "❌ Please provide a valid number or `all`.",
        "invalid_lang": "❌ Invalid language. Use `de` or `en`.",
        "channel_not_found": "❌ Channel not found. Mention a channel or use `off`.",
        # Erfolge
        "deleted_count_msg": "✅ Deleted {count} messages.",
        "counter_reset": "✅ Counter reset to 0 for this server.",
        "lang_set": "✅ Language set to **{lang}**.",
        "lang_current": "🌐 Current language: **{lang}**",
        # Debug
        "debug_status_on": "🐛 Debug mode: 🟢 on → <#{ch}>",
        "debug_status_off": "🐛 Debug mode: 🔴 off",
        "debug_disabled": "🐛 Debug mode disabled.",
        "debug_enabled": "🐛 Debug mode enabled → {ch}",
        "debug_enabled_by": "🐛 Debug mode enabled by `{author}` (ID: {id})",
        # Log-Nachrichten
        "log_msg_deleted": "🗑️ **Message deleted** in {ch} (author: `{author}`)",
        "log_bulk_delete": "🧹 **Bulk delete** in {ch} — {amount} messages removed",
        "log_counter_reset": "♻️ Counter reset by `{author}`",
        "log_purge_all": "🧹 `{author}` purged **ALL** in {ch} ({count} deleted)",
        "log_purge_num": "🧹 `{author}` purged **{num}** in {ch} ({count} deleted)",
        "log_lang_changed": "🌐 Language set to **{lang}** by `{author}`",
        # Sonstiges
        "unknown": "unknown",
        "pong": "🏓 Pong! `{latency}ms`",
        # Command-Beschreibungen (cb)
        "cmd_cinfo": "Show information and current deleted-message count.",
        "cmd_cstats": "Show statistics for this server.",
        "cmd_cping": "Simple ping check.",
        "cmd_cclean": "Delete the given amount of messages, or all messages in this channel. Add `force` to skip confirmation.",
        "cmd_creset": "Reset the deleted-message counter for this server.",
        "cmd_cdebug": "Enable/disable debug mode and set the log channel.",
        "cmd_cc": "Show copyright and information about this cog.",
        "cmd_cb": "Show this list of commands.",
        "cmd_clang": "Set the language for this server (German or English).",
    },
    "de": {
        # Embed-Titel / Beschreibungen
        "info_title": "C – Cleaner",
        "info_desc": "Ein simpler Cleaner-Cog, der gelöschte Nachrichten zählt und Aufräumbefehle bereitstellt.",
        "stats_title": "C – Statistiken",
        "commands_title": "C – Befehle",
        "commands_desc": "Liste aller Befehle, die dieser Cog bereitstellt.",
        # Feldnamen
        "field_deleted": "Gelöschte Nachrichten",
        "field_deleted_server": "Gelöschte Nachrichten (dieser Server)",
        "field_server": "Server",
        "field_author": "Autor",
        "field_repository": "Repository",
        "field_debug": "Debug-Modus",
        "debug_on": "🟢 an",
        "debug_off": "🔴 aus",
        # Bestätigung
        "confirm_prompt": "⚠️ Bist du sicher? Reagiere mit ✅ zur Bestätigung.",
        "confirm_timeout": "❌ Zeitüberschreitung. Abgebrochen.",
        # Fehler
        "no_perm_delete": "❌ Ich habe keine Berechtigung, Nachrichten zu löschen.",
        "invalid_number": "❌ Bitte gib eine gültige Zahl oder `all` an.",
        "invalid_lang": "❌ Ungültige Sprache. Nutze `de` oder `en`.",
        "channel_not_found": "❌ Channel nicht gefunden. Erwähne einen Channel oder nutze `off`.",
        # Erfolge
        "deleted_count_msg": "✅ {count} Nachrichten gelöscht.",
        "counter_reset": "✅ Zähler für diesen Server auf 0 zurückgesetzt.",
        "lang_set": "✅ Sprache auf **{lang}** gesetzt.",
        "lang_current": "🌐 Aktuelle Sprache: **{lang}**",
        # Debug
        "debug_status_on": "🐛 Debug-Modus: 🟢 an → <#{ch}>",
        "debug_status_off": "🐛 Debug-Modus: 🔴 aus",
        "debug_disabled": "🐛 Debug-Modus deaktiviert.",
        "debug_enabled": "🐛 Debug-Modus aktiviert → {ch}",
        "debug_enabled_by": "🐛 Debug-Modus aktiviert von `{author}` (ID: {id})",
        # Log-Nachrichten
        "log_msg_deleted": "🗑️ **Nachricht gelöscht** in {ch} (Autor: `{author}`)",
        "log_bulk_delete": "🧹 **Massenlöschung** in {ch} — {amount} Nachrichten entfernt",
        "log_counter_reset": "♻️ Zähler zurückgesetzt von `{author}`",
        "log_purge_all": "🧹 `{author}` hat **ALLE** in {ch} geleert ({count} gelöscht)",
        "log_purge_num": "🧹 `{author}` hat **{num}** in {ch} geleert ({count} gelöscht)",
        "log_lang_changed": "🌐 Sprache auf **{lang}** gesetzt von `{author}`",
        # Sonstiges
        "unknown": "unbekannt",
        "pong": "🏓 Pong! `{latency}ms`",
        # Command-Beschreibungen (cb)
        "cmd_cinfo": "Zeigt Informationen und die aktuelle Anzahl gelöschter Nachrichten.",
        "cmd_cstats": "Zeigt Statistiken für diesen Server.",
        "cmd_cping": "Simpler Ping-Test.",
        "cmd_cclean": "Löscht die angegebene Anzahl an Nachrichten oder alle in diesem Channel. Mit `force` wird die Bestätigung übersprungen.",
        "cmd_creset": "Setzt den Zähler gelöschter Nachrichten für diesen Server zurück.",
        "cmd_cdebug": "Aktiviert/deaktiviert den Debug-Modus und setzt den Log-Channel.",
        "cmd_cc": "Zeigt Copyright und Informationen über diesen Cog.",
        "cmd_cb": "Zeigt diese Befehlsliste.",
        "cmd_clang": "Setzt die Sprache für diesen Server (Deutsch oder Englisch).",
    },
}


class C(red_commands.Cog):
    """Simple cleaner cog with statistics, cleanup commands, debug mode and i18n."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=0xC0FFEE2024, force_registration=True
        )
        self.config.register_guild(
            deleted_count=0,
            language=DEFAULT_LANG,
            debug_channel=None,
            debug_enabled=False,
        )

        self._recently_cleaned: dict[int, float] = {}

        self._debug_queue: asyncio.Queue = asyncio.Queue()
        self._debug_task: asyncio.Task = self.bot.loop.create_task(self._debug_worker())

    # ============================================================
    # Übersetzungs-Helper
    # ============================================================
    async def _t(self, guild: discord.Guild, key: str, **kwargs) -> str:
        """Gibt den übersetzten Text für die im Server eingestellte Sprache zurück."""
        lang = DEFAULT_LANG
        if guild is not None:
            lang = await self.config.guild(guild).language()
        table = TRANSLATIONS.get(lang) or TRANSLATIONS[DEFAULT_LANG]
        text = table.get(key) or TRANSLATIONS[DEFAULT_LANG].get(key) or key
        return text.format(**kwargs) if kwargs else text

    # ============================================================
    # Helper: Zähler
    # ============================================================
    async def _add_deleted(self, guild: discord.Guild, amount: int) -> int:
        conf = self.config.guild(guild)
        current = await conf.deleted_count()
        new = current + amount
        await conf.deleted_count.set(new)
        return new

    # ============================================================
    # Debug-Worker (2s Verzögerung pro Log)
    # ============================================================
    async def _debug_worker(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                guild_id, channel_id, text = await self._debug_queue.get()
                await asyncio.sleep(2)

                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    self._debug_queue.task_done()
                    continue

                channel = guild.get_channel(channel_id)
                if channel is None:
                    self._debug_queue.task_done()
                    continue

                try:
                    await channel.send(text)
                except discord.HTTPException:
                    pass

                self._debug_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                continue

    def cog_unload(self):
        self._debug_task.cancel()

    async def _debug_log(self, guild: discord.Guild, text: str):
        if guild is None:
            return
        conf = self.config.guild(guild)
        if not await conf.debug_enabled():
            return
        channel_id = await conf.debug_channel()
        if not channel_id:
            return
        await self._debug_queue.put((guild.id, channel_id, text))

    # ============================================================
    # Listener
    # ============================================================
    @red_commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if payload.guild_id is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        last = self._recently_cleaned.get(payload.channel_id, 0)
        if time.time() - last < DEBOUNCE_SECONDS:
            return

        if payload.cached_message and payload.cached_message.author.bot:
            return

        await self._add_deleted(guild, 1)

        channel = guild.get_channel(payload.channel_id)
        ch_mention = channel.mention if channel else f"<#{payload.channel_id}>"
        author = (
            str(payload.cached_message.author)
            if payload.cached_message
            else await self._t(guild, "unknown")
        )

        await self._debug_log(
            guild,
            await self._t(guild, "log_msg_deleted", ch=ch_mention, author=author),
        )

    @red_commands.Cog.listener()
    async def on_raw_bulk_message_delete(
        self, payload: discord.RawBulkMessageDeleteEvent
    ):
        if payload.guild_id is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        last = self._recently_cleaned.get(payload.channel_id, 0)
        if time.time() - last < DEBOUNCE_SECONDS:
            return

        amount = len(payload.message_ids)
        if amount == 0:
            return

        await self._add_deleted(guild, amount)

        channel = guild.get_channel(payload.channel_id)
        ch_mention = channel.mention if channel else f"<#{payload.channel_id}>"

        await self._debug_log(
            guild,
            await self._t(guild, "log_bulk_delete", ch=ch_mention, amount=amount),
        )

    # ============================================================
    # Confirm-Helper
    # ============================================================
    async def _confirm(self, ctx: commands.Context, timeout: int = 30) -> bool:
        prompt = await self._t(ctx.guild, "confirm_prompt")
        msg = await ctx.send(prompt)
        await start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        try:
            await self.bot.wait_for("reaction_add", check=pred, timeout=timeout)
        except asyncio.TimeoutError:
            with contextlib.suppress(discord.HTTPException):
                await msg.delete()
            await ctx.send(await self._t(ctx.guild, "confirm_timeout"), delete_after=5)
            return False
        with contextlib.suppress(discord.HTTPException):
            await msg.delete()
        return bool(pred.result)

    # ============================================================
    # Info / Ping / Stats
    # ============================================================
    @red_commands.command(name="cinfo", aliases=["c_info", "cleanerinfo"])
    @red_commands.guild_only()
    async def cinfo(self, ctx: commands.Context):
        """Show info about this cog and the current deleted-message count."""
        count = await self.config.guild(ctx.guild).deleted_count()

        embed = discord.Embed(
            title=await self._t(ctx.guild, "info_title"),
            description=await self._t(ctx.guild, "info_desc"),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name=await self._t(ctx.guild, "field_deleted_server"),
            value=str(count),
            inline=False,
        )
        embed.add_field(
            name=await self._t(ctx.guild, "field_author"),
            value="[ToHubLab](https://github.com/ToHubLab)",
            inline=False,
        )
        embed.set_footer(text="© ToHubLab")
        await ctx.send(embed=embed)

    @red_commands.command(name="cping", aliases=["c_ping"])
    async def cping(self, ctx: commands.Context):
        """Simple ping check."""
        latency = round(self.bot.latency * 1000)
        if ctx.guild:
            msg = await self._t(ctx.guild, "pong", latency=latency)
        else:
            msg = TRANSLATIONS[DEFAULT_LANG]["pong"].format(latency=latency)
        await ctx.send(msg)

    @red_commands.command(name="cstats", aliases=["c_stats"])
    @red_commands.guild_only()
    async def cstats(self, ctx: commands.Context):
        """Show statistics for this server."""
        conf = self.config.guild(ctx.guild)
        count = await conf.deleted_count()
        debug_on = await conf.debug_enabled()
        debug_ch = await conf.debug_channel()

        embed = discord.Embed(
            title=await self._t(ctx.guild, "stats_title"),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name=await self._t(ctx.guild, "field_server"),
            value=ctx.guild.name,
            inline=False,
        )
        embed.add_field(
            name=await self._t(ctx.guild, "field_deleted"),
            value=str(count),
            inline=False,
        )
        if debug_on and debug_ch:
            debug_state = await self._t(ctx.guild, "debug_status_on", ch=debug_ch)
        else:
            debug_state = await self._t(ctx.guild, "debug_status_off")
        embed.add_field(
            name=await self._t(ctx.guild, "field_debug"),
            value=debug_state,
            inline=False,
        )
        embed.set_footer(text="© ToHubLab")
        await ctx.send(embed=embed)

    # ============================================================
    # Reset
    # ============================================================
    @red_commands.command(name="creset", aliases=["c_reset"])
    @red_commands.guild_only()
    @red_commands.admin_or_permissions(manage_guild=True)
    async def creset(self, ctx: commands.Context):
        """Reset the deleted-message counter for this server."""
        await self.config.guild(ctx.guild).deleted_count.set(0)
        await self._debug_log(
            ctx.guild,
            await self._t(ctx.guild, "log_counter_reset", author=str(ctx.author)),
        )
        await ctx.send(await self._t(ctx.guild, "counter_reset"))

    # ============================================================
    # Cleanup
    # ============================================================
    @red_commands.command(name="cclean", aliases=["c_clean"])
    @red_commands.guild_only()
    @red_commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def cclean(self, ctx: commands.Context, *, args: str = ""):
        """Delete messages. Usage: `cclean <number>` or `cclean all [force]`."""

        parts = args.strip().lower().split()
        if not parts:
            await ctx.send(await self._t(ctx.guild, "invalid_number"))
            return

        target = parts[0]
        force_flag = any(p in ("force", "f", "-f", "--force", "yes", "true") for p in parts[1:])

        # ---- Permission-Check (nur bei menschlichen Aufrufern) ----
        if not ctx.author.bot:
            has_perm = (
                ctx.author.guild_permissions.manage_messages
                or ctx.author.guild_permissions.administrator
                or await self.bot.is_owner(ctx.author)
            )
            if not has_perm:
                await ctx.send(await self._t(ctx.guild, "no_perm_delete"))
                return

        # ---------- ALL ----------
        if target in ("all", "alles", "everything"):
            # Bestätigung nur bei Menschen ohne force
            if not force_flag and not ctx.author.bot:
                if not await self._confirm(ctx):
                    return

            try:
                deleted = await ctx.channel.purge(limit=None)
            except discord.Forbidden:
                await ctx.send(await self._t(ctx.guild, "no_perm_delete"))
                return

            self._recently_cleaned[ctx.channel.id] = time.time()
            await self._add_deleted(ctx.guild, len(deleted))

            await self._debug_log(
                ctx.guild,
                await self._t(
                    ctx.guild,
                    "log_purge_all",
                    author=str(ctx.author),
                    ch=ctx.channel.mention,
                    count=len(deleted),
                ),
            )
            with contextlib.suppress(discord.HTTPException):
                await ctx.send(
                    await self._t(ctx.guild, "deleted_count_msg", count=len(deleted)),
                    delete_after=5,
                )
            return

        # ---------- Zahl ----------
        try:
            num = int(target)
            if num <= 0:
                raise ValueError
        except ValueError:
            await ctx.send(await self._t(ctx.guild, "invalid_number"))
            return

        try:
            deleted = await ctx.channel.purge(limit=num)
        except discord.Forbidden:
            await ctx.send(await self._t(ctx.guild, "no_perm_delete"))
            return

        self._recently_cleaned[ctx.channel.id] = time.time()
        await self._add_deleted(ctx.guild, len(deleted))

        await self._debug_log(
            ctx.guild,
            await self._t(
                ctx.guild,
                "log_purge_num",
                author=str(ctx.author),
                num=num,
                ch=ctx.channel.mention,
                count=len(deleted),
            ),
        )
        with contextlib.suppress(discord.HTTPException):
            await ctx.send(
                await self._t(ctx.guild, "deleted_count_msg", count=len(deleted)),
                delete_after=5,
            )

    # ============================================================
    # Copyright / Help
    # ============================================================
    @red_commands.command(name="cc")
    async def cc(self, ctx: commands.Context):
        """Show copyright and information about this cog."""
        guild = ctx.guild
        embed = discord.Embed(
            title=await self._t(guild, "info_title"),
            url="https://github.com/ToHubLab",
            description=await self._t(guild, "info_desc"),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name=await self._t(guild, "field_author"),
            value="[ToHubLab](https://github.com/ToHubLab)",
            inline=False,
        )
        embed.add_field(
            name=await self._t(guild, "field_repository"),
            value="[github.com/ToHubLab](https://github.com/ToHubLab)",
            inline=False,
        )
        embed.set_footer(text="© ToHubLab")
        await ctx.send(embed=embed)

    @red_commands.command(name="cb", aliases=["chelp", "c_help"])
    async def cb(self, ctx: commands.Context):
        """Show all commands from this cog."""
        p = ctx.clean_prefix
        g = ctx.guild

        embed = discord.Embed(
            title=await self._t(g, "commands_title"),
            description=await self._t(g, "commands_desc"),
            color=discord.Color.blurple(),
        )
        embed.add_field(name=f"`{p}cinfo`", value=await self._t(g, "cmd_cinfo"), inline=False)
        embed.add_field(name=f"`{p}cstats`", value=await self._t(g, "cmd_cstats"), inline=False)
        embed.add_field(name=f"`{p}cping`", value=await self._t(g, "cmd_cping"), inline=False)
        embed.add_field(
            name=f"`{p}cclean <number|all> [force]`",
            value=await self._t(g, "cmd_cclean"),
            inline=False,
        )
        embed.add_field(name=f"`{p}creset`", value=await self._t(g, "cmd_creset"), inline=False)
        embed.add_field(
            name=f"`{p}cdebug <channel|off>`",
            value=await self._t(g, "cmd_cdebug"),
            inline=False,
        )
        embed.add_field(name=f"`{p}cc`", value=await self._t(g, "cmd_cc"), inline=False)
        embed.add_field(name=f"`{p}cb`", value=await self._t(g, "cmd_cb"), inline=False)
        embed.add_field(
            name=f"`{p}clang <de|en>`",
            value=await self._t(g, "cmd_clang"),
            inline=False,
        )
        embed.set_footer(text="© ToHubLab")
        await ctx.send(embed=embed)

    # ============================================================
    # Language (nur Cog-intern – sofort wirksam)
    # ============================================================
    @red_commands.command(name="clang", aliases=["c_lang"])
    @red_commands.guild_only()
    @red_commands.admin_or_permissions(manage_guild=True)
    async def clang(self, ctx: commands.Context, lang: str = None):
        """Set the language for this server. Usage: `clang de` or `clang en`."""
        current = await self.config.guild(ctx.guild).language()

        if lang is None:
            name = LANG_DISPLAY.get(current, current)
            await ctx.send(await self._t(ctx.guild, "lang_current", lang=name))
            return

        lang = lang.lower()
        if lang not in TRANSLATIONS:
            await ctx.send(await self._t(ctx.guild, "invalid_lang"))
            return

        await self.config.guild(ctx.guild).language.set(lang)

        # Bestätigung in der NEUEN Sprache senden
        name = LANG_DISPLAY.get(lang, lang)
        await ctx.send(await self._t(ctx.guild, "lang_set", lang=name))

        # Debug-Log in der neuen Sprache
        await self._debug_log(
            ctx.guild,
            await self._t(
                ctx.guild,
                "log_lang_changed",
                lang=name,
                author=str(ctx.author),
            ),
        )

    # ============================================================
    # Debug
    # ============================================================
    @red_commands.command(name="cdebug", aliases=["c_debug"])
    @red_commands.guild_only()
    @red_commands.admin_or_permissions(manage_guild=True)
    async def cdebug(self, ctx: commands.Context, target: str = None):
        """Enable/disable debug mode. Usage: `cdebug #channel` or `cdebug off`."""
        conf = self.config.guild(ctx.guild)

        if target is None:
            enabled = await conf.debug_enabled()
            ch_id = await conf.debug_channel()
            if enabled and ch_id:
                await ctx.send(await self._t(ctx.guild, "debug_status_on", ch=ch_id))
            else:
                await ctx.send(await self._t(ctx.guild, "debug_status_off"))
            return

        if target.lower() in ("off", "disable", "aus"):
            await conf.debug_enabled.set(False)
            await conf.debug_channel.set(None)
            await ctx.send(await self._t(ctx.guild, "debug_disabled"))
            return

        channel = None
        if ctx.message.channel_mentions:
            channel = ctx.message.channel_mentions[0]
        else:
            with contextlib.suppress(ValueError):
                channel = ctx.guild.get_channel(int(target))

        if channel is None:
            await ctx.send(await self._t(ctx.guild, "channel_not_found"))
            return

        await conf.debug_channel.set(channel.id)
        await conf.debug_enabled.set(True)
        await ctx.send(await self._t(ctx.guild, "debug_enabled", ch=channel.mention))

        await self._debug_log(
            ctx.guild,
            await self._t(
                ctx.guild,
                "debug_enabled_by",
                author=str(ctx.author),
                id=ctx.author.id,
            ),
        )
