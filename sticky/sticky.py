import asyncio
import discord
from redbot.core import commands, Config


class Sticky(commands.Cog):
    """Keep a message at the bottom of a channel."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=4578932145, force_registration=True)
        self.config.register_guild(channels={})
        self._locks = {}

    # ---------- Helpers ----------
    async def _get_data(self, guild, channel_id):
        channels = await self.config.guild(guild).channels()
        return channels.get(str(channel_id))

    async def _set_data(self, guild, channel_id, data):
        channels = await self.config.guild(guild).channels()
        channels[str(channel_id)] = data
        await self.config.guild(guild).channels.set(channels)

    async def _del_data(self, guild, channel_id):
        channels = await self.config.guild(guild).channels()
        channels.pop(str(channel_id), None)
        await self.config.guild(guild).channels.set(channels)

    def _get_lock(self, channel_id):
        if channel_id not in self._locks:
            self._locks[channel_id] = asyncio.Lock()
        return self._locks[channel_id]

    # ---------- Commands ----------
    @commands.group()
    @commands.admin_or_permissions(manage_messages=True)
    async def sticky(self, ctx):
        """Manage sticky messages."""

    @sticky.command(name="set")
    async def sticky_set(self, ctx, channel: discord.TextChannel, *, message: str):
        """Set a sticky message for a channel."""
        # Delete the previous sticky if any
        old = await self._get_data(ctx.guild, channel.id)
        if old and old.get("last_id"):
            try:
                old_msg = await channel.fetch_message(old["last_id"])
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        # Post the new sticky
        try:
            sticky_msg = await channel.send(message)
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to send messages in that channel.")
            return

        await self._set_data(ctx.guild, channel.id, {
            "content": message,
            "last_id": sticky_msg.id
        })
        await ctx.send(f"✅ Sticky message set in {channel.mention}.")

    @sticky.command(name="remove")
    async def sticky_remove(self, ctx, channel: discord.TextChannel):
        """Remove the sticky message from a channel."""
        data = await self._get_data(ctx.guild, channel.id)
        if not data:
            await ctx.send("❌ There is no sticky message in that channel.")
            return

        if data.get("last_id"):
            try:
                msg = await channel.fetch_message(data["last_id"])
                await msg.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        await self._del_data(ctx.guild, channel.id)
        await ctx.send(f"✅ Sticky message removed from {channel.mention}.")

    @sticky.command(name="list")
    async def sticky_list(self, ctx):
        """List all sticky messages in this server."""
        channels = await self.config.guild(ctx.guild).channels()
        if not channels:
            await ctx.send("📋 No sticky messages configured.")
            return

        lines = []
        for ch_id, data in channels.items():
            ch = ctx.guild.get_channel(int(ch_id))
            if ch:
                preview = data["content"][:70] + ("..." if len(data["content"]) > 70 else "")
                lines.append(f"• {ch.mention}: {preview}")

        if lines:
            await ctx.send("📋 **Sticky messages:**\n" + "\n".join(lines))
        else:
            await ctx.send("📋 No valid sticky messages found.")

    # ---------- Listener ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        data = await self._get_data(message.guild, message.channel.id)
        if not data:
            return

        # Don't react to the sticky message itself
        if message.id == data.get("last_id"):
            return

        lock = self._get_lock(message.channel.id)
        async with lock:
            # Delete old sticky
            if data.get("last_id"):
                try:
                    old = await message.channel.fetch_message(data["last_id"])
                    await old.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass

            # Short delay so consecutive messages don't cause spam
            await asyncio.sleep(0.3)

            # Post the new sticky
            try:
                new_msg = await message.channel.send(data["content"])
                await self._set_data(message.guild, message.channel.id, {
                    "content": data["content"],
                    "last_id": new_msg.id
                })
            except discord.Forbidden:
                pass