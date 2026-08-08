"""
monitor.py
==========
This file watches which window you have open right now, and does the two
little things the enforcer needs done: shrink a window away, or bring our
own window to the front.

What works where
-------------------
Windows : works fully, using two helper toolkits. This is the main platform
          this app is built for.
macOS   : can only look, not touch. Shrinking windows away is turned off,
          because macOS requires extra permission for that, which isn't
          worth asking for just for this.
Linux   : can only look, and only if a small tool called `xdotool` happens
          to already be installed.
Anywhere else, or if a needed piece is missing: the app just says "unknown
window" forever and quietly becomes a plain (still very good!) Pomodoro
timer, with no blocking.

Nearly everything here is wrapped in a safety net (try/except), because
asking Windows "what window is this?" can be surprisingly unreliable — a
window can close in the split second between us noticing it and asking it
questions. Without that safety net, one weird moment could silently turn off
all blocking without ever telling you.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from typing import Callable, Optional

from .enforcer import WindowInfo

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"

# --------------------------------------------------------------------------- #
# These toolkits are optional. We try to load them once here, and set a
# simple yes/no flag so the rest of the app can just check
# `monitor.BACKEND_AVAILABLE` instead of dealing with import errors itself.
# --------------------------------------------------------------------------- #
_win32gui = _win32process = _win32con = None
_psutil = None

if IS_WINDOWS:
    try:
        import win32gui as _win32gui          # type: ignore
        import win32process as _win32process  # type: ignore
        import win32con as _win32con          # type: ignore
    except ImportError:  # pragma: no cover - depends on install
        _win32gui = _win32process = _win32con = None

try:
    # psutil turns a process ID number into a program name. Windows already
    # used it; now Linux uses it too, so block/allow lists work there.
    import psutil as _psutil              # type: ignore
except ImportError:  # pragma: no cover - depends on install
    _psutil = None

BACKEND_AVAILABLE = _win32gui is not None or IS_MACOS or sys.platform.startswith("linux")


# --------------------------------------------------------------------------- #
# Figuring out which window is in front right now
# --------------------------------------------------------------------------- #
def _active_window_windows() -> WindowInfo:
    """Ask Windows which window is in front, and which program owns it."""
    assert _win32gui is not None  # the caller already checked this exists
    try:
        hwnd = _win32gui.GetForegroundWindow()
        if not hwnd:
            return WindowInfo()

        title = _win32gui.GetWindowText(hwnd) or ""

        # This gives back two numbers; we only care about the second one.
        _, pid = _win32process.GetWindowThreadProcessId(hwnd)

        process_name = ""
        if pid and _psutil is not None:
            try:
                process_name = _psutil.Process(pid).name()
            except Exception:
                # This happens for protected system programs we're not
                # allowed to look at — just leave the name blank.
                process_name = ""

        return WindowInfo(process_name=process_name, title=title, pid=pid, handle=hwnd)
    except Exception:
        return WindowInfo()


def _active_window_macos() -> WindowInfo:
    """
    Ask the operating system for the name of the app in front, and its
    window's title.

    The first time this runs, macOS will ask you to grant permission. If you
    say no, we just get nothing back and return an empty WindowInfo.
    """
    script = (
        'tell application "System Events"\n'
        '  set frontApp to name of first application process whose frontmost is true\n'
        '  try\n'
        '    set winTitle to name of front window of application process frontApp\n'
        '  on error\n'
        '    set winTitle to ""\n'
        '  end try\n'
        '  return frontApp & "|" & winTitle\n'
        'end tell'
    )
    try:
        out = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        app, _, title = out.partition("|")
        return WindowInfo(process_name=app.lower(), title=title)
    except Exception:
        return WindowInfo()


def _active_window_linux() -> WindowInfo:
    """
    Try to read the active window using xdotool. Gives back nothing if
    it's not installed.

    Also asks for the window's process name, the same way the Windows
    side does — first xdotool tells us the window's ID number (its PID),
    then psutil turns that number into a program name like "discord".
    Without this, block/allow lists could only ever catch a window by
    its title text, never by its exact program name.
    """
    try:
        title = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()

        process_name = ""
        try:
            pid_text = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowpid"],
                capture_output=True, text=True, timeout=2,
            ).stdout.strip()
            if pid_text and _psutil is not None:
                process_name = _psutil.Process(int(pid_text)).name()
        except Exception:
            # Some windows don't have a PID we can find. That's fine —
            # we just won't know the program name for this one window.
            process_name = ""

        return WindowInfo(process_name=process_name, title=title)
    except Exception:
        return WindowInfo()


def get_active_window() -> WindowInfo:
    """The one function everyone calls — picks the right method for your computer. Never crashes."""
    if _win32gui is not None:
        return _active_window_windows()
    if IS_MACOS:
        return _active_window_macos()
    if sys.platform.startswith("linux"):
        return _active_window_linux()
    return WindowInfo()


# --------------------------------------------------------------------------- #
# Doing things to windows
# --------------------------------------------------------------------------- #
def minimize_window(handle: Optional[int]) -> bool:
    """
    Shrink the currently active window down, out of the way. Returns True
    if it probably worked.

    We shrink it rather than fully hide it — a fully hidden window disappears
    from the taskbar with no visible way to bring it back, which would be
    genuinely annoying if we ever guessed wrong about a window.

    On Windows we shrink the exact window `handle` points to. macOS and
    Linux don't give us a handle like that here, so both instead shrink
    whatever window is active right now — which is fine, since we only
    ever call this the instant after we've checked that window is still
    the one on screen.
    """
    if IS_WINDOWS:
        if _win32gui is None or not handle:
            return False
        try:
            _win32gui.ShowWindow(handle, _win32con.SW_MINIMIZE)
            return True
        except Exception:
            return False

    if IS_MACOS:
        # This copies the keyboard shortcut a person would press
        # (Cmd + M) to shrink whatever window is in front. macOS will
        # ask for "Accessibility" permission the first time an app tries
        # to do this — until that's allowed, this quietly does nothing.
        try:
            script = 'tell application "System Events" to keystroke "m" using command down'
            result = subprocess.run(
                ["osascript", "-e", script], timeout=2, capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    if sys.platform.startswith("linux"):
        # This only works on the older X11 kind of Linux desktop, not the
        # newer Wayland kind — there's no tool like xdotool for Wayland
        # yet. On Wayland this will just quietly do nothing.
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "windowminimize"],
                timeout=2, capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    return False


def bring_to_front(handle: Optional[int]) -> bool:
    """
    Bring our own app's window to the front, above everything else.

    Windows normally won't let a background app just jump to the front — it's
    a safety rule, so this can genuinely fail sometimes. The trick below
    (briefly marking the window "always on top", then turning that back off)
    is the standard workaround: it's enough to raise the window without
    permanently pinning it above everything forever.
    """
    if _win32gui is None or not handle:
        return False
    try:
        # First un-shrink it — bringing a shrunk window to the front doesn't work otherwise.
        _win32gui.ShowWindow(handle, _win32con.SW_RESTORE)
        try:
            _win32gui.SetForegroundWindow(handle)
        except Exception:
            _win32gui.SetWindowPos(
                handle, _win32con.HWND_TOPMOST, 0, 0, 0, 0,
                _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE | _win32con.SWP_SHOWWINDOW,
            )
            _win32gui.SetWindowPos(
                handle, _win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE | _win32con.SWP_SHOWWINDOW,
            )
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# The background checker
# --------------------------------------------------------------------------- #
class ActiveWindowMonitor:
    """
    Checks the active window over and over, on its own background thread —
    separate from the main app, so it never freezes the screen.

    The callback runs on THAT separate thread, not the screen's own thread.
    Because of that, `ui.py` doesn't do any real work inside the callback —
    it just drops the info into a safe waiting line (`queue.Queue`) for the
    main screen to pick up later. This is the standard safe way to mix a
    background thread with a graphical window, and skipping it is usually
    why an app's window randomly freezes.
    """

    def __init__(self, callback: Callable[[WindowInfo], None], interval: float = 1.0) -> None:
        self._callback = callback
        self.interval = interval
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._paused.set()   # start paused — nothing to check until a focus block begins

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Start the background thread. Safe to call more than once."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="window-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Tell the background thread to stop, and wait a moment for it to finish."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def resume(self) -> None:
        """Start sending updates again (called when a focus block begins)."""
        self._paused.clear()

    def pause(self) -> None:
        """Stop sending updates (during breaks, pauses, or idle time)."""
        self._paused.set()

    @property
    def is_active(self) -> bool:
        return not self._paused.is_set()

    # ------------------------------------------------------------------ #
    def _run(self) -> None:
        """What the background thread actually does: check, send, wait, repeat."""
        while not self._stop.is_set():
            if not self._paused.is_set():
                try:
                    self._callback(get_active_window())
                except Exception:
                    # If the callback breaks, blocking must not silently stop working.
                    pass
            # Waiting this way lets stop() interrupt the wait instantly,
            # instead of always waiting out the full second.
            self._stop.wait(self.interval)