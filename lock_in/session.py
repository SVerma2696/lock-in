"""
session.py
==========
This file is the timer's brain — it keeps track of whether you're focusing
or on a break.

It needs nothing fancy at all — no windows, no screen, nothing from your
computer's operating system. It's just simple logic: you give it a clock,
call `tick()`, and it tells you what's happening and what just changed.

That's what lets us test it so easily — `tests/test_session.py` can fast
forward a pretend clock by hours in an instant, without ever really waiting.

How the phases flow
----------------------
    IDLE ──start()──> FOCUS ──timer runs out──> SHORT_BREAK ──> FOCUS ...
                        │                          │
                        │    every so many blocks  │
                        └──────────────────> LONG_BREAK ──> FOCUS
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Callable, List, Optional


class Phase(str, Enum):
    """
    Which part of the timer we're in right now.

    This is built so a Phase can be compared to plain text like "focus",
    which makes saving it and looking it up much simpler.
    """

    IDLE = "idle"
    FOCUS = "focus"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"

    @property
    def is_break(self) -> bool:
        return self in (Phase.SHORT_BREAK, Phase.LONG_BREAK)

    @property
    def label(self) -> str:
        """The Kamen-Rider-flavored name shown on screen."""
        return {
            Phase.IDLE: "Standing By",
            Phase.FOCUS: "Henshin",
            Phase.SHORT_BREAK: "Recovery",
            Phase.LONG_BREAK: "Stand Down",
        }[self]

    @property
    def professional_label(self) -> str:
        """The plain, ordinary name shown on screen."""
        return {
            Phase.IDLE: "Idle",
            Phase.FOCUS: "Focus",
            Phase.SHORT_BREAK: "Short Break",
            Phase.LONG_BREAK: "Long Break",
        }[self]


# Plain, ordinary words are the app's normal voice. The Kamen Rider
# flavor is something you turn ON, in Settings, not something you have
# to turn off.
DEFAULT_TERMINOLOGY = "professional"


def label_for(phase: Phase, terminology: str = DEFAULT_TERMINOLOGY) -> str:
    """
    The phase name to show on screen, picking which voice to use.

    Anything other than exactly "tokusatsu" (including a typo, or a
    missing setting) quietly gives back the plain, professional name
    instead of guessing wrong or crashing.
    """
    if terminology == "tokusatsu":
        return phase.label
    return phase.professional_label


class Event(str, Enum):
    """Things `tick()` can report happened, for the screen to react to."""

    PHASE_STARTED = "phase_started"
    PHASE_ENDED = "phase_ended"
    TICK = "tick"


class PomodoroSession:
    """
    Runs the focus-and-break cycle from start to finish.

    Parameters
    ----------
    config:
        Anything with `.focus_minutes`, `.short_break_minutes`,
        `.long_break_minutes`, `.blocks_until_long_break`, `.auto_start_breaks`,
        and `.auto_start_focus` on it. Normally this is a real `Config`, but
        the tests use a simple stand-in instead.
    clock:
        A function that gives back a number of seconds that only ever goes
        up. Normally `time.monotonic` — NOT the regular clock on your
        computer, on purpose, because if someone changes their computer's
        clock (or daylight saving time kicks in), the timer must never
        suddenly jump.
    """

    def __init__(self, config, clock: Callable[[], float] = time.monotonic) -> None:
        self.config = config
        self._clock = clock

        self.phase: Phase = Phase.IDLE
        self.completed_focus_blocks: int = 0

        self._phase_ends_at: Optional[float] = None   # the exact moment this phase should end
        self._paused_remaining: Optional[float] = None  # time left, saved while paused

    # ------------------------------------------------------------------ #
    # Asking questions
    # ------------------------------------------------------------------ #
    @property
    def is_running(self) -> bool:
        """True when a phase is going and isn't paused."""
        return self.phase is not Phase.IDLE and self._paused_remaining is None

    @property
    def is_paused(self) -> bool:
        return self._paused_remaining is not None

    @property
    def remaining_seconds(self) -> int:
        """
        How many seconds are left in this phase — never a negative number.

        We round UP so the timer doesn't show "0:59" the instant it starts
        at "1:00" — that tiny glitch would make the countdown feel broken.
        """
        if self._paused_remaining is not None:
            return max(0, int(self._paused_remaining + 0.999))
        if self._phase_ends_at is None:
            return 0
        return max(0, int(self._phase_ends_at - self._clock() + 0.999))

    @property
    def total_seconds(self) -> int:
        """The full length of the current phase, used to draw the progress bar."""
        if self.phase is Phase.IDLE:
            return self.config.focus_minutes * 60
        return self.config.phase_seconds(self.phase.value)

    @property
    def progress(self) -> float:
        """0.0 when a phase just started, 1.0 when it's finished."""
        total = self.total_seconds
        if total <= 0:
            return 0.0
        return min(1.0, max(0.0, 1.0 - (self.remaining_seconds / total)))

    @property
    def blocks_until_long_break(self) -> int:
        """How many more focus blocks until you earn a long break."""
        n = self.config.blocks_until_long_break
        if n <= 0:
            return 0
        return n - (self.completed_focus_blocks % n)

    def format_remaining(self) -> str:
        """Shows the time left as MM:SS, or H:MM:SS for a really long focus block."""
        secs = self.remaining_seconds
        hours, rem = divmod(secs, 3600)
        mins, s = divmod(rem, 60)
        if hours:
            return f"{hours}:{mins:02d}:{s:02d}"
        return f"{mins:02d}:{s:02d}"

    # ------------------------------------------------------------------ #
    # Things you can tell it to do
    # ------------------------------------------------------------------ #
    def start(self) -> List[Event]:
        """Start (or continue) the session. Starting fresh always begins with focus time."""
        if self.is_paused:
            return self.resume()
        if self.phase is Phase.IDLE:
            return self._enter(Phase.FOCUS)
        return []

    def pause(self) -> None:
        """
        Freeze the countdown right where it is.

        We save how much time is LEFT, not what time it was when you paused
        — that way, doing the math to resume later is simple and can't
        slowly go wrong.
        """
        if not self.is_running or self._phase_ends_at is None:
            return
        self._paused_remaining = max(0.0, self._phase_ends_at - self._clock())
        self._phase_ends_at = None

    def resume(self) -> List[Event]:
        """Un-freeze the countdown, picking up from right where it left off."""
        if self._paused_remaining is None:
            return []
        self._phase_ends_at = self._clock() + self._paused_remaining
        self._paused_remaining = None
        return []

    def toggle(self) -> List[Event]:
        """One button that starts, pauses, or resumes — what the big button on screen calls."""
        if self.is_running:
            self.pause()
            return []
        return self.start()

    def skip(self) -> List[Event]:
        """
        Jump straight to the next phase.

        Skipping a focus block still counts it as done, on purpose — if
        skipping reset your streak, people would rather sit around doing
        nothing than skip honestly, and that's the wrong incentive.
        """
        if self.phase is Phase.IDLE:
            return self._enter(Phase.FOCUS)
        return self._advance()

    def reset(self) -> None:
        """Stop everything and go back to the very beginning."""
        self.phase = Phase.IDLE
        self._phase_ends_at = None
        self._paused_remaining = None
        self.completed_focus_blocks = 0

    # ------------------------------------------------------------------ #
    # The heartbeat — call this over and over to keep time moving
    # ------------------------------------------------------------------ #
    def tick(self) -> List[Event]:
        """
        Move the clock forward by checking the current time. Call this a few
        times a second from the app's main loop.

        Gives back a list of things that just happened, so whoever called
        this can react (play a sound, turn blocking on or off) instead of
        having to keep asking "did anything change yet?".
        """
        if not self.is_running or self._phase_ends_at is None:
            return []
        if self._clock() >= self._phase_ends_at:
            return self._advance()
        return [Event.TICK]

    # ------------------------------------------------------------------ #
    # Behind-the-scenes helpers
    # ------------------------------------------------------------------ #
    def _advance(self) -> List[Event]:
        """Figure out what phase comes next, and move into it."""
        finished = self.phase
        events: List[Event] = [Event.PHASE_ENDED]

        if finished is Phase.FOCUS:
            self.completed_focus_blocks += 1
            n = self.config.blocks_until_long_break
            earned_long = n > 0 and self.completed_focus_blocks % n == 0
            nxt = Phase.LONG_BREAK if earned_long else Phase.SHORT_BREAK
            auto = self.config.auto_start_breaks
        else:
            nxt = Phase.FOCUS
            auto = self.config.auto_start_focus

        events += self._enter(nxt, autostart=auto)
        return events

    def _enter(self, phase: Phase, autostart: bool = True) -> List[Event]:
        """
        Switch into `phase`.

        If `autostart` is False, we still switch into the phase but leave it
        paused — so the screen shows "5:00 — press start" instead of quietly
        burning through someone's break time while they're away.
        """
        self.phase = phase
        duration = self.config.phase_seconds(phase.value)

        if autostart:
            self._phase_ends_at = self._clock() + duration
            self._paused_remaining = None
        else:
            self._phase_ends_at = None
            self._paused_remaining = float(duration)

        return [Event.PHASE_STARTED]