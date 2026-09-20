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
