[![Red-DiscordBot](https://img.shields.io/badge/Red--DiscordBot-%23cd0000?style=flat)](https://github.com/Cog-Creators/Red-DiscordBot) [![Finn_Bot](https://img.shields.io/badge/Finn__Bot-%231874cd?style=flat)](https://finn-bot.rf.gd) 

# ToHubLab-Cogs

This repository is where my Red-DiscordBot cogs are published, maintained, and kept up to date. Explore the available cogs and their latest versions here.
<details>
<summary>📌 sticky</summary>

# Sticky Cog for Red-DiscordBot

A powerful cog that keeps a message pinned at the bottom of a Discord channel. When new messages arrive, the sticky message automatically moves down — no need to delete and repost manually.

## ✨ Features
| Feature | Description |
|---|---|
| 📌 **Persistent Messages** | Keep a message permanently visible at the bottom of a channel |
| 📝 **Text Stickies** | Create sticky messages with emojis, mentions, and Markdown |
| 🖼️ **Embeds** | Copy embeds 1:1 from any existing message |
| 🔘 **Components** | Support buttons, link buttons, select menus, and custom emojis |
| ⚙️ **Command Buttons** | Add buttons that trigger real bot commands |
| 🔄 **Automatic Reposting** | Automatically moves the sticky message down when new messages arrive |
| ⏱️ **Configurable Delay** | Set a debounce delay per channel or globally to prevent unnecessary reposts |
| 🧹 **Auto-delete** | Automatically remove bot replies after a configurable number of seconds to reduce spam |
| 🖱️ **Interactive Menu** | Manage all configured stickies through buttons, modals, and an interactive menu |
| 📋 **Sticky Overview** | View all active stickies, including previews and configured delays |
| ✏️ **Easy Editing** | Edit existing stickies without manually deleting and recreating them |
| 🌐 **Bilingual** | Switch between English and German live from the interactive menu |
| 🔧 **Persistent Buttons** | Buttons continue to work even after the bot restarts |
| 🔒 **Permission Checks** | Commands triggered via buttons respect the permissions of the user who clicked them |
| 🔒 **Admin Only** | Configuration commands are restricted to administrators |
| 🐛 **Debug Mode** | Display detailed error messages to simplify troubleshooting |
| 🎨 **Finn Bot Theme** | Teal-themed embeds matching Finn Bot's branding |
| 🐙 **Credits** | Built-in credits page with links to GitHub, website, and Discord |

## 📦 Installation

```text
[p]repo add ToHubLab-Cogs https://github.com/ToHubLab/ToHubLab-Cogs
```
```text
[p]cog install ToHubLab-Cogs sticky
```
```text
[p]load sticky
```
</details>
</details>

<details>
<summary>📌 verification</summary>

# Verification Cog for Red-DiscordBot

A Red-DiscordBot cog that verifies new members via a button or reaction, challenges them with a math or text task, and grants a role — with a full setup wizard, custom emoji support, security checks, and a live management menu.

## ✨ Features

| Feature | Description |
|---|---|
| ⚙️ **Interactive Setup Wizard** | 4-step wizard: channel → role → mode → confirm — one single message, no spam |
| 🔘 **Button Mode** | Users verify via a button directly on a message the bot posts |
| 💬 **Reaction Mode** | Use any existing message — the bot adds a reaction emoji to trigger verification |
| 🎨 **Emoji Picker** | Choose from 24 standard emojis — or extend them via a JSON data file |
| 🧮 **Math Challenges** | Random addition, subtraction, and multiplication problems |
| ✍️ **Text Challenges** | Prompts like `Type 'ToHubLab' to verify` or `Write 'Color' to verify` |
| 🎭 **Auto Role Assignment** | Grants the configured verification role upon success |
| ⏳ **3-Strike Lockout** | Wrong answers lock the user out for 10 minutes with a live progress bar |
| 🔐 **Security Check** | If the role is manually removed, users answer 2 security questions to re-verify |
| 🧹 **Auto-Cleanup** | Setup, status, reset, and cancel messages auto-delete after a few seconds |
| 🔄 **Background Sync** | Every 5 minutes, reactions and roles are synced to prevent drift |
| 📊 **Live Status Menu** | `.verifymenu` shows the current config with buttons to change things |
| 📋 **Verified Users List** | `.verifysetup verified` — ephemeral, paginated (5 per page), with Prev/Next |
| 📁 **JSON Data File** | Emoji options, text challenges, and security questions all live in one file |
| 🔧 **Persistent Buttons** | Verification buttons keep working after bot restarts |
| 🔒 **Admin Only** | Configuration commands require `Manage Server` |
| 🐙 **Credits** | Built-in link to [ToHubLab on GitHub](https://github.com/ToHubLab) |

## 📦 Installation

```text
[p]repo add ToHubLab-Cogs https://github.com/ToHubLab/ToHubLab-Cogs
```

```text
[p]cog install ToHubLab-Cogs verification
```

```text
[p]verifysetup start
```
</details>
</details>

## Support

- **Bug reports & feature requests:** Please open an issue in the repository.
- **Quick help & general support:**  [![Discord Support](https://img.shields.io/discord/1549415908143792149?logo=discord&label=Discord%20Support)](https://discord.gg/xZgWjC2HH)

