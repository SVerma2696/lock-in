"""
config.py
=========
This is the app's memory box — everything it remembers between one time you
open it and the next lives here.

The idea: nothing important is hard-baked into the screen code. The screen
just asks a `Config` object for answers, and `Config` is a simple wrapper
around a JSON file saved on your computer. That means you (or anyone) can
open `config.json` in a plain text editor, change a number, and the app will
use it the next time it starts.

Where the file lives
---------------------
Windows : C:\\Users\\<you>\\AppData\\Roaming\\Lock In\\config.json
macOS   : ~/Library/Application Support/Lock In/config.json
Linux   : ~/.config/Lock In/config.json

We do NOT save it next to the .py files on purpose. Once the app is packaged
into an .exe, that folder might not allow saving files into it, and we don't
want saving to quietly fail.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List

APP_NAME = "Lock In"


def app_data_dir() -> Path:
    """
    Find (or make) the folder where this app is allowed to save its files.

    We check exactly which operating system you're on so macOS and Linux
    each get their own normal spot, instead of getting lumped together.
    """
    if sys.platform == "win32":
        # Windows always sets this, but we have a backup just in case.
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        # Use the folder Linux users have chosen, if they picked one.
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    directory = base / APP_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


CONFIG_PATH = app_data_dir() / "config.json"
MODEL_PATH = app_data_dir() / "model.json"
LOG_PATH = app_data_dir() / "sessions.jsonl"
OBSERVATIONS_PATH = app_data_dir() / "observations.jsonl"


# --------------------------------------------------------------------------- #
# The starter "always block" and "always allow" lists
# --------------------------------------------------------------------------- #
# These are checked against the name of the program itself (like "discord.exe"),
# not the window title, because that name almost never changes or lies. These
# lists are the boss — the smart guessing model never gets to overrule them.
# Think of this as "things I already know for sure, no need to guess."

DEFAULT_BLOCKLIST: List[str] = [
    "discord.exe",
    "steam.exe",
    "steamwebhelper.exe",
    "epicgameslauncher.exe",
    "riotclientux.exe",
    "leagueclient.exe",
    "spotify.exe",           # take this out of the list if music helps you study
    "netflix.exe",
    "vlc.exe",
    "telegram.exe",
    "whatsapp.exe",
    "slack.exe",
    "roblox.exe",
    "minecraft.exe",
]

DEFAULT_ALLOWLIST: List[str] = [
    "code.exe",              # VS Code
    "devenv.exe",            # Visual Studio
    "pycharm64.exe",
    "idea64.exe",
    "python.exe",
    "pythonw.exe",
    "windowsterminal.exe",
    "powershell.exe",
    "cmd.exe",
    "winword.exe",
    "excel.exe",
    "powerpnt.exe",
    "onenote.exe",
    "acrobat.exe",
    "acrord32.exe",
    "sumatrapdf.exe",
    "obsidian.exe",
    "notepad.exe",
    "notepad++.exe",
    "matlab.exe",
    "explorer.exe",          # this runs your whole desktop — never block it
]


@dataclass
class Config:
    """
    Holds all the app's settings, with a safe default for each one.

    Because every setting has a default, even a missing or messed-up
    config.json still lets the app open and work, instead of crashing.
    """

    # --- How long each part of the timer lasts (in minutes) ---------------- #
    focus_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    blocks_until_long_break: int = 4      # focus rounds before a big break

    # --- What happens automatically ----------------------------------------- #
    auto_start_breaks: bool = True        # break starts right away
    auto_start_focus: bool = False        # you must press start to work again

    # --- Blocking rules ------------------------------------------------------ #
    enforcement_enabled: bool = True
    hard_mode: bool = False               # allows minimising + full-screen warning
    grace_seconds: int = 8                # a few free seconds before we react
    strike_interval_seconds: int = 12     # how often we get stricter
    strike_decay_seconds: int = 45        # good behavior needed to calm down
    lockdown_seconds: int = 15            # how long the full-screen warning stays up

    # --- Notifications ----------------------------------------------------- #
    sound_enabled: bool = True
    toast_enabled: bool = True

    # --- The guessing model -------------------------------------------------- #
    use_classifier: bool = True
    classifier_threshold: float = 0.80    # how sure it must be before blocking

    # Write down EVERY window seen during focus, not just the ones we blocked.
    # That way `train.py label` can also show you the sneaky distracting apps
    # the model let slide, not only the ones it wrongly flagged.
    record_observations: bool = True

    # --- Claude fallback (an optional helper) -------------------------------- #
    # Off unless you turn it on. When it's on, and the local model is UNSURE
    # about a window (below claude_confidence_floor), that one window title
    # gets sent to Claude to ask for a second opinion. This is the only time
    # anything leaves your computer, and only for the confusing cases — most
    # windows are judged right here and never go anywhere.
    claude_fallback_enabled: bool = False
    claude_model: str = "claude-haiku-4-5-20251001"
    # Below this much confidence, ask Claude instead of just shrugging.
    claude_confidence_floor: float = 0.65
    # Remember Claude's answer for a while, so we don't ask about the
    # same confusing window twice in one sitting.
    claude_cache_minutes: int = 30

    # --- The block/allow lists ------------------------------------------------ #
    blocklist: List[str] = field(default_factory=lambda: list(DEFAULT_BLOCKLIST))
    allowlist: List[str] = field(default_factory=lambda: list(DEFAULT_ALLOWLIST))

    # --- Looks --------------------------------------------------------------- #
    appearance: str = "dark"              # "dark" | "light" | "system"
    accent: str = "blue"                  # the app's color theme
    rider_theme: str = "Kamen Rider (1971)"   # which Kamen Rider's colors to use
    terminology: str = "professional"     # "professional" | "tokusatsu" — which words to use

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        """
        Read config.json, and use the normal defaults for anything it's missing.

        If the file has old or extra bits we don't recognize, we just ignore
        them instead of complaining — that way an older app never breaks on
        a config file saved by a newer one.
        """
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg

        try:
            raw: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # If the file got messed up somehow, just start fresh instead
            # of stopping you from studying.
            return cls()

        known = {f for f in cls.__dataclass_fields__}          # type: ignore[attr-defined]
        filtered = {k: v for k, v in raw.items() if k in known}
        return cls(**filtered)

    def save(self, path: Path = CONFIG_PATH) -> None:
        """Save the current settings to disk, written out neatly."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Little helpers the blocking logic uses
    # ------------------------------------------------------------------ #
    def normalised_blocklist(self) -> set[str]:
        """Give back the block list as lowercase names, quick to check against."""
        return {name.strip().lower() for name in self.blocklist if name.strip()}

    def normalised_allowlist(self) -> set[str]:
        return {name.strip().lower() for name in self.allowlist if name.strip()}

    def phase_seconds(self, phase_name: str) -> int:
        """Turn a phase's name into how many seconds it should last."""
        return {
            "focus": self.focus_minutes * 60,
            "short_break": self.short_break_minutes * 60,
            "long_break": self.long_break_minutes * 60,
        }[phase_name]