"""
claude_fallback.py
===================
This is an extra, optional helper that asks Claude for a second opinion when
our own little model can't decide. It only kicks in after everything else:

    allow list  >  block list  >  our own model (if sure)  >  Claude  >  allowed

If our own model isn't confident about a window, right now it just shrugs and
lets it through. This file gives it a way to ask Claude instead of shrugging
— but only for the genuinely confusing, small minority of windows:

  - The app checks your window once every second. Asking Claude takes real
    time (sometimes half a second or more) and costs a tiny bit of money each
    time. Asking every single second, all day, would slow everything down and
    add up in cost — for something our free local model already gets right
    most of the time anyway.
  - This is the ONLY place a window title ever leaves your computer.
    Everything else in the app — the lists, the local model — stays entirely
    on your machine. That's exactly why this feature is switched off unless
    you turn it on yourself.

Every answer Claude gives is also used to teach the local model (through the
same storage `train.py` uses), so over time the local model learns what
Claude knows and needs to ask less and less.

What happens when something goes wrong
-----------------------------------------
No API key, no internet, too many requests, a weird reply — none of these
should ever crash the app. They should all just quietly turn into "no strong
opinion" (STUDY, 0.5), exactly like when the local model isn't sure. A wrong
or missing API key should never break your Pomodoro timer.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from .classifier import DISTRACTION, STUDY

SYSTEM_PROMPT = (
    "You classify a computer window as either study-related or a distraction, "
    "based only on its title and process name. Study includes coursework, "
    "research, coding, documentation, note-taking, and academic tools. "
    "Distraction includes social media, video/music streaming, games, and chat "
    "apps used for non-work purposes. If genuinely unclear, prefer 'study' — a "
    "false alarm interrupts real work, which is worse than missing one "
    "borderline case.\n\n"
    'Respond with ONLY a JSON object, nothing else: {"label": "study" or '
    '"distraction", "confidence": a number from 0.5 to 1.0}'
)


@dataclass
class ClaudeVerdict:
    """The answer from asking Claude — or the reason we didn't ask."""

    label: str
    confidence: float
    source: str          # "claude" | "cache" | "unavailable" | "error"
    detail: str = ""


class ClaudeFallback:
    """
    Talks to Claude, but gives back answers in the exact same shape as our
    own local model (a label plus how sure it is). That way the rest of the
    app barely notices the difference.

    Made once when the app starts, and reused the whole time it's open — that
    way it doesn't have to reconnect or forget its remembered answers every
    single check.
    """

    def __init__(self, config) -> None:
        self.config = config
        self._client = None
        self._client_error: Optional[str] = None
        self._cache: dict[str, Tuple[ClaudeVerdict, float]] = {}
        self._inflight: set[str] = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    @property
    def available(self) -> bool:
        """
        True only if this feature is turned on, the Claude toolkit is
        installed, and you have an API key set up. We check this fresh every
        time (not just once when the app starts), so flipping the switch or
        adding a key while the app is open works right away.
        """
        if not self.config.claude_fallback_enabled:
            return False
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        return self._ensure_client()

    def _ensure_client(self) -> bool:
        if self._client is not None:
            return True
        if self._client_error is not None:
            return False
        try:
            import anthropic
        except ImportError:
            self._client_error = "anthropic package not installed (pip install anthropic)"
            return False
        try:
            self._client = anthropic.Anthropic()
        except Exception as exc:                       # for example, a bad key
            self._client_error = str(exc)
            return False
        return True

    @property
    def status(self) -> str:
        """A short, plain-English status message shown on the Blocking tab."""
        if not self.config.claude_fallback_enabled:
            return "off"
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return "no ANTHROPIC_API_KEY environment variable found"
        if not self._ensure_client():
            return self._client_error or "unavailable"
        return f"ready ({self.config.claude_model})"

    # ------------------------------------------------------------------ #
    def judge(self, text: str) -> ClaudeVerdict:
        """
        Ask about `text`, checking our remembered answers first. Never crashes.

        Careful: this WAITS for the internet, so it can take a moment. Don't
        call it directly from the main app — use `judge_async` below instead,
        which does the waiting on the side without freezing the app.
        """
        if not text.strip():
            return ClaudeVerdict(STUDY, 0.5, "unavailable", "empty text")

        cached = self._cache_get(text)
        if cached is not None:
            return cached

        if not self.available:
            return ClaudeVerdict(STUDY, 0.5, "unavailable", self.status)

        verdict = self._call(text)
        self._cache_set(text, verdict)
        return verdict

    def peek(self, text: str) -> Optional[ClaudeVerdict]:
        """
        Check if we already remember an answer for this text — instantly,
        without ever touching the internet.

        The app calls this every single second, so it needs to be instant and
        safe to run right on the main screen. If nothing is remembered yet,
        the app uses the local model's own guess for right now, and quietly
        starts `judge_async` in the background — so by the NEXT check (about
        a second later, and the same window is usually still open), the real
        answer is ready.
        """
        return self._cache_get(text)

    def judge_async(self, text: str, on_result) -> None:
        """
        Start asking Claude in the background, and hand the answer to
        `on_result` once it arrives.

        `on_result` runs on a separate background thread, not the main app
        thread — so it must only safely drop its answer into a queue, nothing
        fancier.

        We also make sure not to ask about the exact same text twice at once
        — if two checks in a row both come up empty before the first answer
        arrives, only one background request gets started.
        """
        if not text.strip() or not self.available:
            return

        with self._lock:
            if text in self._inflight:
                return
            self._inflight.add(text)

        def run() -> None:
            try:
                verdict = self.judge(text)
                try:
                    on_result(text, verdict)
                except Exception:
                    pass       # a broken callback must not crash this background thread
            finally:
                with self._lock:
                    self._inflight.discard(text)

        threading.Thread(target=run, daemon=True, name="claude-fallback").start()

    def _call(self, text: str) -> ClaudeVerdict:
        try:
            response = self._client.messages.create(
                model=self.config.claude_model,
                max_tokens=40,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"Window: {text}"}],
            )
            raw = "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()
            data = json.loads(raw)

            label = data.get("label", "").strip().lower()
            if label not in (STUDY, DISTRACTION):
                return ClaudeVerdict(STUDY, 0.5, "error", f"unexpected label: {label!r}")

            confidence = float(data.get("confidence", 0.75))
            confidence = min(1.0, max(0.5, confidence))    # keep it in a sensible range
            return ClaudeVerdict(label, confidence, "claude")

        except json.JSONDecodeError:
            return ClaudeVerdict(STUDY, 0.5, "error", "unparseable response")
        except Exception as exc:
            # We catch anything at all here on purpose — too many requests,
            # a slow connection, a bad key, the internet dropping — all of
            # these should just mean "no answer right now," never a crash.
            return ClaudeVerdict(STUDY, 0.5, "error", str(exc)[:120])

    # ------------------------------------------------------------------ #
    # Remembering answers, so we don't ask (and pay for) the same thing twice
    # ------------------------------------------------------------------ #
    def _cache_get(self, text: str) -> Optional[ClaudeVerdict]:
        with self._lock:
            entry = self._cache.get(text)
            if entry is None:
                return None
            verdict, expires_at = entry
            if time.monotonic() >= expires_at:
                del self._cache[text]
                return None
            return ClaudeVerdict(verdict.label, verdict.confidence, "cache", verdict.detail)

    def _cache_set(self, text: str, verdict: ClaudeVerdict) -> None:
        if verdict.source != "claude":
            return          # don't remember failures — a one-time hiccup shouldn't stick around
        ttl = self.config.claude_cache_minutes * 60
        with self._lock:
            self._cache[text] = (verdict, time.monotonic() + ttl)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()