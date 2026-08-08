# Lock In Rebrand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename FocusLock to "Lock In", reskin its copy with a serious
tokusatsu (Kamen Rider) tone, add a 38-Rider color-theme toggle, bring
macOS/Linux to real feature parity with Windows, and add a tag-triggered
GitHub Actions release pipeline.

**Architecture:** Rename the `pomodoro_lock` package to `lock_in` first
(everything downstream depends on that import path), then layer in copy
changes, a new `rider_themes.py` data module consumed by `ui.py`, platform
branches in `monitor.py`/`notifier.py`, and finally CI workflow files.

**Tech Stack:** Python 3.11+, CustomTkinter, pywin32/psutil (Windows),
osascript/afplay (macOS), xdotool/notify-send/paplay (Linux), pytest,
GitHub Actions.

## Global Constraints

- **No git or GitHub operations of any kind** — no `git init`, `add`,
  `commit`, `push`, `tag`, `remote`, and no `gh` commands against the real
  repo. This repo has no `.git` yet; the user will initialize it, wire up
  `https://github.com/SVerma2696/lock-in`, and push/tag it themselves
  after every task below is done. Every task ends with "mark the task
  complete" instead of a commit step.
- App name is **Lock In** everywhere user-facing; Python package is
  `lock_in` (snake_case, since it's an import path).
- Enum *values* (`Action.WARN = "warn"`, `Phase.FOCUS = "focus"`,
  `STUDY = "study"`, etc.) are persisted to `config.json`/`model.json` on
  disk and must **not** change — only `.label` strings and UI copy change.
- Rider theme system is colors-only (one `primary` + one `secondary` hex
  per Rider) — no per-Rider copy/catchphrases.
- The corrected 38-Rider palette in the spec
  (`docs/superpowers/specs/2026-08-07-lock-in-rebrand-design.md`, section 3)
  is the exact source of truth for hex values — copy it verbatim, don't
  re-derive it.
- Functional/error copy (dependency warnings, "App detection unavailable")
  stays plain English, not themed.
- I'm implementing on Windows and cannot run the macOS/Linux code paths
  (`monitor.py`, `notifier.py` platform branches) — those tasks end with
  "needs verification on that OS," not a passing automated test.

---

## Task 1: Rename `pomodoro_lock/` to `lock_in/` and fix every import

**Files:**
- Move: `pomodoro_lock/` → `lock_in/` (all 9 files inside, plus delete the
  stale `pomodoro_lock/__pycache__/`)
- Modify: `main.py:66`, `train.py:42,49,50,93`
- Modify: `tests/test_claude_fallback.py:16-18`,
  `tests/test_enforcer.py:5-7,146,151,304,314,340,350,361`,
  `tests/test_classifier.py:7`, `tests/test_observations.py:7-8`,
  `tests/smoke_ui.py:19-21,33`

**Interfaces:**
- Produces: the import path `lock_in.*` that every later task uses
  (`from lock_in.config import Config`, `from lock_in.ui import run`, etc).

- [ ] **Step 1: Move the directory**

```bash
git mv pomodoro_lock lock_in 2>/dev/null || mv pomodoro_lock lock_in
rm -rf lock_in/__pycache__
```

(`git mv` will fail harmlessly since there's no repo yet — the `mv`
fallback does the actual work. This is a filesystem move, not a git
operation; it's fine under the "no git" constraint because no `git`
command actually runs.)

- [ ] **Step 2: Fix every import in the app and CLI**

In `main.py` line 66, change:
```python
    from pomodoro_lock.ui import run
```
to:
```python
    from lock_in.ui import run
```

In `train.py`, change every occurrence of `pomodoro_lock` to `lock_in`
(lines 42, 49, 50, 93 — `from pomodoro_lock.classifier import (...)`,
`from pomodoro_lock.config import ...`, `from pomodoro_lock.observations
import ...`, `from pomodoro_lock.monitor import ...`).

- [ ] **Step 3: Fix every import in tests**

In each of these files, replace every `pomodoro_lock` with `lock_in`
(these are plain import-path strings, not logic — a global find-replace
per file is correct):
- `tests/test_claude_fallback.py` (lines 16-18)
- `tests/test_enforcer.py` (lines 5-7, and the inline imports at 146,
  151, 304, 314, 340, 350, 361)
- `tests/test_classifier.py` (line 7)
- `tests/test_observations.py` (lines 7-8)
- `tests/smoke_ui.py` (lines 19-21 — also rename the `FocusLockApp`
  reference on line 21 and its use on line 33 to `LockInApp`; the class
  itself is renamed in Task 2, so this makes both edits consistent)

- [ ] **Step 4: Run the test suite**

Run: `pytest`
Expected: all tests pass (same tests, just importing from the new path).
If anything fails with `ModuleNotFoundError: No module named
'pomodoro_lock'`, grep for the leftover reference:

```bash
grep -rn "pomodoro_lock" --include="*.py" .
```

- [ ] **Step 5: Mark task complete** (no git — see Global Constraints)

---

## Task 2: Rebrand identity strings and config paths

**Files:**
- Modify: `lock_in/config.py:15-17,33`
- Modify: `lock_in/notifier.py:60`
- Modify: `lock_in/ui.py:69,107,432-433,964,1009,1011`
- Modify: `lock_in/__init__.py` (whole file)
- Modify: `lock_in/observations.py:21` (docstring only)
- Modify: `main.py:4,11`
- Modify: `train.py:5,90` (docstring/comment text only, not logic)
- Modify: `build.bat:3,13,22`
- Modify: `run.bat:3`
- Modify: `.gitignore:29,35`

**Interfaces:**
- Produces: `Config.APP_NAME == "Lock In"`, `LockInApp` class (renamed from
  `FocusLockApp`), `Notifier(config, app_name="Lock In")` default.

- [ ] **Step 1: `config.py` — app name and docstring paths**

At line 33, change:
```python
APP_NAME = "FocusLock"
```
to:
```python
APP_NAME = "Lock In"
```

At lines 15-17, change the docstring:
```
Windows : C:\\Users\\<you>\\AppData\\Roaming\\FocusLock\\config.json
macOS   : ~/Library/Application Support/FocusLock/config.json
Linux   : ~/.config/FocusLock/config.json
```
to:
```
Windows : C:\\Users\\<you>\\AppData\\Roaming\\Lock In\\config.json
macOS   : ~/Library/Application Support/Lock In/config.json
Linux   : ~/.config/Lock In/config.json
```

- [ ] **Step 2: `notifier.py` — default app name**

At line 60, change:
```python
    def __init__(self, config, app_name: str = "FocusLock") -> None:
```
to:
```python
    def __init__(self, config, app_name: str = "Lock In") -> None:
```

- [ ] **Step 3: `ui.py` — class name, window title, self-window check**

At line 69, change `class FocusLockApp(ctk.CTk):` to
`class LockInApp(ctk.CTk):`.

At line 107, change `self.title("FocusLock")` to
`self.title("Lock In")`.

At lines 432-433, change:
```python
            # Never block someone just for looking at FocusLock itself.
            if "focuslock" in (latest.title or "").lower():
```
to:
```python
            # Never block someone just for looking at Lock In itself.
            if "lock in" in (latest.title or "").lower():
```

At line 964, change:
```python
        self.title(f"{self.session.format_remaining()} · {phase.label} — FocusLock")
```
to:
```python
        self.title(f"{self.session.format_remaining()} · {phase.label} — Lock In")
```

At line 1011, change `FocusLockApp().mainloop()` to
`LockInApp().mainloop()`.

- [ ] **Step 4: `__init__.py` — rewrite the module docstring**

Replace the whole file with:
```python
"""
Lock In — a Pomodoro timer that actually keeps you off the fun apps.

Package layout
--------------
    config.py        settings + JSON persistence            (no deps)
    session.py       the Pomodoro state machine             (no deps, pure logic)
    classifier.py    Naive Bayes study/distraction model     (no deps, pure logic)
    enforcer.py      judgement + escalation ladder           (no deps, pure logic)
    rider_themes.py  Kamen Rider color palettes              (no deps, pure data)
    monitor.py       foreground-window polling               (pywin32/psutil, osascript, xdotool)
    notifier.py      toasts and sounds                       (winotify/winsound, osascript/afplay, notify-send/paplay)
    ui.py            CustomTkinter front end                 (customtkinter)

The first five modules import nothing outside the standard library, which
is why the whole behavioural core is unit-tested without a display server.
"""

__version__ = "2.0.0"
__all__ = ["__version__"]
```

- [ ] **Step 5: Everything else — mechanical string replacements**

In `lock_in/observations.py` line 21, change `FocusLock` to `Lock In` in
the docstring path example.

In `main.py` lines 4 and 11, change "FocusLock" to "Lock In" and
"pomodoro_lock folder" to "lock_in folder" in the module docstring.

In `train.py` lines 5 and 90, change "FocusLock" to "Lock In" in the
comment/docstring text (these are prose, not code — don't touch the
actual logic on those lines).

In `build.bat`:
- Line 3: `REM This turns the app into one FocusLock.exe file...` →
  `REM This turns the app into one "Lock In.exe" file...`
- Line 13: `--name FocusLock ^` → `--name "Lock In" ^`
- Line 22: `echo Built: dist\FocusLock.exe` →
  `echo Built: dist\Lock In.exe`

In `run.bat` line 3: `REM This double-click file starts FocusLock for
you.` → `REM This double-click file starts Lock In for you.`

In `.gitignore`:
- Line 29: `# %APPDATA%\FocusLock\ on Windows...` →
  `# %APPDATA%\Lock In\ on Windows...`
- Line 35: `focuslock_training_data.csv` → `lockin_training_data.csv`

- [ ] **Step 6: Verify no stray references remain**

Run:
```bash
grep -rniE "focuslock" --include="*.py" --include="*.bat" --include="*.md" --include=".gitignore" .
```
Expected: no output (the README is handled separately in Task 10 — if
this grep flags README.md lines, that's expected until Task 10 runs).

- [ ] **Step 7: Run the test suite**

Run: `pytest`
Expected: all tests still pass — none of these are behavior changes.

- [ ] **Step 8: Mark task complete** (no git)

---

## Task 3: Rename the app's self-reference strings in training data

**Files:**
- Modify: `lock_in/classifier.py:99,156`
- Modify: `tests/test_classifier.py:84`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — this only changes the *content* of two seed
  examples and one test fixture string, not any interface.

- [ ] **Step 1: Update `classifier.py` SEED_DATA**

At line 99, change:
```python
    ("main.py - focuslock - Visual Studio Code code.exe", STUDY),
```
to:
```python
    ("main.py - lock_in - Visual Studio Code code.exe", STUDY),
```

At line 156, change:
```python
    ("classifier.py - focuslock - Visual Studio Code code.exe", STUDY),
```
to:
```python
    ("classifier.py - lock_in - Visual Studio Code code.exe", STUDY),
```

- [ ] **Step 2: Update the matching test fixture**

In `tests/test_classifier.py` line 84, change:
```python
        "enforcer.py - focuslock - Visual Studio Code code.exe",
```
to:
```python
        "enforcer.py - lock_in - Visual Studio Code code.exe",
```

- [ ] **Step 3: Run the classifier tests**

Run: `pytest tests/test_classifier.py -v`
Expected: `test_recognises_obvious_study` still passes — the string still
tokenizes to mostly the same study-signal words (`enforcer`, `py`,
`visual`, `studio`, `code`), `lock`/`in` aren't associated with
distraction anywhere in `SEED_DATA`, so the prediction doesn't flip.

- [ ] **Step 4: Mark task complete** (no git)

---

## Task 4: Serious-tone phase labels, with tests

**Files:**
- Modify: `tests/test_session.py` (currently empty)
- Modify: `lock_in/session.py:47-54`

**Interfaces:**
- Produces: `Phase.IDLE.label == "Standing By"`,
  `Phase.FOCUS.label == "Henshin"`, `Phase.SHORT_BREAK.label ==
  "Recovery"`, `Phase.LONG_BREAK.label == "Stand Down"` — later tasks
  (ui.py banners) read `phase.label` and depend on these exact strings.

- [ ] **Step 1: Write the failing tests**

`tests/test_session.py` is currently empty. Write:

```python
from lock_in.session import Phase


def test_phase_labels_are_serious_tokusatsu_tone():
    assert Phase.IDLE.label == "Standing By"
    assert Phase.FOCUS.label == "Henshin"
    assert Phase.SHORT_BREAK.label == "Recovery"
    assert Phase.LONG_BREAK.label == "Stand Down"


def test_break_phases_are_still_flagged_as_breaks():
    assert Phase.SHORT_BREAK.is_break
    assert Phase.LONG_BREAK.is_break
    assert not Phase.FOCUS.is_break
    assert not Phase.IDLE.is_break
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_session.py -v`
Expected: `test_phase_labels_are_serious_tokusatsu_tone` FAILS (current
labels are "Ready"/"Focus"/"Short Break"/"Long Break").
`test_break_phases_are_still_flagged_as_breaks` should already PASS —
that's an existing behavior this task doesn't touch, included so the
file isn't a single fragile test.

- [ ] **Step 3: Implement the label change**

In `lock_in/session.py`, change the `label` property (lines 47-54) from:
```python
    @property
    def label(self) -> str:
        """The friendly name shown on screen."""
        return {
            Phase.IDLE: "Ready",
            Phase.FOCUS: "Focus",
            Phase.SHORT_BREAK: "Short Break",
            Phase.LONG_BREAK: "Long Break",
        }[self]
```
to:
```python
    @property
    def label(self) -> str:
        """The friendly name shown on screen."""
        return {
            Phase.IDLE: "Standing By",
            Phase.FOCUS: "Henshin",
            Phase.SHORT_BREAK: "Recovery",
            Phase.LONG_BREAK: "Stand Down",
        }[self]
```

- [ ] **Step 4: Run the tests again**

Run: `pytest tests/test_session.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Mark task complete** (no git)

---

## Task 5: Serious-tone copy in the enforcer's notifications

**Files:**
- Modify: `tests/test_enforcer.py` (add to the "Copy" section, ~line 275)
- Modify: `lock_in/enforcer.py:309-326`

**Interfaces:**
- Consumes: `Action.WARN/NAG/MINIMIZE/LOCKDOWN` (unchanged from Task 1).
- Produces: `message_for(action, ...)` returns the exact new copy —
  `ui.py`'s `_perform()` (Task 6) passes these straight to the notifier
  without modification.

- [ ] **Step 1: Write the failing test**

In `tests/test_enforcer.py`, add this test near the existing
`test_every_rung_has_message_copy` (around line 275) to pin the exact new
copy, not just "non-empty":

```python
def test_message_copy_matches_serious_tokusatsu_tone():
    title, body = message_for(Action.WARN, app="discord.exe", remaining="12:30",
                              seconds=20, lockdown=15)
    assert title == "Off Mission"
    assert body == "discord.exe is not part of the mission. 12:30 remains in this Henshin block."

    title, body = message_for(Action.NAG, app="discord.exe", remaining="12:30",
                              seconds=20, lockdown=15)
    assert title == "Repeated Violation"
    assert body == "20s on discord.exe. 12:30 until the mission ends — hold the line."

    title, body = message_for(Action.MINIMIZE, app="discord.exe", remaining="12:30",
                              seconds=20, lockdown=15)
    assert title == "Window Neutralized"
    assert body == "discord.exe minimized. 12:30 remaining. This was your directive."

    title, body = message_for(Action.LOCKDOWN, app="discord.exe", remaining="12:30",
                              seconds=20, lockdown=15)
    assert title == "Full Lockdown"
    assert body == "Screen sealed for 15s. Recover, then resume the mission."
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_enforcer.py -k serious_tokusatsu -v`
Expected: FAIL — current titles are "Back to it" / "Still there" /
"Closing that for you" / "Locked in".

- [ ] **Step 3: Implement the new MESSAGES dict**

In `lock_in/enforcer.py`, replace the `MESSAGES` dict (lines 309-326):
```python
MESSAGES = {
    Action.WARN: (
        "Back to it",
        "{app} isn't on the plan. {time} left in this block.",
    ),
    Action.NAG: (
        "Still there",
        "That's {seconds}s on {app}. The break is {time} away — it'll keep.",
    ),
    Action.MINIMIZE: (
        "Closing that for you",
        "{app} minimised. {time} left. You asked me to do this.",
    ),
    Action.LOCKDOWN: (
        "Locked in",
        "Screen's covered for {lockdown}s. Deep breath, then back to work.",
    ),
}
```
with:
```python
MESSAGES = {
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
}
```

- [ ] **Step 4: Run the tests again**

Run: `pytest tests/test_enforcer.py -v`
Expected: all pass, including the pre-existing
`test_every_rung_has_message_copy` (still true: every rung still has
non-empty title/body with no unfilled `{...}`).

- [ ] **Step 5: Mark task complete** (no git)

---

## Task 6: Serious-tone copy in `ui.py` (buttons, banners, lockdown, streak)

**Files:**
- Modify: `lock_in/ui.py:181-185` (Henshin button)
- Modify: `lock_in/ui.py:636-643` (phase-start banners)
- Modify: `lock_in/ui.py:573-587` (lockdown screen)
- Modify: `lock_in/ui.py:953,957-960` (streak label + start/pause text)

**Interfaces:**
- Consumes: `Phase.label` values from Task 4.
- Produces: no new interfaces — pure copy changes inside `LockInApp`.

This task is UI copy with no headless test coverage (CustomTkinter needs
a display) — verify by running the app manually per Step 4.

- [ ] **Step 1: Rename the main button**

In `lock_in/ui.py`, the toggle button is created at lines 181-185:
```python
        self.start_button = ctk.CTkButton(
            controls, text="Start", width=140, height=40,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._on_toggle,
        )
```
Change `text="Start"` to `text="Henshin"`.

Then find `_refresh_timer_widgets` (around line 953):
```python
        self.start_button.configure(text="Pause" if self.session.is_running else "Start")
```
Change to:
```python
        self.start_button.configure(text="Pause" if self.session.is_running else "Henshin")
```

- [ ] **Step 2: Rewrite phase-transition banners**

In `_on_phase_started` (around lines 636-643), change:
```python
        if phase is not Phase.IDLE:
            self.notifier.phase_chime(phase.label)
            if phase.is_break:
                self._show_banner(
                    f"{phase.label} — {self.session.format_remaining()}. Go get water.",
                    "low",
                )
            else:
                self._show_banner("Focus block started. Blocking is live.", "low")
```
to:
```python
        if phase is not Phase.IDLE:
            self.notifier.phase_chime(phase.label)
            if phase.is_break:
                self._show_banner(
                    f"{phase.label} — {self.session.format_remaining()} remaining.",
                    "low",
                )
            else:
                self._show_banner("Henshin initiated. Blocking is active.", "low")
```
(Both break phases now share one banner format using `phase.label`,
which is already "Recovery" or "Stand Down" from Task 4 — no need to
special-case short vs. long break text.)

- [ ] **Step 3: Rewrite the lockdown screen**

In `_show_lockdown` (around lines 573-587), change:
```python
        ctk.CTkLabel(overlay, text="Back to work.",
                     font=ctk.CTkFont(size=54, weight="bold"),
                     text_color=COLOR_FOCUS).pack(pady=(220, 10))

        ctk.CTkLabel(overlay, text=f"{self.session.format_remaining()} left in this block",
                     font=ctk.CTkFont(size=20), text_color="#9aa4b2").pack()

        countdown = ctk.CTkLabel(overlay, text="", font=ctk.CTkFont(size=16),
                                 text_color="#6b7480")
        countdown.pack(pady=26)

        ctk.CTkButton(overlay, text="End session instead", width=200,
                      fg_color="transparent", border_width=1,
                      text_color="#6b7480", hover_color="#1d2026",
                      command=self._end_session_from_lockdown).pack()
```
to:
```python
        ctk.CTkLabel(overlay, text="LOCKDOWN ENGAGED.",
                     font=ctk.CTkFont(size=54, weight="bold"),
                     text_color=self.color_focus).pack(pady=(220, 10))

        ctk.CTkLabel(overlay, text=f"{self.session.format_remaining()} left in this mission",
                     font=ctk.CTkFont(size=20), text_color="#9aa4b2").pack()

        countdown = ctk.CTkLabel(overlay, text="", font=ctk.CTkFont(size=16),
                                 text_color="#6b7480")
        countdown.pack(pady=26)

        ctk.CTkButton(overlay, text="Abort Mission", width=200,
                      fg_color="transparent", border_width=1,
                      text_color="#6b7480", hover_color="#1d2026",
                      command=self._end_session_from_lockdown).pack()
```
Note `COLOR_FOCUS` → `self.color_focus`: this anticipates Task 9 making
the focus color Rider-theme-dependent. If you're doing this task before
Task 9, temporarily leave it as `COLOR_FOCUS` and come back to change
this one reference when Task 9 introduces `self.color_focus` — don't
introduce `self.color_focus` early since nothing defines it yet.

- [ ] **Step 4: Rewrite the streak label**

Find `_refresh_timer_widgets` (around lines 955-960):
```python
        done = self.session.completed_focus_blocks
        until_long = self.session.blocks_until_long_break
        self.streak_label.configure(
            text=f"{done} block{'s' if done != 1 else ''} done · long break in {until_long}",
            text_color=COLOR_LOOK_ACCENT,
        )
```
Change the f-string to:
```python
        self.streak_label.configure(
            text=f"{done} mission{'s' if done != 1 else ''} complete · Full Recovery in {until_long}",
            text_color=COLOR_LOOK_ACCENT,
        )
```

- [ ] **Step 5: Manually verify by running the app**

Run: `python main.py`
Check:
- The header button reads "Henshin" before starting, "Pause" while running.
- Starting a focus block shows the banner "Henshin initiated. Blocking is
  active."
- The streak label reads "N missions complete · Full Recovery in M".
- If you have a blocked app running, let it escalate to a lockdown and
  confirm the fullscreen reads "LOCKDOWN ENGAGED." with an "Abort
  Mission" button that ends the session.

- [ ] **Step 6: Mark task complete** (no git)

---

## Task 7: Fix `.exe`-suffix cross-platform block/allow-list bug

**Files:**
- Modify: `tests/test_enforcer.py` (new test near the `judge()` tests)
- Modify: `lock_in/enforcer.py:148-154`

**Interfaces:**
- Consumes: `WindowInfo(process_name=..., title=...)` (unchanged).
- Produces: `judge()` now matches `process_name` against block/allow
  lists after stripping a trailing `.exe` from both sides — Task 9
  (Linux process-name lookup) and macOS's existing `.lower()`
  `process_name` both rely on this to actually block anything.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_enforcer.py` near the other `judge()` tests:

```python
def test_blocklist_matches_process_without_exe_suffix():
    """macOS/Linux report process names with no .exe — the list still has
    to match, since users shouldn't need a separate list per OS."""
    config = Config(blocklist=["discord.exe"], allowlist=[])
    window = WindowInfo(process_name="discord", title="general #chat")
    verdict = judge(window, config)
    assert verdict.blocked
    assert verdict.reason == Reason.BLOCKLIST


def test_allowlist_matches_process_without_exe_suffix():
    config = Config(blocklist=[], allowlist=["code.exe"])
    window = WindowInfo(process_name="code", title="main.py - lock_in")
    verdict = judge(window, config)
    assert not verdict.blocked
    assert verdict.reason == Reason.ALLOWLIST
```

(`tests/test_enforcer.py` lines 5-14 already import `Config`,
`WindowInfo`, `judge`, and `Reason` at module level — no new imports
needed.)

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_enforcer.py -k without_exe_suffix -v`
Expected: FAIL — `"discord" in {"discord.exe"}` is `False`, so `judge()`
falls through to the classifier/unknown path instead of matching the
blocklist.

- [ ] **Step 3: Implement the fix**

In `lock_in/enforcer.py`, `judge()` currently starts (lines 148-154):
```python
    process = (window.process_name or "").strip().lower()

    if process and process in config.normalised_allowlist():
        return Verdict(False, Reason.ALLOWLIST, 1.0, f"{process} is allow-listed")

    if process and process in config.normalised_blocklist():
        return Verdict(True, Reason.BLOCKLIST, 1.0, f"{process} is block-listed")
```
Change to:
```python
    def _strip_exe(name: str) -> str:
        return name[:-4] if name.endswith(".exe") else name

    process = (window.process_name or "").strip().lower()
    process_bare = _strip_exe(process)
    allowlist_bare = {_strip_exe(name) for name in config.normalised_allowlist()}
    blocklist_bare = {_strip_exe(name) for name in config.normalised_blocklist()}

    if process_bare and process_bare in allowlist_bare:
        return Verdict(False, Reason.ALLOWLIST, 1.0, f"{process} is allow-listed")

    if process_bare and process_bare in blocklist_bare:
        return Verdict(True, Reason.BLOCKLIST, 1.0, f"{process} is block-listed")
```
This keeps `Windows` behavior identical (`"discord.exe"` stripped to
`"discord"` matches a list entry also stripped to `"discord"`) while
making the same lists work when `process_name` arrives with no
extension.

- [ ] **Step 4: Run the tests again**

Run: `pytest tests/test_enforcer.py -v`
Expected: all pass, including every pre-existing `judge()` test (Windows
`.exe`-suffixed matching still works, since both sides get stripped
identically).

- [ ] **Step 5: Mark task complete** (no git)

---

## Task 8: `rider_themes.py` module and `Config.rider_theme` field

**Files:**
- Create: `lock_in/rider_themes.py`
- Test: `tests/test_rider_themes.py` (new)
- Modify: `lock_in/config.py:171-173` (add the new field)

**Interfaces:**
- Produces: `RIDER_THEMES: dict[str, RiderTheme]` (38 entries),
  `DEFAULT_RIDER_THEME: str`, `RiderTheme.primary_pair -> tuple[str,
  str]`, `RiderTheme.secondary_pair -> tuple[str, str]`, `lighten(hex:
  str, factor: float = 0.35) -> str`. `Config.rider_theme: str`. Task 9
  (`ui.py` wiring) consumes all of these by exact name.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rider_themes.py`:

```python
from lock_in.rider_themes import DEFAULT_RIDER_THEME, RIDER_THEMES, lighten


def test_has_all_38_riders():
    assert len(RIDER_THEMES) == 38


def test_default_theme_is_the_original():
    assert DEFAULT_RIDER_THEME == "Kamen Rider (1971)"
    assert DEFAULT_RIDER_THEME in RIDER_THEMES


def test_spot_check_corrected_palette_values():
    # These pin the user-corrected palette so a future edit can't quietly
    # drift back toward the original (wrong) guesses.
    assert RIDER_THEMES["Kamen Rider (1971)"].primary == "#1b5e3a"
    assert RIDER_THEMES["Kamen Rider (1971)"].secondary == "#c0392b"
    assert RIDER_THEMES["Kamen Rider V3 (1973)"].primary == "#2e7d32"
    assert RIDER_THEMES["Kamen Rider Zero-One (2019)"].primary == "#aeea00"
    assert RIDER_THEMES["Kamen Rider Gavv (2024)"].secondary == "#fbc02d"
    assert RIDER_THEMES["Kamen Rider MY-TH (2026)"].primary == "#1565c0"


def test_every_entry_has_valid_hex_colors():
    for name, theme in RIDER_THEMES.items():
        for value in (theme.primary, theme.secondary):
            assert value.startswith("#") and len(value) == 7, f"{name}: {value!r}"


def test_lighten_moves_toward_white():
    assert lighten("#000000", 0.5) == "#7f7f7f"
    assert lighten("#000000", 0.0) == "#000000"
    assert lighten("#000000", 1.0) == "#ffffff"


def test_theme_color_pairs_are_light_dark_tuples():
    theme = RIDER_THEMES["Kamen Rider (1971)"]
    light, dark = theme.primary_pair
    assert light == theme.primary
    assert dark != theme.primary  # the dark-mode variant must actually differ
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_rider_themes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named
'lock_in.rider_themes'`.

- [ ] **Step 3: Create `rider_themes.py`**

```python
"""
rider_themes.py
================
Kamen Rider color themes. Picking a Rider in Settings swaps two colors:
`primary` (the Henshin/focus color -- timer digits, progress bar, phase
label, and the Henshin button) and `secondary` (the button's accent
border and the small "DRIVER: <name>" label under the header). Everything
else in the UI (break green, danger red, tab accents) stays constant
across every theme.

Each entry stores exactly one hex per role; `lighten()` derives a
dark-mode-friendly variant at load time instead of hand-picking a second
shade for every one of the 38 entries.

Palette source: user-corrected against real show reference, see
docs/superpowers/specs/2026-08-07-lock-in-rebrand-design.md section 3.
A handful of ties (OOO, Fourze, Zi-O, Den-O, Saber, Geats each listed
more than one candidate secondary color) were resolved there too --
see that doc if a color here looks surprising.
"""

from __future__ import annotations

from dataclasses import dataclass


def lighten(hex_color: str, factor: float = 0.35) -> str:
    """
    Blend a hex color toward white by `factor` (0 = unchanged, 1 = white).

    Dark mode wants a brighter, less saturated version of the same color
    so text stays readable against a dark background -- the same idea as
    the hand-picked (light, dark) tuples elsewhere in ui.py, just computed
    instead of guessed for all 38 themes.
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = round(r + (255 - r) * factor)
    g = round(g + (255 - g) * factor)
    b = round(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass(frozen=True)
class RiderTheme:
    era: str
    year: int
    primary: str
    secondary: str

    @property
    def primary_pair(self) -> tuple[str, str]:
        return (self.primary, lighten(self.primary))

    @property
    def secondary_pair(self) -> tuple[str, str]:
        return (self.secondary, lighten(self.secondary))


RIDER_THEMES: dict[str, RiderTheme] = {
    "Kamen Rider (1971)": RiderTheme("Showa", 1971, "#1b5e3a", "#c0392b"),
    "Kamen Rider V3 (1973)": RiderTheme("Showa", 1973, "#2e7d32", "#c0392b"),
    "Kamen Rider X (1974)": RiderTheme("Showa", 1974, "#cfd8dc", "#1565c0"),
    "Kamen Rider Amazon (1974)": RiderTheme("Showa", 1974, "#33691e", "#e65100"),
    "Kamen Rider Stronger (1975)": RiderTheme("Showa", 1975, "#c62828", "#212121"),
    "Kamen Rider Skyrider (1979)": RiderTheme("Showa", 1979, "#2e7d32", "#8d6e63"),
    "Kamen Rider Super-1 (1980)": RiderTheme("Showa", 1980, "#e0e0e0", "#212121"),
    "Kamen Rider ZX (1982)": RiderTheme("Showa", 1982, "#c62828", "#b0bec5"),
    "Kamen Rider Black (1987)": RiderTheme("Showa", 1987, "#1a1a1a", "#00c853"),
    "Kamen Rider Black RX (1988)": RiderTheme("Showa", 1988, "#2e7d32", "#1a1a1a"),
    "Kamen Rider Kuuga (2000)": RiderTheme("Heisei", 2000, "#c1272d", "#212121"),
    "Kamen Rider Agito (2001)": RiderTheme("Heisei", 2001, "#ffca28", "#212121"),
    "Kamen Rider Ryuki (2002)": RiderTheme("Heisei", 2002, "#c62828", "#9e9e9e"),
    "Kamen Rider 555 (2003)": RiderTheme("Heisei", 2003, "#111111", "#d50000"),
    "Kamen Rider Blade (2004)": RiderTheme("Heisei", 2004, "#1565c0", "#b0bec5"),
    "Kamen Rider Hibiki (2005)": RiderTheme("Heisei", 2005, "#4a148c", "#c62828"),
    "Kamen Rider Kabuto (2006)": RiderTheme("Heisei", 2006, "#c62828", "#90a4ae"),
    "Kamen Rider Den-O (2007)": RiderTheme("Heisei", 2007, "#c62828", "#eceff1"),
    "Kamen Rider Kiva (2008)": RiderTheme("Heisei", 2008, "#8e0000", "#ffca28"),
    "Kamen Rider Decade (2009)": RiderTheme("Heisei", 2009, "#d81b60", "#212121"),
    "Kamen Rider W (2009)": RiderTheme("Heisei", 2009, "#2e7d32", "#1a1a1a"),
    "Kamen Rider OOO (2010)": RiderTheme("Heisei", 2010, "#1a1a1a", "#c62828"),
    "Kamen Rider Fourze (2011)": RiderTheme("Heisei", 2011, "#ffffff", "#ef6c00"),
    "Kamen Rider Wizard (2012)": RiderTheme("Heisei", 2012, "#c62828", "#212121"),
    "Kamen Rider Gaim (2013)": RiderTheme("Heisei", 2013, "#ef6c00", "#c9a227"),
    "Kamen Rider Drive (2014)": RiderTheme("Heisei", 2014, "#c62828", "#212121"),
    "Kamen Rider Ghost (2015)": RiderTheme("Heisei", 2015, "#1a1a1a", "#ff9800"),
    "Kamen Rider Ex-Aid (2016)": RiderTheme("Heisei", 2016, "#e91e63", "#00e676"),
    "Kamen Rider Build (2017)": RiderTheme("Heisei", 2017, "#c62828", "#1565c0"),
    "Kamen Rider Zi-O (2018)": RiderTheme("Heisei", 2018, "#212121", "#d81b60"),
    "Kamen Rider Zero-One (2019)": RiderTheme("Reiwa", 2019, "#aeea00", "#1a1a1a"),
    "Kamen Rider Saber (2020)": RiderTheme("Reiwa", 2020, "#c62828", "#212121"),
    "Kamen Rider Revice (2021)": RiderTheme("Reiwa", 2021, "#e91e63", "#00e5ff"),
    "Kamen Rider Geats (2022)": RiderTheme("Reiwa", 2022, "#ffffff", "#c62828"),
    "Kamen Rider Gotchard (2023)": RiderTheme("Reiwa", 2023, "#00bcd4", "#ff9800"),
    "Kamen Rider Gavv (2024)": RiderTheme("Reiwa", 2024, "#7b1fa2", "#fbc02d"),
    "Kamen Rider Zeztz (2025)": RiderTheme("Reiwa", 2025, "#2e7d32", "#1a1a1a"),
    "Kamen Rider MY-TH (2026)": RiderTheme("Reiwa", 2026, "#1565c0", "#b0bec5"),
}

DEFAULT_RIDER_THEME = "Kamen Rider (1971)"
```

- [ ] **Step 4: Run the tests again**

Run: `pytest tests/test_rider_themes.py -v`
Expected: all pass. If `test_lighten_moves_toward_white` fails on
rounding (e.g. off by one in `7f` vs `80`), adjust the test's expected
value to match `lighten`'s actual rounding rather than changing the
rounding rule — either is a defensible midpoint, just pick one and keep
the test honest about what the code does.

- [ ] **Step 5: Add the config field**

In `lock_in/config.py`, find the "Looks" section (lines 171-173):
```python
    # --- Looks --------------------------------------------------------------- #
    appearance: str = "dark"              # "dark" | "light" | "system"
    accent: str = "blue"                  # the app's color theme
```
Add a new field after `accent`:
```python
    # --- Looks --------------------------------------------------------------- #
    appearance: str = "dark"              # "dark" | "light" | "system"
    accent: str = "blue"                  # the app's color theme
    rider_theme: str = "Kamen Rider (1971)"   # key into rider_themes.RIDER_THEMES
```
(Don't import `rider_themes` into `config.py` — `config.py` is one of the
"pure logic, stdlib only" modules per the project's own architecture
notes, and the default string here doesn't need the import. `ui.py`
Task 9 is what actually looks the string up in `RIDER_THEMES`.)

- [ ] **Step 6: Run the full test suite**

Run: `pytest`
Expected: all pass — `Config` gaining a field with a default doesn't
break `Config.load()`'s "unknown/missing fields get defaults" contract.

- [ ] **Step 7: Mark task complete** (no git)

---

## Task 9: Wire the Rider theme into `ui.py`

**Files:**
- Modify: `lock_in/ui.py` (imports, `__init__`, header, settings tab,
  `_refresh_timer_widgets`, the `COLOR_FOCUS` reference from Task 6's
  lockdown screen)

**Interfaces:**
- Consumes: `RIDER_THEMES`, `DEFAULT_RIDER_THEME` from `lock_in.rider_themes`
  (Task 8), `config.rider_theme` (Task 8).
- Produces: `self.color_focus: tuple[str, str]`, `self.color_rider_accent:
  tuple[str, str]` — instance attributes other methods and Task 6's
  lockdown screen reference.

No automated test — this is CustomTkinter widget code. Verify manually in
Step 6 by actually running the app (this machine can run it; it's a
desktop GUI, not headless).

- [ ] **Step 1: Import the theme module**

At the top of `lock_in/ui.py`, alongside the existing relative imports:
```python
from .session import Event, Phase, PomodoroSession
```
add:
```python
from .rider_themes import DEFAULT_RIDER_THEME, RIDER_THEMES
```

- [ ] **Step 2: Compute the theme colors in `__init__`**

In `__init__`, right after this existing line:
```python
        self.config_obj = Config.load()
```
add:
```python
        self._apply_rider_theme()
```

Then add a new method (near the other `_on_*`/`_apply_*` helpers, after
`__init__`):
```python
    def _apply_rider_theme(self) -> None:
        """Recompute the two Rider-driven colors from the current config."""
        theme = RIDER_THEMES.get(
            self.config_obj.rider_theme, RIDER_THEMES[DEFAULT_RIDER_THEME]
        )
        self.color_focus = theme.primary_pair
        self.color_rider_accent = theme.secondary_pair
```

- [ ] **Step 3: Use `self.color_focus` instead of `COLOR_FOCUS`**

In `_refresh_timer_widgets`, find:
```python
        color = {
            Phase.FOCUS: COLOR_FOCUS,
            Phase.SHORT_BREAK: COLOR_BREAK,
            Phase.LONG_BREAK: COLOR_BREAK,
            Phase.IDLE: COLOR_IDLE,
        }[phase]
```
Change to:
```python
        color = {
            Phase.FOCUS: self.color_focus,
            Phase.SHORT_BREAK: COLOR_BREAK,
            Phase.LONG_BREAK: COLOR_BREAK,
            Phase.IDLE: COLOR_IDLE,
        }[phase]
```

If Task 6 was done first and left a `COLOR_FOCUS` reference in
`_show_lockdown`, change that one too:
```python
        ctk.CTkLabel(overlay, text="LOCKDOWN ENGAGED.",
                     font=ctk.CTkFont(size=54, weight="bold"),
                     text_color=self.color_focus).pack(pady=(220, 10))
```

The module-level `COLOR_FOCUS = "#e2483d"` constant (near the top of the
file) can stay defined but unused, or be deleted — check for any other
reference with `grep -n "COLOR_FOCUS" lock_in/ui.py` before deleting it;
if nothing else uses it, delete the line to avoid dead code.

- [ ] **Step 4: Style the Henshin button and add a driver label**

In `_build_header`, find the Henshin button (renamed in Task 6):
```python
        self.start_button = ctk.CTkButton(
            controls, text="Henshin", width=140, height=40,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._on_toggle,
        )
```
Give it the Rider's colors:
```python
        self.start_button = ctk.CTkButton(
            controls, text="Henshin", width=140, height=40,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._on_toggle,
            fg_color=self.color_rider_accent,
        )
```

Then, right after the existing `self.streak_label` block in
`_build_header` (after `self.streak_label.pack()`), add a small driver
identity label:
```python
        self.driver_label = ctk.CTkLabel(
            header, text=f"DRIVER: {self.config_obj.rider_theme.upper()}",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=self.color_rider_accent,
        )
        self.driver_label.pack(pady=(2, 0))
```

- [ ] **Step 5: Add the Settings tab dropdown**

In `_build_settings_tab`, right after the existing Appearance row (after
`self.appearance_menu.pack(side="left")`), add:
```python
        rider_row = ctk.CTkFrame(frame, fg_color="transparent")
        rider_row.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(rider_row, text="Kamen Rider theme", width=260, anchor="w").pack(side="left")
        self.rider_menu = ctk.CTkOptionMenu(
            rider_row, values=list(RIDER_THEMES.keys()), width=220,
            command=self._on_rider_theme_change,
        )
        self.rider_menu.set(self.config_obj.rider_theme)
        self.rider_menu.pack(side="left")
```

Then add the handler near `_on_appearance_change`:
```python
    def _on_rider_theme_change(self, value: str) -> None:
        self.config_obj.rider_theme = value
        self.config_obj.save()
        self._apply_rider_theme()
        self.driver_label.configure(text=f"DRIVER: {value.upper()}", text_color=self.color_rider_accent)
        self.start_button.configure(fg_color=self.color_rider_accent)
        self._refresh_timer_widgets()
```

- [ ] **Step 6: Manually verify**

Run: `python main.py`
Check:
- The header shows "DRIVER: KAMEN RIDER (1971)" under the streak label.
- The Henshin button is tinted green (the 1971 primary/accent).
- Settings tab → "Kamen Rider theme" dropdown lists all 38 names.
- Picking a different Rider (e.g. "Kamen Rider 555 (2003)") immediately
  changes the driver label text and the Henshin button color, and
  starting a focus block now shows the timer digits/progress bar in that
  Rider's primary color instead of the default.
- Restart the app — the previously selected theme should persist (it's
  saved to `config.json`).

- [ ] **Step 7: Mark task complete** (no git)

---

## Task 10: Cross-platform `monitor.py` (Linux process name + real minimize)

**Files:**
- Modify: `lock_in/monitor.py:46-55` (optional-import block)
- Modify: `lock_in/monitor.py:120-129` (`_active_window_linux`)
- Modify: `lock_in/monitor.py:146-160` (`minimize_window`)

**Interfaces:**
- Produces: `minimize_window(handle) -> bool` now works (best-effort) on
  all three platforms, not just Windows. `get_active_window()` on Linux
  now populates `process_name`, not just `title`.

No automated test for the platform-specific subprocess calls themselves
(they need the real OS tool installed) — verify via Step 4's import/smoke
check on this machine, and flag mac/Linux behavior for the user to
confirm on those OSes.

- [ ] **Step 1: Decouple `psutil` from the Windows-only import block**

Currently (lines 46-57):
```python
_win32gui = _win32process = _win32con = _psutil = None

if IS_WINDOWS:
    try:
        import win32gui as _win32gui          # type: ignore
        import win32process as _win32process  # type: ignore
        import win32con as _win32con          # type: ignore
        import psutil as _psutil              # type: ignore
    except ImportError:  # pragma: no cover - depends on install
        _win32gui = _win32process = _win32con = _psutil = None
```
Change to:
```python
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
    # psutil is used on Windows (already) and now Linux, to turn a PID
    # from xdotool into a process name for block/allow-list matching.
    import psutil as _psutil              # type: ignore
except ImportError:  # pragma: no cover - depends on install
    _psutil = None
```

- [ ] **Step 2: Give Linux a process name, not just a title**

Currently (lines 120-129):
```python
def _active_window_linux() -> WindowInfo:
    """Try to read the active window using xdotool. Gives back nothing if it's not installed."""
    try:
        title = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        return WindowInfo(process_name="", title=title)
    except Exception:
        return WindowInfo()
```
Change to:
```python
def _active_window_linux() -> WindowInfo:
    """
    Try to read the active window using xdotool. Gives back nothing if
    it's not installed.

    Also looks up the owning process's name via its PID, the same way the
    Windows backend does with psutil -- without this, block/allow-list
    entries like "discord.exe" would only ever match through the
    title-text fallback, never directly.
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
            # Some windows (browser popups, some non-native toolkits)
            # don't report a PID -- fall back to title-only, same as
            # before this lookup existed.
            process_name = ""

        return WindowInfo(process_name=process_name, title=title)
    except Exception:
        return WindowInfo()
```

- [ ] **Step 3: Make `minimize_window` work on macOS and Linux**

Currently (lines 146-160):
```python
def minimize_window(handle: Optional[int]) -> bool:
    """
    Shrink the given window down to the taskbar. Returns True if it probably worked.

    We shrink it rather than fully hide it — a fully hidden window disappears
    from the taskbar with no visible way to bring it back, which would be
    genuinely annoying if we ever guessed wrong about a window.
    """
    if _win32gui is None or not handle:
        return False
    try:
        _win32gui.ShowWindow(handle, _win32con.SW_MINIMIZE)
        return True
    except Exception:
        return False
```
Change to:
```python
def minimize_window(handle: Optional[int]) -> bool:
    """
    Minimize whichever window is currently in front. Returns True if it
    probably worked.

    On Windows this acts on the exact handle you pass in. macOS and Linux
    have no equivalent handle available here, so both act on whatever
    window is currently active -- which is fine, since this is always
    called immediately after `judge()` confirms that window is still the
    one you're on.

    We minimize rather than fully hide -- a fully hidden window disappears
    with no visible way to bring it back, which would be genuinely
    annoying if we ever guessed wrong about a window.
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
        # Simulating Cmd+M is the standard way to minimize the frontmost
        # window from a script on macOS. This needs Accessibility
        # permission for whatever process runs this (Terminal, or the
        # packaged app) -- macOS will prompt for it the first time this
        # runs, and blocking silently does nothing until it's granted.
        try:
            script = 'tell application "System Events" to keystroke "m" using command down'
            result = subprocess.run(
                ["osascript", "-e", script], timeout=2, capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    if sys.platform.startswith("linux"):
        # X11 only -- xdotool has no Wayland equivalent, so this silently
        # does nothing under a Wayland session. That's a real limitation,
        # not a bug to chase here.
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "windowminimize"],
                timeout=2, capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    return False
```

- [ ] **Step 4: Verify nothing broke on Windows**

Run: `pytest`
Expected: all pass (no test exercises the real subprocess calls, but this
confirms nothing in the file fails to import/parse).

Run: `python -c "import lock_in.monitor; print(lock_in.monitor.BACKEND_AVAILABLE)"`
Expected: prints `True` with no exception.

- [ ] **Step 5: Flag for real-OS verification**

This task's macOS and Linux branches are written to each OS's documented
mechanism but not run here (this machine is Windows). Note in your final
summary to the user that `minimize_window` on macOS needs an Accessibility
permission grant on first use, and on Linux needs `xdotool` installed and
an X11 (not Wayland) session — both should be manually confirmed on real
hardware before relying on them.

- [ ] **Step 6: Mark task complete** (no git)

---

## Task 11: Cross-platform `notifier.py` (macOS/Linux toasts and sound)

**Files:**
- Modify: `lock_in/notifier.py` (imports, `_toast`, `phase_chime`,
  `alert_sound`, plus two new private helpers)

**Interfaces:**
- Produces: `Notifier.notify/phase_chime/alert_sound` now degrade
  gracefully through Windows → macOS → Linux → in-app banner, instead of
  Windows → in-app banner.

No automated test (same reasoning as Task 10 — these call real OS
binaries). Verify via Step 5's import check plus manual confirmation on
macOS/Linux.

- [ ] **Step 1: Add the new imports and platform/tool detection**

At the top of `lock_in/notifier.py`, change:
```python
from __future__ import annotations

import sys
import threading
from typing import Optional

IS_WINDOWS = sys.platform == "win32"
```
to:
```python
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

_HAS_NOTIFY_SEND = IS_LINUX and shutil.which("notify-send") is not None
_HAS_PAPLAY = IS_LINUX and shutil.which("paplay") is not None
_HAS_APLAY = IS_LINUX and shutil.which("aplay") is not None

# In rough order of preference -- paplay (PulseAudio) plays Ogg files
# fine; if only aplay (plain ALSA) is present, a system Ogg won't work,
# but this is still better than silence on a machine with no PulseAudio.
_LINUX_SOUND_CANDIDATES = [
    "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga",
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
]
```

- [ ] **Step 2: Add macOS/Linux branches to `_toast`**

Currently:
```python
    def _toast(self, title: str, body: str, urgency: str) -> None:
        """Show a real Windows pop-up if we have the tool for it; otherwise do nothing."""
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
```
Change to:
```python
    def _toast(self, title: str, body: str, urgency: str) -> None:
        """Show a real OS pop-up if we have a way to; otherwise do nothing."""
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
                    # AppleScript string literals escape a double quote
                    # by backslash-prefixing it -- without this, a window
                    # title containing a quote would break the script.
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
```

- [ ] **Step 3: Add macOS/Linux sound helpers, and use them from `phase_chime`/`alert_sound`**

Currently:
```python
    def phase_chime(self, starting_phase_label: str) -> None:
        """A soft, friendly two-note chime when a new phase (focus or break) starts."""
        if not self.config.sound_enabled or _winsound is None:
            return
        self._beep_sequence([(880, 140), (1175, 220)])

    def alert_sound(self) -> None:
        """A sharper three-note sound for when you need a nudge back to work."""
        if not self.config.sound_enabled or _winsound is None:
            return
        self._beep_sequence([(1000, 110), (760, 110), (1000, 160)])
```
Change to:
```python
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

    def _play_mac_sound(self, path: str, repeat: int = 1) -> None:
        """Play a bundled macOS system sound on its own thread, so it can't freeze the UI."""
        def run() -> None:
            try:
                for _ in range(repeat):
                    subprocess.run(["afplay", path], timeout=3, capture_output=True)
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    def _play_linux_sound(self, repeat: int = 1) -> None:
        """Play whichever known system sound file actually exists, via paplay or aplay."""
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
```

- [ ] **Step 4: Update the module docstring's "three ways" list**

Near the top of the file, the docstring currently says:
```
It tries three ways to get your attention, in order of how gentle they are:

  1. A real Windows pop-up (using `winotify`, if it's installed) — shows up
     quietly without stealing your focus.
  2. A sound (using `winsound`, which comes built into Windows) — simple,
     and hard to miss.
  3. A little banner inside the app itself — always works, no matter what.
```
Change to:
```
It tries three ways to get your attention, in order of how gentle they are:

  1. A real OS pop-up (winotify on Windows, `osascript` on macOS,
     `notify-send` on Linux if installed) — shows up quietly without
     stealing your focus.
  2. A sound (winsound on Windows, `afplay` on macOS, `paplay`/`aplay` on
     Linux) — simple, and hard to miss.
  3. A little banner inside the app itself — always works, no matter what.
```

- [ ] **Step 5: Verify nothing broke on Windows**

Run: `pytest`
Expected: all pass.

Run: `python -c "import lock_in.notifier"`
Expected: no exception.

- [ ] **Step 6: Flag for real-OS verification**

Same as Task 10 — note in the final summary that the macOS/Linux toast
and sound paths are written but unverified on real hardware.

- [ ] **Step 7: Mark task complete** (no git)

---

## Task 12: README rewrite

**Files:**
- Modify: `README.md` (whole file)

**Interfaces:** none — documentation only.

- [ ] **Step 1: Update naming throughout**

Change the title (`# FocusLock` → `# Lock In`) and every other
"FocusLock" occurrence in the file (lines 1, 49, 91, 114, 338, 381, 419)
to "Lock In". **Leave alone** every occurrence of the generic word
"Pomodoro" on its own (lines 3, 8, 204, 333, 349, etc.) — that's the
technique name, not the app's brand name, and isn't being renamed
anywhere else in the codebase either (see `claude_fallback.py`'s "your
Pomodoro timer" phrase, which the spec also leaves untouched). Change the
project-structure tree's `pomodoro_lock/` to `lock_in/` (line 343), and
add `rider_themes.py` to the listed files there:
```
├── lock_in/                     The application package.
│   ├── __init__.py              Marks this folder as a package.
│   │
│   │   ── pure logic, stdlib only, fully unit-tested ──
│   ├── config.py                Settings dataclass, JSON persistence, block/allow
│   │                             defaults, and the %APPDATA% path resolution.
│   ├── session.py                Pomodoro state machine. Injectable clock, so tests
│   │                             run four-hour sessions instantly.
│   ├── classifier.py             Naive Bayes study/distraction model, tokenizer,
│   │                             seed corpus, explain(), JSON persistence.
│   ├── enforcer.py               judge() applies allowlist → blocklist → model.
│   │                             Enforcer() runs the strike/escalation ladder.
│   ├── observations.py           Records every window seen during focus and tracks
│   │                             which have been labelled. Backs train.py.
│   ├── rider_themes.py           Kamen Rider color palettes for the theme toggle.
│   │
│   │   ── platform-facing shells, thin by design ──
│   ├── monitor.py                Foreground-window polling on a daemon thread.
│   │                             Win32 backend, macOS (osascript), Linux (xdotool).
│   ├── notifier.py               Toasts and sounds: winotify/winsound (Windows),
│   │                             osascript/afplay (macOS), notify-send/paplay (Linux).
│   └── ui.py                     CustomTkinter front end. The only module that
│                                 imports tkinter.
```

- [ ] **Step 2: Update the intro paragraph for the serious tone**

Replace the opening two lines:
```
A Pomodoro timer that notices when you've drifted onto Discord and does
something about it.
```
with:
```
A Pomodoro timer that notices when you've drifted onto Discord and does
something about it — Henshin into a focus block, and Lock In makes
leaving it a deliberate decision, not an absent-minded one.
```

- [ ] **Step 3: Add a "Kamen Rider theme" section**

Add a new section after "## The model" (before "## Training it"):
```markdown
## Kamen Rider theme

Settings → "Kamen Rider theme" picks from all 38 Rider series (Showa,
Heisei, and Reiwa era), each with its own accent-color pair pulled from
that Rider's actual suit colors. This only changes colors — the Henshin
button, the timer digits/progress bar during a focus block, and a small
"DRIVER: <name>" label — not any copy or behavior. Defaults to the
original 1971 series. See `lock_in/rider_themes.py` for the full palette.
```

- [ ] **Step 4: Rewrite "Known limits" for real cross-platform behavior**

Replace the existing "Known limits" section's platform bullet:
```
- **Windows is the real target.** macOS gets read-only detection via
  AppleScript (no minimising — that needs Accessibility permission). Linux gets
  read-only detection if `xdotool` happens to be installed.
```
with:
```
- **Windows, macOS, and Linux are all supported**, though Windows has the
  most mileage. macOS minimizing simulates Cmd+M via System Events, which
  needs Accessibility permission — macOS prompts for it the first time
  blocking tries to act. Linux detection and minimizing need `xdotool`
  installed and an X11 session — there's no Wayland equivalent, so
  blocking silently can't minimize windows under Wayland (detection still
  works). Toasts and sounds use `notify-send`/`paplay`/`aplay` on Linux
  and `osascript`/`afplay` on macOS, falling back to the in-app banner if
  those tools aren't present, exactly like the Windows toast falls back
  when `winotify` isn't installed.
```

- [ ] **Step 5: Add a "Releases" section**

Add near the end, before "## License":
```markdown
## Releases

Tagged releases (`vX.Y.Z`) are built automatically for Windows, macOS,
and Linux via GitHub Actions and published to
[Releases](https://github.com/SVerma2696/lock-in/releases) — download the
one for your OS rather than building from source. Every push and pull
request also runs the test suite on all three OSes
(`.github/workflows/tests.yml`); a release only builds on a version tag
(`.github/workflows/release.yml`).

The macOS build isn't code-signed or notarized, so Gatekeeper will call it
from an "unidentified developer" the first time you open it — right-click
→ Open once to bypass that.
```

- [ ] **Step 6: Proofread**

Read through the whole file once. Confirm:
- No remaining "FocusLock" or "pomodoro_lock" strings
  (`grep -in "focuslock\|pomodoro_lock" README.md` should print nothing).
- The project-structure tree matches the actual file list (run `ls
  lock_in/` and compare).

- [ ] **Step 7: Mark task complete** (no git)

---

## Task 13: GitHub Actions workflows

**Files:**
- Create: `.github/workflows/tests.yml`
- Create: `.github/workflows/release.yml`

**Interfaces:** none — these are CI configuration, not consumed by any
Python code.

These can't be executed here (no `.git`, no GitHub connection) — validate
by parsing the YAML, and leave real end-to-end verification for after the
user pushes/tags per their own process.

- [ ] **Step 1: Create the test workflow**

Create `.github/workflows/tests.yml`:
```yaml
name: Tests

on:
  push:
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest
```

- [ ] **Step 2: Create the release workflow**

Create `.github/workflows/release.yml`:
```yaml
name: Release

on:
  push:
    tags:
      - "v*.*.*"

permissions:
  contents: write

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            asset_name: LockIn-Windows.zip
          - os: macos-latest
            asset_name: LockIn-macOS.zip
          - os: ubuntu-latest
            asset_name: LockIn-Linux.tar.gz
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Build (Windows)
        if: runner.os == 'Windows'
        run: pyinstaller --noconfirm --onefile --windowed --name "Lock In" --hidden-import win32gui --hidden-import win32process --hidden-import win32con --hidden-import psutil --collect-all customtkinter main.py

      - name: Build (macOS/Linux)
        if: runner.os != 'Windows'
        run: pyinstaller --noconfirm --onefile --windowed --name "Lock In" --collect-all customtkinter main.py

      - name: Package (Windows)
        if: runner.os == 'Windows'
        shell: pwsh
        run: |
          Compress-Archive -Path "dist/Lock In.exe" -DestinationPath "${{ matrix.asset_name }}"

      - name: Package (macOS)
        if: matrix.os == 'macos-latest'
        run: |
          cd dist
          zip -r "../${{ matrix.asset_name }}" "Lock In.app"

      - name: Package (Linux)
        if: matrix.os == 'ubuntu-latest'
        run: |
          cd dist
          tar -czf "../${{ matrix.asset_name }}" "Lock In"

      - uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.asset_name }}
          path: ${{ matrix.asset_name }}

  publish:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: artifacts
          merge-multiple: true
      - name: Create release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release create "${{ github.ref_name }}" artifacts/*.zip artifacts/*.tar.gz \
            --repo "${{ github.repository }}" \
            --title "Lock In ${{ github.ref_name }}" \
            --generate-notes
```

- [ ] **Step 3: Validate both files parse as YAML**

Run:
```bash
python -c "import yaml, sys; [yaml.safe_load(open(f)) for f in ['.github/workflows/tests.yml', '.github/workflows/release.yml']]; print('both valid')"
```
Expected: prints `both valid`. If `yaml` isn't installed
(`pyyaml` isn't in `requirements.txt`), run
`pip install pyyaml` first just for this check — it's not a project
dependency, only a local validation tool.

- [ ] **Step 4: Mark task complete** (no git — and no workflow will
  actually run until the user pushes this to GitHub themselves)

---

## Handoff: what the user runs themselves

None of the above touched git. Once every task is complete, the user
runs (not the implementer):

```bash
git init
git add .
git commit -m "Rename to Lock In, add Kamen Rider theming, cross-platform support, and release CI"
git remote add origin https://github.com/SVerma2696/lock-in.git
git push -u origin main
git tag v1.0.0
git push origin v1.0.0    # this is what triggers the release build
```
