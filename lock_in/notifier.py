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
     Linux) — simple, and hard to miss.
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

# A couple of common sound files that ship on most Linux desktops. We use
# whichever one of these actually exists on this computer.
_LINUX_SOUND_CANDIDATES = [
    "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga",
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
]


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
        if IS_WINDOWS and _winsound is not None:
            self._beep_sequence([(880, 140), (1175, 220)])
        elif IS_MACOS:
            self._play_mac_sound("/System/Library/Sounds/Ping.aiff")
        elif _HAS_PAPLAY or _HAS_APLAY:
            self._play_linux_sound()

    def alert_sound(self) -> None:
        """A sharper sound for when you need a nudge back to work."""
        if not self.config.sound_enabled:
            return
        if IS_WINDOWS and _winsound is not None:
            self._beep_sequence([(1000, 110), (760, 110), (1000, 160)])
        elif IS_MACOS:
            self._play_mac_sound("/System/Library/Sounds/Sosumi.aiff", repeat=2)
        elif _HAS_PAPLAY or _HAS_APLAY:
            self._play_linux_sound(repeat=2)

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
                subprocess.run(["notify-send", title, body], timeout=2, capture_output=True)
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

    def _play_linux_sound(self, repeat: int = 1) -> None:
        """Play whichever Linux system sound we can actually find on this computer."""
        sound = next((p for p in _LINUX_SOUND_CANDIDATES if Path(p).exists()), None)
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