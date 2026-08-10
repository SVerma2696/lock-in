"""
enforcer.py
===========
This file decides what to do when you drift off and start doing something
else instead of studying.

It has two jobs, kept separate on purpose:

  1. `judge()`  — is the window you're looking at okay right now, or not?
  2. `update()` — given that answer, and how long it's been going on, what
                  should we actually DO about it?

Neither of these two functions touches your screen or your computer directly.
`ui.py` takes the answer and does the actual work (like minimizing a window).
That split means we can test all of this decision-making without needing a
real screen at all.

The step-by-step escalation
------------------------------
Soft mode (the default — hard_mode is off):
    0-8 seconds on a blocked app .. do nothing (maybe you're about to close it)
    first time ...................... WARN  (a gentle pop-up: come back)
    every time after that ........... NAG   (pop-up + sound, a bit louder)

Hard mode (you turned it on): no warnings first — it acts right away.
    0-8 seconds on a blocked app .. do nothing (maybe you're about to close it)
    first time ...................... MINIMIZE  (window shrinks away, the
                                                   timer comes to the front)
    every time after that ........... LOCKDOWN   (whole screen covered for a bit)

If you behave for a while (`strike_decay_seconds`), one of these "strikes"
goes away. So one slip-up early on doesn't leave you one click away from a
full lockdown twenty minutes later.

A note about "trap me so I can't leave"
-------------------------------------------
There's no safe, allowed way for a normal app on Windows to truly stop you
from switching to another window — and that's a good thing. The tricks that
COULD do that are the same tricks malware uses, they need special permission,
and they can freeze your whole computer if something goes wrong. So instead
of trying to trap you, this app makes wandering off annoying and hard to do
without noticing — which is really the actual problem. Every single step,
even the full-screen LOCKDOWN, always has a visible way to get out. An app
that can trap you is an app you'd delete the first time it messes up during
something important.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from .classifier import DISTRACTION, STUDY, NaiveBayesClassifier


class Action(str, Enum):
    """The steps we can take, from "do nothing" to "loudest possible"."""

    NONE = "none"
    WARN = "warn"
    NAG = "nag"
    MINIMIZE = "minimize"
    LOCKDOWN = "lockdown"


class Reason(str, Enum):
    """Why a window got the answer it did — shown in the activity list."""

    ALLOWLIST = "allowlist"
    BLOCKLIST = "blocklist"
    CLASSIFIER = "classifier"
    CLAUDE = "claude"
    UNKNOWN = "unknown"
    NOT_FOCUSING = "not_focusing"


@dataclass
class Verdict:
    """The answer we gave for one single window."""

    blocked: bool
    reason: Reason
    confidence: float = 1.0
    detail: str = ""


@dataclass
class WindowInfo:
    """
    Whatever we could find out about the window you're currently looking at.

    `handle` is a special Windows ID number when we have one, or nothing
    otherwise. This file never opens or pokes at it directly — it just
    passes it along so the screen code can use it later.
    """

    process_name: str = ""
    title: str = ""
    pid: int = 0
    handle: Optional[int] = None

    @property
    def text(self) -> str:
        """The title and program name mashed together, for the guessing model."""
        return f"{self.title} {self.process_name}".strip()

    @property
    def display(self) -> str:
        """A short, friendly label, like 'discord.exe — general #chat'."""
        title = self.title if len(self.title) <= 60 else self.title[:57] + "..."
        if self.process_name and title:
            return f"{self.process_name} — {title}"
        return self.process_name or title or "unknown window"


def judge(
    window: WindowInfo,
    config,
    model: Optional[NaiveBayesClassifier] = None,
    claude=None,
) -> Verdict:
    """
    Decide whether `window` is okay to have open during a focus block.

    We always check things in this exact order:

        allow list  >  block list  >  our model (if sure)  >  Claude  >  allowed

    The lists you set yourself always win. If you put chrome.exe on the allow
    list, no guessing model — ours or Claude's — gets to overrule that. A
    tool that ignores what you told it stops being trustworthy right away.

    `claude`, if you pass one in, is a `ClaudeFallback`. We only ask it when
    our own model isn't confident (below `classifier_threshold`) — and even
    then, this function only checks if we already have a remembered answer,
    it never waits on the internet itself. If there's no remembered answer
    yet, we just use our own model's "not sure" answer for now; the caller
    (`ui.py`) is the one that quietly asks Claude in the background so an
    answer is ready by the next check.

    If we couldn't read a program's name at all (some programs block that
    when they're running "as administrator" and we aren't), we still try
    the allow/block lists a second way — by checking the window's title
    text for the program's name — before giving up and asking the model.
    """
    def _strip_exe(name: str) -> str:
        # Windows process names end in ".exe"; macOS and Linux ones don't.
        # Chopping it off both sides before comparing means one block/allow
        # list works the same on every computer, not just Windows.
        return name[:-4] if name.endswith(".exe") else name

    process = (window.process_name or "").strip().lower()
    process_bare = _strip_exe(process)
    allowlist_bare = {_strip_exe(name) for name in config.normalised_allowlist()}
    blocklist_bare = {_strip_exe(name) for name in config.normalised_blocklist()}

    if process_bare and process_bare in allowlist_bare:
        return Verdict(False, Reason.ALLOWLIST, 1.0, f"{process} is allow-listed")

    if process_bare and process_bare in blocklist_bare:
        return Verdict(True, Reason.BLOCKLIST, 1.0, f"{process} is block-listed")

    # Sometimes we can't find out a window's program name at all — some
    # programs (like Steam, if it's running "as administrator") block that
    # kind of question from a program that isn't also running as admin. When
    # that happens, take a second guess: check if the window's title itself
    # contains the name of a listed program, since most apps put their own
    # name in their title bar somewhere.
    title = (window.title or "").strip().lower()
    if not process and title:
        for allowed in config.normalised_allowlist():
            name = allowed[:-4] if allowed.endswith(".exe") else allowed
            if name and name in title:
                return Verdict(False, Reason.ALLOWLIST, 1.0,
                               f"title looks like allow-listed {allowed}")
        for blocked in config.normalised_blocklist():
            name = blocked[:-4] if blocked.endswith(".exe") else blocked
            if name and name in title:
                return Verdict(True, Reason.BLOCKLIST, 1.0,
                               f"title looks like block-listed {blocked}")

    local_verdict: Optional[Verdict] = None
    if config.use_classifier and model is not None and window.text:
        label, confidence = model.predict(window.text)
        if label == DISTRACTION and confidence >= config.classifier_threshold:
            return Verdict(True, Reason.CLASSIFIER, confidence,
                           f"model: distraction ({confidence:.0%})")
        if label == STUDY and confidence >= config.classifier_threshold:
            return Verdict(False, Reason.CLASSIFIER, confidence,
                           f"model: study ({confidence:.0%})")
        # Not confident either way — this is exactly the confusing case
        # Claude is meant to help with. Keep this answer as a backup in
        # case Claude doesn't have a remembered answer either.
        local_verdict = Verdict(False, Reason.CLASSIFIER, confidence,
                                f"model: unsure ({confidence:.0%})")

    if claude is not None and getattr(config, "claude_fallback_enabled", False) and window.text:
        cached = claude.peek(window.text)
        if cached is not None and cached.source in ("claude", "cache"):
            blocked = cached.label == DISTRACTION
            return Verdict(blocked, Reason.CLAUDE, cached.confidence,
                           f"claude: {cached.label} ({cached.confidence:.0%})")

    if local_verdict is not None:
        return local_verdict

    # We don't recognize this window and no model had an opinion — just
    # leave the user alone.
    return Verdict(False, Reason.UNKNOWN, 0.5, "not recognised — allowed")


class Enforcer:
    """
    Keeps track of how "in trouble" you are, over time.

    You feed it one answer every second through `update()`, and it tells you
    the one thing to do right now (usually "nothing"). It only fires each
    step once, not over and over — so you get one pop-up, not one every
    second.
    """

    def __init__(self, config, clock: Callable[[], float] = time.monotonic) -> None:
        self.config = config
        self._clock = clock

        self.strikes: int = 0
        self._blocked_since: Optional[float] = None    # when this visit to the app started
        self._last_strike_at: Optional[float] = None   # last time we stepped things up
        self._last_clean_at: Optional[float] = None    # when you got back to work
        self._current_key: Optional[str] = None        # which app you're currently on

    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        """Forget everything and start over — called whenever the phase changes."""
        self.strikes = 0
        self._blocked_since = None
        self._last_strike_at = None
        self._last_clean_at = None
        self._current_key = None

    @property
    def seconds_on_blocked_app(self) -> float:
        """How many seconds you've been on a blocked app, this one visit."""
        if self._blocked_since is None:
            return 0.0
        return self._clock() - self._blocked_since

    # ------------------------------------------------------------------ #
    def update(self, verdict: Verdict, window: WindowInfo) -> Action:
        """
        Move the ladder forward by one check and return what to do right now.

        Called about once every second, whenever we notice which window
        you're looking at.
        """
        now = self._clock()

        # --- You're doing fine ------------------------------------------- #
        if not verdict.blocked:
            self._blocked_since = None
            self._current_key = None
            if self._last_clean_at is None:
                self._last_clean_at = now
            # Take away one strike for every full "calm down" period of good work.
            elif self.strikes > 0 and now - self._last_clean_at >= self.config.strike_decay_seconds:
                self.strikes -= 1
                self._last_clean_at = now
            return Action.NONE

        # --- You're on a blocked app --------------------------------------- #
        self._last_clean_at = None
        key = f"{window.process_name}|{window.title}"

        # Hopping to a different blocked app gives you a fresh grace period,
        # but your strikes don't reset — jumping around to dodge the warning
        # shouldn't actually work.
        if key != self._current_key:
            self._current_key = key
            self._blocked_since = now

        elapsed = now - (self._blocked_since or now)

        # A short grace period — you might really be about to close it.
        if elapsed < self.config.grace_seconds:
            return Action.NONE

        # Don't step things up more than once per interval, even if we check every second.
        if self._last_strike_at is not None:
            if now - self._last_strike_at < self.config.strike_interval_seconds:
                return Action.NONE

        self._last_strike_at = now
        self.strikes += 1
        return self._action_for_strike(self.strikes)

    def _action_for_strike(self, strikes: int) -> Action:
        """Turn a strike count into an action, respecting the hard-mode switch."""
        if not self.config.hard_mode:
            # Soft mode never touches your windows — just a warning, then
            # a louder nag forever after that.
            if strikes <= 1:
                return Action.WARN
            return Action.NAG
        # Hard mode means what it says: no warnings first, it minimizes the
        # blocked window as soon as the grace period runs out, and covers
        # the screen if you keep going back to it after that.
        if strikes <= 1:
            return Action.MINIMIZE
        return Action.LOCKDOWN


# --------------------------------------------------------------------------- #
# The words shown at each step. Kept here in one place so the tone is
# consistent, and the screen code doesn't need to know what to say.
#
# There's one full set of words per Kamen Rider era (Showa, Heisei,
# Reiwa), so picking a different era of Rider in Settings doesn't just
# repaint the app — it also talks to you a little differently:
#   Showa  — an old base alarm: blunt, short, siren-like.
#   Heisei — a tactical mission briefing. This is also the fallback set,
#            used if we ever get handed an era name we don't recognise.
#   Reiwa  — a modern digital system alert: crisp, a bit clinical.
# --------------------------------------------------------------------------- #
DEFAULT_ERA = "Heisei"

MESSAGES_BY_ERA = {
    "Showa": {
        Action.WARN: (
            "Intruder Alert",
            "{app} detected. {time} remains in this Henshin block.",
        ),
        Action.NAG: (
            "Second Alarm",
            "{seconds}s on {app}. {time} until mission's end — hold the line.",
        ),
        Action.MINIMIZE: (
            "Target Neutralized",
            "{app} minimized. {time} remaining.",
        ),
        Action.LOCKDOWN: (
            "Base Lockdown",
            "Sealed for {lockdown}s. Regroup, then resume the mission.",
        ),
    },
    "Heisei": {
        Action.WARN: (
            "Off Mission",
            "{app} is not part of the mission. {time} remains in this Henshin block.",
        ),
        Action.NAG: (
            "Repeated Violation",
            "{seconds}s on {app}. {time} until the mission ends — hold the line.",
        ),
        Action.MINIMIZE: (
            "Window Neutralized",
            "{app} minimized. {time} remaining. This was your directive.",
        ),
        Action.LOCKDOWN: (
            "Full Lockdown",
            "Screen sealed for {lockdown}s. Recover, then resume the mission.",
        ),
    },
    "Reiwa": {
        Action.WARN: (
            "Focus Breach",
            "{app} flagged. {time} left in this Henshin block.",
        ),
        Action.NAG: (
            "Repeated Breach",
            "{seconds}s on {app} — {time} to mission end. System recommends refocusing.",
        ),
        Action.MINIMIZE: (
            "Process Terminated",
            "{app} minimized. {time} remaining. Directive executed.",
        ),
        Action.LOCKDOWN: (
            "System Lockdown",
            "Screen locked {lockdown}s. Recalibrate, then resume.",
        ),
    },
}

# The big shouted words on the full-screen lockdown cover, one per era.
LOCKDOWN_LABELS = {
    "Showa": "BASE LOCKDOWN.",
    "Heisei": "LOCKDOWN ENGAGED.",
    "Reiwa": "SYSTEM LOCKDOWN.",
}


def message_for(action: Action, *, app: str, remaining: str,
                seconds: int, lockdown: int, era: str = DEFAULT_ERA) -> tuple[str, str]:
    """
    Fill in the blanks for `action`'s message, in the voice of `era`.

    If `era` isn't one we know, we quietly use the Heisei words instead
    of crashing — a typo in a saved settings file shouldn't break the app.
    """
    messages = MESSAGES_BY_ERA.get(era, MESSAGES_BY_ERA[DEFAULT_ERA])
    title, body = messages[action]
    return title, body.format(app=app, time=remaining, seconds=int(seconds),
                              lockdown=lockdown)


def lockdown_label_for(era: str) -> str:
    """The big shouted words on the full-screen lockdown cover, for this era."""
    return LOCKDOWN_LABELS.get(era, LOCKDOWN_LABELS[DEFAULT_ERA])