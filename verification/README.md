# Verification Cog for Red-DiscordBot

A Red-DiscordBot cog that verifies new members via a button or reaction, challenges them with a math or text task, and grants a role — with a full setup wizard, custom emoji support, security checks, and a live management menu.

---

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

---

## 📦 Installation

```text
[p]repo add ToHubLab-Cogs https://github.com/ToHubLab/ToHubLab-Cogs
```

```text
[p]cog install ToHubLab-Cogs verification
```

```text
[p]load verification
```

---

## 🚀 Quick Start

```text
[p]verifysetup start
```

Follow the wizard:

1. **Select the verification channel**
2. **Select the role** to grant on success
3. **Choose a mode**:
   - 📝 *Send new message* — bot posts a message with a **Verify** button
   - 💬 *Use existing message* — pick a message ID and a reaction emoji
4. **Confirm & Create**

Then verify your setup with:

```text
[p]verifysetup status
```

---

## 🛠️ Commands

| Command | Description |
|---|---|
| `[p]verifysetup start` | Runs the interactive setup wizard |
| `[p]verifysetup status` | Shows the current config (auto-deletes after 8s) |
| `[p]verifysetup reset` | Resets the setup and cleans up everything |
| `[p]verifysetup cleanup [#channel]` | Deletes orphaned verification messages |
| `[p]verifysetup reloaddata` | Reloads `verification_data.json` from disk |
| `[p]verifysetup sync` | Manually runs the reaction/role sync |
| `[p]verifysetup verified` | Paginated list of verified users (ephemeral, 5 per page) |
| `[p]verifymenu` | Opens the interactive management menu |

All commands require **Manage Server** permission.

---

## 📁 Project Structure

The cog is organized into focused modules with clear responsibilities.
The main cog file handles commands and events, while every helper lives
in its own file under `helpers/`.

```text
verification/
├── __init__.py                 Package entry point
├── info.json                   Cog metadata for Red
├── verification.py             Main cog (commands, listeners, sync)
├── README.md                   This file
├── LICENSE                     MIT License
└── helpers/
    ├── __init__.py             Centralized re-exports
    ├── constants.py            All constants and default data
    ├── utils.py                Emoji normalization + challenge generator
    ├── embeds.py               All embed builders
    ├── data_manager.py         JSON file I/O (data + verified users)
    ├── modals.py               All modals
    ├── verify_views.py         User-facing views
    ├── setup_views.py          Setup wizard and its views
    └── menu_views.py           .verifymenu views
```

### Why modular?

- **Single Responsibility** — each file handles one concern
- **Easier to extend** — adding an embed only touches `embeds.py`
- **No circular imports** — helpers import strictly what they need
- **Testable in isolation** — every helper can be unit-tested
- **Cleaner cog** — `verification.py` stays small (~500 lines)

---

## 📁 Data Files

On first load, the cog creates two files in its data directory:

```text
<Red-Daten-Ordner>/Verification/verification_data.json
<Red-Daten-Ordner>/Verification/verified_users.json
```

### `verification_data.json`

Contains all customizable content. Edit it and run
`[p]verifysetup reloaddata` to apply changes.

```json
{
    "emoji_options": [
        ["✅", "Check Mark Button"],
        ["👍", "Thumbs Up"]
    ],
    "text_challenges": [
        ["Write 'Color' to verify", "color"],
        ["Type 'ToHubLab' to verify", "tohublab"]
    ],
    "security_questions": [
        ["How many letters are in the word 'verify'?", "6"],
        ["What color is the sky on a clear day?", "blue"]
    ]
}
```

### `verified_users.json`

A read-only mirror of verified user IDs per guild. It is written
automatically after each successful verification.

```json
{
    "1234567890": [111111111111111111, 222222222222222222]
}
```

---

## 🔑 Requirements

The bot needs the following permissions in the verification channel:

| Permission | Why |
|---|---|
| **Send Messages** | Post verification messages |
| **Embed Links** | Embed support |
| **Add Reactions** | Reaction mode |
| **Read Message History** | Reaction mode + cleanup |
| **Manage Messages** | Delete old setup/status messages |
| **Manage Roles** | Grant the verification role |

> ⚠️ The verification role must be **below** the bot's highest role
> in the server role hierarchy.

---

## 🎯 How It Works

### Button Mode

1. User clicks the **Verify** button on the verification message
2. A modal opens with a math or text challenge
3. Correct answer → role granted
4. Wrong answer → failed attempt counted
5. After 3 wrong answers → 10-minute lockout with progress bar

### Reaction Mode

1. User reacts with the configured emoji
2. Bot posts a short prompt in the same channel with an **Enter Answer** button
3. Button click opens the challenge modal
4. Correct answer → role granted and reaction kept
5. Wrong answer → reaction removed so the user can retry
6. Cancel or timeout → reaction removed automatically

### Security Check

If an admin manually removes the verification role from a verified user,
the next time they try to verify they must first answer **two security
questions**. On success, they are removed from the verified list and can
run through verification again.

### Background Sync

Every 5 minutes the cog reconciles the reaction list and the role list:

| Situation | Action |
|---|---|
| Member has the role but **no reaction** | Role is removed |
| Member has a reaction but **no role** and is on the verified list | Reaction is removed |
| Member has a reaction but **no role** and is mid-verification | Nothing (in progress) |

This prevents drift between the reaction counter and the actual role
assignment.

---

## 🎨 Customization

Everything user-facing can be customized without touching the code:

- **Emojis** — add or remove entries in `emoji_options`
- **Text challenges** — add custom prompts in `text_challenges`
- **Security questions** — add your own questions in `security_questions`
- **Timings** — edit the constants at the top of `helpers/constants.py`
- **Embed colors** — adjust in `helpers/embeds.py`

After editing `verification_data.json`, run:

```text
[p]verifysetup reloaddata
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---|---|
| Users can't verify | Check that the verification role is **below** the bot's role |
| Reaction mode not working | Make sure the bot has **Add Reactions** + **Read Message History** |
| Counter stays at 1 | Run `[p]verifysetup sync` to reconcile |
| Messages not deleting | Bot needs **Manage Messages** |
| Data file not reloading | Run `[p]verifysetup reloaddata` |

---

## 🐙 Credits

Made by [ToHubLab](https://github.com/ToHubLab)

- **GitHub** — [github.com/ToHubLab](https://github.com/ToHubLab)
- **Support & Updates** — [discord.finn-bot.rf.gd](http://discord.finn-bot.rf.gd)

---

## 📜 License

MIT — see [LICENSE](LICENSE) for details.
