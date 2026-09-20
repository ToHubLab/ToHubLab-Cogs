"""All constants and default data for the Verification cog."""

# ── General ──────────────────────────────────────────────
DEFAULT_VERIFICATION_EMOJI = "✅"
VERIFICATION_EMBED_TITLE = "🔐 Server Verification"

# ── Timings ──────────────────────────────────────────────
SETUP_AUTO_DELETE_SECONDS = 8
CANCEL_AUTO_DELETE_SECONDS = 3
MENU_TIMEOUT_SECONDS = 180
SYNC_INTERVAL_MINUTES = 5
CHALLENGE_TIMEOUT_SECONDS = 300
VERIFIED_PAGE_SIZE = 5

# ── Credit ───────────────────────────────────────────────
CREDIT_NAME = "ToHubLab"
CREDIT_URL = "https://github.com/ToHubLab"
CREDIT_LINE = f"\n\n-# Made by [{CREDIT_NAME}]({CREDIT_URL})"

# ── Data files ───────────────────────────────────────────
DATA_FILE_NAME = "verification_data.json"
VERIFIED_FILE_NAME = "verified_users.json"

# ── Default content (written to data file on first load) ─
DEFAULT_EMOJI_OPTIONS = [
    ["✅", "Check Mark Button"], ["✔️", "Check Mark"], ["☑️", "Check Box with Check"],
    ["👍", "Thumbs Up"], ["👋", "Waving Hand"], ["🙌", "Raising Hands"],
    ["🤝", "Handshake"], ["🟢", "Green Circle"], ["🔵", "Blue Circle"],
    ["🟡", "Yellow Circle"], ["🟣", "Purple Circle"], ["🟠", "Orange Circle"],
    ["🔴", "Red Circle"], ["⚪", "White Circle"], ["⚫", "Black Circle"],
    ["🔒", "Locked"], ["🔓", "Unlocked"], ["🎉", "Party Popper"],
    ["⭐", "Star"], ["🌟", "Glowing Star"], ["💫", "Dizzy"],
    ["🚀", "Rocket"], ["🎯", "Direct Hit"], ["🛡️", "Shield"],
]

DEFAULT_TEXT_CHALLENGES = [
    ["Write 'Color' to verify", "color"],
    ["Type 'Verify' to verify", "verify"],
    ["Write 'Human' to verify", "human"],
    ["Type 'ToHubLab' to verify", "tohublab"],
    ["Write 'Blue' to verify", "blue"],
    ["Type 'Hello' to verify", "hello"],
    ["Write 'Purple' to verify", "purple"],
    ["Type 'Apple' to verify", "apple"],
    ["Write 'Yes' to verify", "yes"],
    ["Type 'Ready' to verify", "ready"],
    ["Write 'Discord' to verify", "discord"],
    ["Type 'Welcome' to verify", "welcome"],
]

DEFAULT_SECURITY_QUESTIONS = [
    ["How many letters are in the word 'verify'?", "6"],
    ["What color is the sky on a clear day?", "blue"],
    ["What is 2 + 2?", "4"],
    ["Type the word 'confirm'", "confirm"],
    ["What color is grass?", "green"],
    ["Type the number seven", "7"],
    ["How many days are in a week?", "7"],
    ["What color is snow?", "white"],
]