# C Cog for Red-DiscordBot

A lightweight Red-DiscordBot cog that counts deleted messages, provides clean-up commands, a debug log channel, and live bilingual support (German / English) — all switchable per server without a bot restart.

## ✨ Features

| Feature | Description |
|---|---|
| 🗑️ **Delete Counter** | Counts every deleted message per server — including bulk deletes and manual purges |
| 🧹 **Clean-up Commands** | Delete a specific amount of messages or wipe an entire channel with `cclean` |
| ↩️ **Counter Reset** | Reset the deleted-message counter for the current server with `creset` |
| 📊 **Statistics** | View server stats, counter, and debug status via `cstats` |
| 🐛 **Debug Mode** | Forward all cog events to a dedicated log channel with a 2-second delay |
| 🌐 **Bilingual** | Switch between German and English live with `clang` — affects only this cog |
| ⚡ **Instant Language Switch** | No bot restart required — changes take effect immediately |
| 🔒 **Safe Counting** | Debounce logic prevents double counting between manual and bulk deletes |
| 📌 **Persistent Counter** | Counter is stored per guild and survives bot restarts |
| 🖼️ **Clean Embeds** | Themed embeds for info, stats, help, and credits |
| 🔗 **Credits & Links** | Built-in copyright page with a direct link to [ToHubLab on GitHub](https://github.com/ToHubLab) |
| 📋 **Help Overview** | Localized command list via `cb` — adapts to the configured language |
| 🔒 **Permission Checks** | Configuration commands are restricted to administrators / manage permissions |
| 🐳 **No Dependencies** | No extra Python packages required — works out of the box |

## 📦 Installation

```text
[p]repo add ToHubLab-Cogs https://github.com/ToHubLab/ToHubLab-Cogs
```
```text
[p]cog install ToHubLab-Cogs C
```
```text
[p]load C
```
```text
[p]cb
```