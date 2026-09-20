"""All embed builders."""

import discord

from .constants import (
    VERIFICATION_EMBED_TITLE,
    SETUP_AUTO_DELETE_SECONDS,
    CREDIT_LINE,
)


def verification_embed() -> discord.Embed:
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


def step1_embed() -> discord.Embed:
    return discord.Embed(
        title="🔧 Verification Setup – Step 1/4",
        description=(
            "Welcome to the setup wizard!\n\n"
            "**Please select the channel** where verification should take place."
            + CREDIT_LINE
        ),
        color=discord.Color.blue(),
    )


def step2_embed(channel) -> discord.Embed:
    return discord.Embed(
        title="🔧 Verification Setup – Step 2/4",
        description=(
            f"**Channel selected:** {channel.mention}\n\n"
            "**Now select the role** that will be granted to verified users."
            + CREDIT_LINE
        ),
        color=discord.Color.blue(),
    )


def step3_embed(channel, role) -> discord.Embed:
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


def step4_embed(channel, role, mode: str, message_id, emoji: str) -> discord.Embed:
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


def success_embed(description, role, channel, mode, emoji) -> discord.Embed:
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


def error_embed(description: str) -> discord.Embed:
    return discord.Embed(
        title="❌ Setup Failed",
        description=description + CREDIT_LINE,
        color=discord.Color.red(),
    )


def cancel_embed() -> discord.Embed:
    return discord.Embed(
        title="❌ Setup Cancelled",
        description=(
            "The setup process was cancelled. This message will disappear in a moment."
            + CREDIT_LINE
        ),
        color=discord.Color.red(),
    )


def status_embed(channel_id, message_id, role_id, mode, emoji,
                 *, title="📊 Verification Status") -> discord.Embed:
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


def not_setup_embed() -> discord.Embed:
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