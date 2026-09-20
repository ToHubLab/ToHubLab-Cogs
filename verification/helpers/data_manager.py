"""Handles reading/writing the JSON data files."""

import json
from pathlib import Path

from .constants import (
    DATA_FILE_NAME,
    VERIFIED_FILE_NAME,
    DEFAULT_EMOJI_OPTIONS,
    DEFAULT_TEXT_CHALLENGES,
    DEFAULT_SECURITY_QUESTIONS,
)


class DataManager:
    """Loads and saves the cog's JSON files."""

    def __init__(self, data_path: Path):
        self.data_path = Path(data_path)
        self.config_file: Path = self.data_path / DATA_FILE_NAME
        self.verified_file: Path = self.data_path / VERIFIED_FILE_NAME

        self.emoji_options: list[tuple[str, str]] = []
        self.text_challenges: list[tuple[str, str]] = []
        self.security_questions: list[tuple[str, str]] = []

    # ── Public API ───────────────────────────────────────
    def ensure_dir(self) -> None:
        try:
            self.data_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def write_defaults(self) -> None:
        default_data = {
            "emoji_options": DEFAULT_EMOJI_OPTIONS,
            "text_challenges": DEFAULT_TEXT_CHALLENGES,
            "security_questions": DEFAULT_SECURITY_QUESTIONS,
        }
        try:
            self.config_file.write_text(
                json.dumps(default_data, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def read(self) -> None:
        try:
            data = json.loads(self.config_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}

        emoji_list = data.get("emoji_options") or DEFAULT_EMOJI_OPTIONS
        text_list = data.get("text_challenges") or DEFAULT_TEXT_CHALLENGES
        sec_list = data.get("security_questions") or DEFAULT_SECURITY_QUESTIONS

        self.emoji_options = [
            (str(p[0]), str(p[1])) for p in emoji_list
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]
        self.text_challenges = [
            (str(p[0]), str(p[1])) for p in text_list
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]
        self.security_questions = [
            (str(p[0]), str(p[1])) for p in sec_list
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]

        # Fallbacks
        if not self.emoji_options:
            self.emoji_options = [(a, b) for a, b in DEFAULT_EMOJI_OPTIONS]
        if not self.text_challenges:
            self.text_challenges = [(a, b) for a, b in DEFAULT_TEXT_CHALLENGES]
        if not self.security_questions:
            self.security_questions = [(a, b) for a, b in DEFAULT_SECURITY_QUESTIONS]

    def write_verified_users(self, guild_id: int, users: list[int]) -> None:
        try:
            raw = self.verified_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        data[str(guild_id)] = users
        try:
            self.verified_file.write_text(
                json.dumps(data, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass