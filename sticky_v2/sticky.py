import asyncio
import discord
from redbot.core import commands, Config

DEFAULT_DELAY = 10
GITHUB_URL = "https://github.com/ToHubLab"
WEBSITE_URL = "https://finn-bot.rf.gd/"
DISCORD_URL = "https://discord.com/invite/TgYqGq9P3v"

class StickyTextModal(discord.ui.Modal):
    def __init__(self, cog, guild, channel, existing=None):
        super().__init__(title=f"Sticky for #{channel.name}"[:45])
        self.cog = cog
        self.guild = guild
        self.channel = channel
        self.text_input = discord.ui.TextInput(
            label="Message content",
            style=discord.TextStyle.paragraph,
            default=existing or "",
            required=True,
            max_length=2000,
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction):
        content = self.text_input.value
        old = await self.cog._get_data(self.guild, self.channel.id)

        if old and old.get("last_id"):
            try:
                old_msg = await self.channel.fetch_message(old["last_id"])
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        try:
            new_msg = await self.channel.send(content)
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {self.channel.mention}.",
                ephemeral=True,
            )
            return

        new_data = {"content": content, "last_id": new_msg.id}
        if old and "delay" in old:
            new_data["delay"] = old["delay"]
        await self.cog._set_data(self.guild, self.channel.id, new_data)

        await interaction.response.send_message(
            f"✅ Sticky set in {self.channel.mention}.",
            ephemeral=True,
        )

class DelayModal(discord.ui.Modal):
    def __init__(self, cog, guild, channel, current=DEFAULT_DELAY):
        super().__init__(title=f"Delay for #{channel.name}"[:45])
        self.cog = cog
        self.guild = guild
        self.channel = channel
        self.delay_input = discord.ui.TextInput(
            label="Delay in seconds (0-600)",
            placeholder="e.g. 5",
            default=str(current),
            required=True,
            max_length=4,
        )
        self.add_item(self.delay_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            seconds = int(self.delay_input.value)
            if seconds < 0 or seconds > 600:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number between 0 and 600.",
                ephemeral=True,
            )
            return

        data = await self.cog._get_data(self.guild, self.channel.id)
        if not data:
            await interaction.response.send_message(
                f"❌ No sticky in {self.channel.mention}.",
                ephemeral=True,
            )
            return

        data["delay"] = seconds
        await self.cog._set_data(self.guild, self.channel.id, data)

        await interaction.response.send_message(
            f"✅ Delay for {self.channel.mention} set to **{seconds}s**.",
            ephemeral=True,
        )

def render_mentions(guild, content):
    if guild is None:
        return content
    try:
        for ch in guild.channels:
            content = content.replace(f"<#{ch.id}>", f"#{ch.name}")
        for role in guild.roles:
            content = content.replace(f"<@&{role.id}>", f"@{role.name}")
        for member in guild.members:
            content = content.replace(f"<@{member.id}>", f"@{member.display_name}")
            content = content.replace(f"<@!{member.id}>", f"@{member.display_name}")
    except Exception:
        pass
    return content

def build_credits_embed():
    embed = discord.Embed(
        title="Sticky Cog - Credits",
        description=(
            "Thank you for using **Sticky**!\n"
            "This cog is maintained by **ToHubLab**."
        ),
        color=discord.Color.teal(),
    )
    embed.add_field(
        name="Links",
        value=(
            f"[Website]({WEBSITE_URL})\n"
            f"[GitHub]({GITHUB_URL})\n"
            f"[Discord Support]({DISCORD_URL})"
        ),
        inline=False,
    )
    embed.set_footer(text="Sticky v2 - Made by ToHubLab")
    return embed

class ChannelPickerView(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild = guild
        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Pick a channel...",
            channel_types=[discord.ChannelType.text],
        )
        self.channel_select.callback = self.on_channel_pick
        self.add_item(self.channel_select)

    async def on_channel_pick(self, interaction: discord.Interaction):
        channel_ref = self.channel_select.values[0]
        channel = self.guild.get_channel(channel_ref.id)
        if channel is None:
            channel = await self.cog.bot.fetch_channel(channel_ref.id)

        data = await self.cog._get_data(self.guild, channel.id)
        existing = data["content"] if data else None
        modal = StickyTextModal(self.cog, self.guild, channel, existing)
        await interaction.response.send_modal(modal)
        self.stop()

class CreditsView(discord.ui.View):
    def __init__(self, parent=None):
        super().__init__(timeout=300)
        self.parent = parent

    @discord.ui.button(
        label="Back",
        style=discord.ButtonStyle.secondary,
        emoji="◀️",
        row=0,
    )
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.parent:
            await self.parent.refresh_select()
            embed = await self.parent.build_embed()
            await interaction.response.edit_message(embed=embed, view=self.parent)
        else:
            await interaction.response.edit_message(content="Closed.", embed=None, view=None)

class StickyManageView(discord.ui.View):
    def __init__(self, cog, guild, channel, parent=None):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.channel = channel
        self.parent = parent

    async def build_embed(self):
        data = await self.cog._get_data(self.guild, self.channel.id)
        default_delay = await self.cog.config.guild(self.guild).default_delay()
        delay = data.get("delay", default_delay) if data else default_delay

        embed = discord.Embed(
            title=f"Sticky in #{self.channel.name}",
            color=discord.Color.teal(),
        )
        if data:
            content = render_mentions(self.guild, data["content"])
            preview = content[:1000] + "..." if len(content) > 1000 else content
            embed.add_field(name="Content", value=preview, inline=False)
            embed.add_field(name="Delay", value=f"{delay}s", inline=True)
            embed.add_field(
                name="Last message ID",
                value=str(data.get("last_id", "N/A")),
                inline=True,
            )
        else:
            embed.description = (
                "No sticky set for this channel yet. Click **Edit Text** to create one."
            )
        return embed

    async def _go_back(self, interaction: discord.Interaction):
        if self.parent:
            await self.parent.refresh_select()
            parent_embed = await self.parent.build_embed()
            await interaction.response.edit_message(embed=parent_embed, view=self.parent)
        else:
            await interaction.response.edit_message(content="Closed.", embed=None, view=None)

    @discord.ui.button(
        label="Edit Text",
        style=discord.ButtonStyle.primary,
        emoji="✏️",
        row=0,
    )
    async def edit_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await self.cog._get_data(self.guild, self.channel.id)
        existing = data["content"] if data else None
        modal = StickyTextModal(self.cog, self.guild, self.channel, existing)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Change Delay",
        style=discord.ButtonStyle.primary,
        emoji="⏱️",
        row=0,
    )
    async def change_delay(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await self.cog._get_data(self.guild, self.channel.id)
        default_delay = await self.cog.config.guild(self.guild).default_delay()
        current = data.get("delay", default_delay) if data else default_delay
        modal = DelayModal(self.cog, self.guild, self.channel, current)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Remove",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        row=0,
    )
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await self.cog._get_data(self.guild, self.channel.id)
        if data and data.get("last_id"):
            try:
                msg = await self.channel.fetch_message(data["last_id"])
                await msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        await self.cog._del_data(self.guild, self.channel.id)
        await self._go_back(interaction)

    @discord.ui.button(
        label="Back",
        style=discord.ButtonStyle.secondary,
        emoji="◀️",
        row=0,
    )
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._go_back(interaction)

class StickyMenuView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.guild = ctx.guild
        self.message = None

        self.select = discord.ui.Select(
            placeholder="Select a sticky to manage...",
            options=[discord.SelectOption(label="Loading...", value="_loading")],
            row=1,
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def refresh_select(self):
        channels = await self.cog._all_data(self.guild)
        options = []
        for ch_id, data in channels.items():
            ch = self.guild.get_channel(int(ch_id))
            if ch is None:
                continue
            preview = data["content"].replace("\n", " ")
            if len(preview) > 90:
                preview = preview[:87] + "..."
            options.append(
                discord.SelectOption(
                    label=f"#{ch.name}"[:100],
                    value=str(ch.id),
                    description=preview[:100],
                )
            )

        if not options:
            self.select.options = [
                discord.SelectOption(label="No stickies yet", value="_none")
            ]
            self.select.disabled = True
        else:
            self.select.options = options[:25]
            self.select.disabled = False

    async def build_embed(self):
        channels = await self.cog._all_data(self.guild)
        default_delay = await self.cog.config.guild(self.guild).default_delay()

        embed = discord.Embed(
            title="Sticky Messages",
            description=(
                "Use the menu below to manage stickies, or click **Add New Sticky**."
            ),
            color=discord.Color.teal(),
        )

        if not channels:
            embed.add_field(
                name="No stickies yet",
                value="Click **Add New Sticky** to create your first one.",
                inline=False,
            )
        else:
            for ch_id, data in channels.items():
                ch = self.guild.get_channel(int(ch_id))
                if ch is None:
                    continue
                content = render_mentions(self.guild, data["content"])
                preview = content[:100] + "..." if len(content) > 100 else content
                delay = data.get("delay", default_delay)
                embed.add_field(
                    name=f"#{ch.name} ({delay}s)",
                    value=preview,
                    inline=False,
                )

        embed.set_footer(text=f"Default delay: {default_delay}s - Made by ToHubLab")
        return embed

    async def on_select(self, interaction: discord.Interaction):
        value = self.select.values[0]
        if value == "_none":
            await interaction.response.defer()
            return
        channel_id = int(value)
        channel = self.guild.get_channel(channel_id)
        if channel is None:
            await interaction.response.send_message(
                "❌ Channel not found.", ephemeral=True
            )
            return
        sub_view = StickyManageView(self.cog, self.guild, channel, parent=self)
        embed = await sub_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=sub_view)

    @discord.ui.button(
        label="Add New Sticky",
        style=discord.ButtonStyle.success,
        emoji="➕",
        row=0,
    )
    async def add_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        picker = ChannelPickerView(self.cog, self.guild)
        await interaction.response.send_message(
            "Pick a channel for the new sticky:",
            view=picker,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Refresh",
        style=discord.ButtonStyle.secondary,
        emoji="🔄",
        row=0,
    )
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.refresh_select()
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="Credits",
        style=discord.ButtonStyle.secondary,
        emoji="🐙",
        row=0,
    )
    async def credits(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_credits_embed()
        view = CreditsView(parent=self)
        await interaction.response.edit_message(embed=embed, view=view)

class Sticky(commands.Cog):
    """Keep a message at the bottom of a channel with a configurable debounce."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=4578932145, force_registration=True
        )
        self.config.register_guild(channels={}, default_delay=DEFAULT_DELAY)
        self._timers = {}
        self._locks = {}

    async def cog_unload(self):
        for t in self._timers.values():
            t.cancel()
        self._timers.clear()

    async def _get_data(self, guild, channel_id):
        channels = await self.config.guild(guild).channels()
        return channels.get(str(channel_id))

    async def _all_data(self, guild):
        return await self.config.guild(guild).channels()

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

    async def _post_sticky(self, guild, channel_id):
        data = await self._get_data(guild, channel_id)
        if not data:
            return
        channel = guild.get_channel(channel_id)
        if channel is None:
            return

        lock = self._get_lock(channel_id)
        async with lock:
            if data.get("last_id"):
                try:
                    old = await channel.fetch_message(data["last_id"])
                    await old.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
            try:
                new_msg = await channel.send(data["content"])
            except (discord.Forbidden, discord.HTTPException):
                return
            data["last_id"] = new_msg.id
            await self._set_data(guild, channel_id, data)

    async def _schedule_repost(self, guild, channel_id):
        existing = self._timers.get(channel_id)
        if existing and not existing.done():
            existing.cancel()
        self._timers[channel_id] = asyncio.create_task(
            self._debounced_repost(guild, channel_id)
        )

    async def _debounced_repost(self, guild, channel_id):
        try:
            data = await self._get_data(guild, channel_id)
            if not data:
                return
            default_delay = await self.config.guild(guild).default_delay()
            delay = data.get("delay", default_delay)
            await asyncio.sleep(delay)
            await self._post_sticky(guild, channel_id)
        except asyncio.CancelledError:
            pass
        finally:
            self._timers.pop(channel_id, None)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if message.type not in (
            discord.MessageType.default,
            discord.MessageType.reply,
        ):
            return
        data = await self._get_data(message.guild, message.channel.id)
        if not data:
            return
        if message.id == data.get("last_id"):
            return
        await self._schedule_repost(message.guild, message.channel.id)

    @commands.group(invoke_without_command=True)
    @commands.admin_or_permissions(manage_messages=True)
    async def sticky(self, ctx):
        """Manage sticky messages."""
        await ctx.send_help(ctx.command)

    @sticky.command(name="menu")
    @commands.admin_or_permissions(manage_messages=True)
    async def sticky_menu(self, ctx):
        """Open the interactive sticky menu."""
        view = StickyMenuView(self, ctx)
        await view.refresh_select()
        embed = await view.build_embed()
        view.message = await ctx.send(embed=embed, view=view)

    @sticky.command(name="set")
    @commands.admin_or_permissions(manage_messages=True)
    async def sticky_set(self, ctx, channel: discord.TextChannel, *, message: str):
        """Set a sticky message in a channel."""
        old = await self._get_data(ctx.guild, channel.id)
        if old and old.get("last_id"):
            try:
                old_msg = await channel.fetch_message(old["last_id"])
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        try:
            sticky_msg = await channel.send(message)
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send(
                "❌ I don't have permission to send messages in that channel."
            )
            return

        new_data = {"content": message, "last_id": sticky_msg.id}
        if old and "delay" in old:
            new_data["delay"] = old["delay"]
        await self._set_data(ctx.guild, channel.id, new_data)
        await ctx.send(f"✅ Sticky message set in {channel.mention}.")

    @sticky.command(name="edit")
    @commands.admin_or_permissions(manage_messages=True)
    async def sticky_edit(
        self, ctx, channel: discord.TextChannel, *, message: str
    ):
        """Edit an existing sticky message's text."""
        data = await self._get_data(ctx.guild, channel.id)
        if not data:
            await ctx.send("❌ No sticky in that channel.")
            return

        if data.get("last_id"):
            try:
                old = await channel.fetch_message(data["last_id"])
                await old.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        try:
            new_msg = await channel.send(message)
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send(
                "❌ I don't have permission to send messages in that channel."
            )
            return

        data["content"] = message
        data["last_id"] = new_msg.id
        await self._set_data(ctx.guild, channel.id, data)
        await ctx.send(f"✅ Sticky message updated in {channel.mention}.")

    @sticky.command(name="remove")
    @commands.admin_or_permissions(manage_messages=True)
    async def sticky_remove(self, ctx, channel: discord.TextChannel):
        """Remove a sticky message from a channel."""
        data = await self._get_data(ctx.guild, channel.id)
        if not data:
            await ctx.send("❌ No sticky in that channel.")
            return

        if data.get("last_id"):
            try:
                msg = await channel.fetch_message(data["last_id"])
                await msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        await self._del_data(ctx.guild, channel.id)
        await ctx.send(f"✅ Sticky message removed from {channel.mention}.")

    @sticky.command(name="delay")
    @commands.admin_or_permissions(manage_messages=True)
    async def sticky_delay(self, ctx, channel: discord.TextChannel, seconds: int):
        """Set a custom debounce delay for one channel's sticky (0-600s)."""
        if not 0 <= seconds <= 600:
            await ctx.send("❌ Delay must be between 0 and 600 seconds.")
            return
        data = await self._get_data(ctx.guild, channel.id)
        if not data:
            await ctx.send("❌ No sticky in that channel.")
            return
        data["delay"] = seconds
        await self._set_data(ctx.guild, channel.id, data)
        await ctx.send(f"✅ Delay for {channel.mention} set to **{seconds}s**.")

    @sticky.command(name="defaultdelay")
    @commands.admin_or_permissions(manage_messages=True)
    async def sticky_defaultdelay(self, ctx, seconds: int):
        """Set the default debounce delay for stickies without a custom value."""
        if not 0 <= seconds <= 600:
            await ctx.send("❌ Delay must be between 0 and 600 seconds.")
            return
        await self.config.guild(ctx.guild).default_delay.set(seconds)
        await ctx.send(f"✅ Default delay set to **{seconds}s**.")

    @sticky.command(name="list")
    @commands.admin_or_permissions(manage_messages=True)
    async def sticky_list(self, ctx):
        """Show an overview of all sticky messages."""
        channels = await self._all_data(ctx.guild)
        default_delay = await self.config.guild(ctx.guild).default_delay()

        if not channels:
            await ctx.send("No sticky messages configured.")
            return

        embed = discord.Embed(
            title="Sticky Messages",
            color=discord.Color.teal(),
        )
        for ch_id, data in channels.items():
            ch = ctx.guild.get_channel(int(ch_id))
            if ch is None:
                continue
            content = render_mentions(ctx.guild, data["content"])
            preview = content[:100] + "..." if len(content) > 100 else content
            delay = data.get("delay", default_delay)
            embed.add_field(
                name=f"#{ch.name} ({delay}s)",
                value=preview,
                inline=False,
            )
        embed.set_footer(text=f"Default delay: {default_delay}s - Made by ToHubLab")
        await ctx.send(embed=embed)

    @sticky.command(name="credits")
    @commands.admin_or_permissions(manage_messages=True)
    async def sticky_credits(self, ctx):
        """Show the credits for this cog."""
        await ctx.send(embed=build_credits_embed())

async def setup(bot):
    await bot.add_cog(Sticky(bot))
