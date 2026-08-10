"""
notifier.py
===========
This file sends you alerts — pop-ups, sounds, or a banner in the app — when
you need a nudge back to work.

It tries three ways to get your attention, in order of how gentle they are:

  1. A real pop-up from your computer itself (winotify on Windows,
     `osascript` on macOS, `notify-send` on Linux if it's installed) —
     shows up quietly without stealing your focus.
  2. A sound (winsound on Windows, `afplay` on macOS, `paplay`/`aplay` on
     Linux) — simple, and hard to miss. Which exact sound plays depends
     on which Kamen Rider era is picked in Settings (Showa/Heisei/Reiwa)
     — see the tone/sound tables below.
  3. A little banner inside the app itself — always works, no matter what.

Why we don't just spam you
-----------------------------
It's tempting to fire off a pop-up every single second, but that's actually a
bad idea: you'd quickly learn to just dismiss them without reading, which
ruins the one channel this app depends on. Windows also starts squashing
pop-ups together after a few in a row anyway. So instead of MORE alerts, each
one just gets LOUDER than the last. The `enforcer.py` file already makes sure
we don't alert too often — this file's job is just to make each alert count.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from .config import app_data_dir
from .rider_themes import DEFAULT_RIDER_THEME, RIDER_THEMES
from .visuals import load_app_icon

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# --- The real Windows pop-up tool, if we have it ---------------------------- #
_winotify = None
if IS_WINDOWS:
    try:
        from winotify import Notification as _WinotifyNotification, audio as _winotify_audio  # type: ignore
        _winotify = True
    except ImportError:  # pragma: no cover
        _winotify = None

# --- The sound tool (built into Windows already) ----------------------------- #
_winsound = None
if IS_WINDOWS:
    try:
        import winsound as _winsound  # type: ignore
    except ImportError:  # pragma: no cover
        _winsound = None

# --- Checking once whether Linux has the little pop-up/sound programs ------- #
# `shutil.which` just looks to see if a program is installed, the same way
# typing its name at a terminal would find it. If a program isn't there, we
# skip it quietly instead of trying to run something that doesn't exist.
_HAS_NOTIFY_SEND = IS_LINUX and shutil.which("notify-send") is not None
_HAS_PAPLAY = IS_LINUX and shutil.which("paplay") is not None
_HAS_APLAY = IS_LINUX and shutil.which("aplay") is not None

# --- Sound cues, one flavor per Kamen Rider era --------------------------- #
# Picking a different era of Rider doesn't just repaint the app — the
# beeps and chimes sound a little different too:
#   Showa  — a plain, blunt two-tone alarm, like an old base siren.
#   Heisei — the original sound this app shipped with. Also the
#            fallback used if we're ever handed an era name we don't
#            recognise.
#   Reiwa  — a quicker, higher-pitched sequence, more "digital".
DEFAULT_ERA = "Heisei"

_WINDOWS_CHIME_TONES = {
    "Showa": [(440, 200), (440, 200)],
    "Heisei": [(880, 140), (1175, 220)],
    "Reiwa": [(1200, 80), (1500, 80), (1800, 120)],
}
_WINDOWS_ALERT_TONES = {
    "Showa": [(440, 180), (330, 180), (440, 220)],
    "Heisei": [(1000, 110), (760, 110), (1000, 160)],
    "Reiwa": [(1800, 70), (1400, 70), (1800, 70), (2200, 120)],
}

# These are all sound files that already come with macOS, so no extra
# download is needed — just a different built-in sound per era.
_MAC_CHIME_SOUND = {"Showa": "Basso", "Heisei": "Ping", "Reiwa": "Glass"}
_MAC_ALERT_SOUND = {"Showa": "Funk", "Heisei": "Sosumi", "Reiwa": "Hero"}

# A couple of common sound files that ship on most Linux desktops, most
# fitting first. We use whichever one of these actually exists on this
# computer — Linux desktops don't all install the same sound files.
_LINUX_CHIME_CANDIDATES = {
    "Showa": ["bell.oga", "dialog-warning.oga"],
    "Heisei": ["dialog-warning.oga", "bell.oga"],
    "Reiwa": ["message.oga", "complete.oga", "bell.oga"],
}
_LINUX_ALERT_CANDIDATES = {
    "Showa": ["dialog-warning.oga", "bell.oga"],
    "Heisei": ["dialog-warning.oga", "bell.oga"],
    "Reiwa": ["complete.oga", "message.oga", "bell.oga"],
}
_LINUX_SOUND_DIR = "/usr/share/sounds/freedesktop/stereo"


def _square_icon_path() -> Optional[str]:
    """
    Give back a file path to the app's own picture, saved as a square.

    Pop-up notifications need an actual file on disk, not a picture
    already sitting in memory — so the first time this is asked for, we
    save one to the app's own settings folder (the same place
    config.json lives) and just reuse that file every time after.
    """
    path = app_data_dir() / "app_icon_square.png"
    if not path.exists():
        icon = load_app_icon()
        if icon is None:
            return None
        try:
            icon.save(path)
        except Exception:
            return None
    return str(path)


class Notifier:
    """
    Sends alerts and doesn't wait around for anything to happen after.

    Every method here is safe to call from anywhere in the app and will never
    crash — a notification failing to show up is not a good enough reason to
    interrupt someone's study session.
    """

    def __init__(self, config, app_name: str = "Lock In") -> None:
        self.config = config
        self.app_name = app_name
        # ui.py fills this in so we can fall back to showing an in-app banner.
        self.banner_callback = None

    # ------------------------------------------------------------------ #
    # What other files use to send alerts
    # ------------------------------------------------------------------ #
    def notify(self, title: str, body: str, urgency: str = "normal") -> None:
        """
        Send an alert. How loud it is depends on `urgency`.

        urgency: "low" (quiet banner only) | "normal" (pop-up) | "high" (pop-up + sound)
        """
        if self.banner_callback is not None:
            try:
                self.banner_callback(title, body, urgency)
            except Exception:
                pass

        if urgency != "low" and self.config.toast_enabled:
            self._toast(title, body, urgency)

        if urgency == "high" and self.config.sound_enabled:
            self.alert_sound()

    def phase_chime(self, starting_phase_label: str) -> None:
        """A soft, friendly chime when a new phase (focus or break) starts."""
        if not self.config.sound_enabled:
            return
        era = self._era()
        if IS_WINDOWS and _winsound is not None:
            self._beep_sequence(_WINDOWS_CHIME_TONES.get(era, _WINDOWS_CHIME_TONES[DEFAULT_ERA]))
        elif IS_MACOS:
            name = _MAC_CHIME_SOUND.get(era, _MAC_CHIME_SOUND[DEFAULT_ERA])
            self._play_mac_sound(f"/System/Library/Sounds/{name}.aiff")
        elif _HAS_PAPLAY or _HAS_APLAY:
            candidates = _LINUX_CHIME_CANDIDATES.get(era, _LINUX_CHIME_CANDIDATES[DEFAULT_ERA])
            self._play_linux_sound(candidates)

    def alert_sound(self) -> None:
        """A sharper sound for when you need a nudge back to work."""
        if not self.config.sound_enabled:
            return
        era = self._era()
        if IS_WINDOWS and _winsound is not None:
            self._beep_sequence(_WINDOWS_ALERT_TONES.get(era, _WINDOWS_ALERT_TONES[DEFAULT_ERA]))
        elif IS_MACOS:
            name = _MAC_ALERT_SOUND.get(era, _MAC_ALERT_SOUND[DEFAULT_ERA])
            self._play_mac_sound(f"/System/Library/Sounds/{name}.aiff", repeat=2)
        elif _HAS_PAPLAY or _HAS_APLAY:
            candidates = _LINUX_ALERT_CANDIDATES.get(era, _LINUX_ALERT_CANDIDATES[DEFAULT_ERA])
            self._play_linux_sound(candidates, repeat=2)

    def _era(self) -> str:
        """
        Which Kamen Rider era (Showa/Heisei/Reiwa) the currently-picked
        Rider is from — this is what actually picks the sound cues.

        If the saved Rider name isn't one we recognise, we quietly fall
        back to the very first Rider instead of crashing.
        """
        theme = RIDER_THEMES.get(self.config.rider_theme, RIDER_THEMES[DEFAULT_RIDER_THEME])
        return theme.era

    # ------------------------------------------------------------------ #
    # The behind-the-scenes bits
    # ------------------------------------------------------------------ #
    def _toast(self, title: str, body: str, urgency: str) -> None:
        """Show a real pop-up if we have a way to on this computer; otherwise do nothing."""
        if IS_WINDOWS:
            if not _winotify:
                return
            try:
                toast = _WinotifyNotification(
                    app_id=self.app_name,
                    title=title,
                    msg=body,
                    duration="short" if urgency == "normal" else "long",
                    icon=_square_icon_path() or "",
                )
                if urgency == "high":
                    toast.set_audio(_winotify_audio.LoopingAlarm2, loop=False)
                toast.show()
            except Exception:
                pass
            return

        if IS_MACOS:
            try:
                def esc(text: str) -> str:
                    # A quote mark inside the message would otherwise
                    # break the little script we hand to macOS — this
                    # puts a backslash in front of it so macOS reads it
                    # as a plain character instead.
                    return text.replace("\\", "\\\\").replace('"', '\\"')
                script = f'display notification "{esc(body)}" with title "{esc(title)}"'
                subprocess.run(["osascript", "-e", script], timeout=2, capture_output=True)
            except Exception:
                pass
            return

        if _HAS_NOTIFY_SEND:
            try:
                args = ["notify-send"]
                icon_path = _square_icon_path()
                if icon_path:
                    args += ["--icon", icon_path]
                args += [title, body]
                subprocess.run(args, timeout=2, capture_output=True)
            except Exception:
                pass

    def _beep_sequence(self, tones) -> None:
        """
        Play a little series of beeps, on their own throwaway background thread.

        Playing a beep pauses everything else until it finishes, so if we did
        this on the app's main thread, the timer would visibly freeze for a
        moment while the sound plays. Doing it on the side avoids that.
        """
        def run() -> None:
            try:
                for freq, ms in tones:
                    _winsound.Beep(freq, ms)  # type: ignore[union-attr]
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _play_mac_sound(self, path: str, repeat: int = 1) -> None:
        """Play one of the sound files that already comes with macOS."""
        def run() -> None:
            try:
                for _ in range(repeat):
                    subprocess.run(["afplay", path], timeout=3, capture_output=True)
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _play_linux_sound(self, candidates: list, repeat: int = 1) -> None:
        """Play whichever Linux system sound we can actually find on this computer."""
        sound = next(
            (f"{_LINUX_SOUND_DIR}/{name}" for name in candidates
             if Path(f"{_LINUX_SOUND_DIR}/{name}").exists()),
            None,
        )
        if sound is None:
            return
        player = "paplay" if _HAS_PAPLAY else "aplay"

        def run() -> None:
            try:
                for _ in range(repeat):
                    subprocess.run([player, sound], timeout=3, capture_output=True)
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()