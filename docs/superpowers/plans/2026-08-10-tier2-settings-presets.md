# Lock In: Tier 2 Settings Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give 3 Riders (Kuuga, Super-1, Gavv) quick-access controls in the Settings tab that adjust the Pomodoro timer's interval lengths — Kuuga and Super-1 as one-click preset buttons, Gavv as a toggle.

**Architecture:** A new pure-data module `lock_in/presets.py` (mirroring `rider_themes.py`'s role) holds the preset tables. `Config` gains one new field (`micro_sprint_mode`) and a priority check inside `phase_seconds()`. In `ui.py`, the preset/toggle rows are built **conditionally inline** inside `_build_settings_tab()` — not as persistent show/hide widgets like Tier 1's progress shape. This is deliberate: `_rebuild_tabs()` already tears down and rebuilds the whole Settings tab from scratch on every Rider change (confirmed by reading the existing `_on_rider_theme_change()`/`_rebuild_tabs()` code), so there is nothing to toggle — the tab just gets rebuilt with only the matching Rider's row present, the same way every other Rider-dependent color in this tab already works.

**Tech Stack:** Python 3.11+, dataclasses (pure data), CustomTkinter, pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-10-tier2-settings-presets-design.md` — this plan implements it in full; no other tier.
- Purely a settings/UX feature — no blocking-logic changes.
- No git commands as part of any task. The user runs every git step themselves.
- Comments stay "simple enough for a 5 year old to understand" — short, plain-English, explain *why* not *what*, matching every existing comment in this codebase.
- TDD: every new function gets a failing test first, then the minimal implementation.
- Applying a preset never touches an already-running phase — `session.py`'s `_advance()` captures a phase's duration once, at the moment it starts, so a `Config` change only applies "from the next phase" (already true today, not something this plan needs to build).

---

### Task 1: `lock_in/presets.py` — the preset data

**Files:**
- Create: `lock_in/presets.py`
- Test: `tests/test_presets.py`

**Interfaces:**
- Produces: `TimerPreset` (frozen dataclass: `name_tokusatsu: str`, `name_professional: str`, `focus_minutes: int`, `short_break_minutes: int`, `long_break_minutes: int`, `blocks_until_long_break: int`, `description: str = ""`), `KUUGA_PRESETS: list[TimerPreset]` (4 entries), `SUPER1_PRESETS: list[TimerPreset]` (5 entries), `GAVV_MICRO_SPRINT: TimerPreset` (1 instance).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_presets.py`:

```python
from lock_in.presets import GAVV_MICRO_SPRINT, KUUGA_PRESETS, SUPER1_PRESETS, TimerPreset


def test_kuuga_has_exactly_4_presets():
    assert len(KUUGA_PRESETS) == 4


def test_kuuga_preset_values():
    by_name = {p.name_tokusatsu: p for p in KUUGA_PRESETS}
    assert by_name["Mighty"] == TimerPreset("Mighty", "Standard (25m)", 25, 5, 15, 4)
    assert by_name["Dragon"] == TimerPreset("Dragon", "Quick Sprint (10m)", 10, 3, 10, 5)
    assert by_name["Pegasus"] == TimerPreset("Pegasus", "Deep Work (50m)", 50, 10, 20, 3)
    assert by_name["Titan"] == TimerPreset("Titan", "Endurance (90m)", 90, 15, 30, 2)


def test_super1_has_exactly_5_presets():
    assert len(SUPER1_PRESETS) == 5


def test_super1_preset_values():
    by_name = {p.name_tokusatsu: p for p in SUPER1_PRESETS}
    assert by_name["Super Hand"] == TimerPreset(
        "Super Hand", "Development (25m)", 25, 5, 15, 4,
        "General software development",
    )
    assert by_name["Power Hand"] == TimerPreset(
        "Power Hand", "Hardware/Embedded (50m)", 50, 10, 20, 3,
        "Hardware & embedded engineering",
    )
    assert by_name["Elek Hand"] == TimerPreset(
        "Elek Hand", "Admin (15m)", 15, 5, 15, 4,
        "Admin & correspondence",
    )
    assert by_name["Cold/Thermal Hand"] == TimerPreset(
        "Cold/Thermal Hand", "Logic/AI (45m)", 45, 10, 20, 3,
        "Logic & AI implementation",
    )
    assert by_name["Radar Hand"] == TimerPreset(
        "Radar Hand", "Research (30m)", 30, 5, 15, 4,
        "Network analysis & research",
    )


def test_gavv_micro_sprint_values():
    assert GAVV_MICRO_SPRINT == TimerPreset(
        "Bite-Sized Mode", "Micro-Sprint Mode", 10, 8, 15, 2,
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_presets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lock_in.presets'`

- [ ] **Step 3: Write the implementation**

Create `lock_in/presets.py`:

```python
"""
presets.py
==========
This file is a small list of ready-made timer-length bundles. A few
Riders in Settings (Kuuga, Super-1, Gavv) show buttons or a switch that
apply one of these bundles all at once, instead of you typing 4 numbers
in by hand.

This file doesn't know anything about buttons or Settings tabs -- it
just lists the numbers. ui.py is the one that turns these into
something you can click.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimerPreset:
    """One ready-made bundle of timer lengths, with a name in each wording style."""

    name_tokusatsu: str
    name_professional: str
    focus_minutes: int
    short_break_minutes: int
    long_break_minutes: int
    blocks_until_long_break: int
    # A short line explaining what this preset is FOR. Only Super-1's
    # presets use this today -- Kuuga's names are self-explanatory
    # enough on their own (a "25m" button doesn't need extra text).
    description: str = ""


KUUGA_PRESETS: list[TimerPreset] = [
    TimerPreset("Mighty", "Standard (25m)", 25, 5, 15, 4),
    TimerPreset("Dragon", "Quick Sprint (10m)", 10, 3, 10, 5),
    TimerPreset("Pegasus", "Deep Work (50m)", 50, 10, 20, 3),
    TimerPreset("Titan", "Endurance (90m)", 90, 15, 30, 2),
]

SUPER1_PRESETS: list[TimerPreset] = [
    TimerPreset(
        "Super Hand", "Development (25m)", 25, 5, 15, 4,
        "General software development",
    ),
    TimerPreset(
        "Power Hand", "Hardware/Embedded (50m)", 50, 10, 20, 3,
        "Hardware & embedded engineering",
    ),
    TimerPreset(
        "Elek Hand", "Admin (15m)", 15, 5, 15, 4,
        "Admin & correspondence",
    ),
    TimerPreset(
        "Cold/Thermal Hand", "Logic/AI (45m)", 45, 10, 20, 3,
        "Logic & AI implementation",
    ),
    TimerPreset(
        "Radar Hand", "Research (30m)", 30, 5, 15, 4,
        "Network analysis & research",
    ),
]

# Gavv's toggle doesn't pick from a list -- it's always this one bundle,
# read straight off of Config.phase_seconds() while the switch is on.
GAVV_MICRO_SPRINT = TimerPreset("Bite-Sized Mode", "Micro-Sprint Mode", 10, 8, 15, 2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_presets.py -v`
Expected: PASS — all 5 tests.

- [ ] **Step 5: Commit**

```bash
git add lock_in/presets.py tests/test_presets.py
git commit -m "feat: add Tier 2 timer preset data (Kuuga, Super-1, Gavv)"
```

---

### Task 2: Gavv's micro-sprint override in `Config`

**Files:**
- Modify: `lock_in/config.py`
- Test: `tests/test_config.py` (new file — `Config` has no dedicated test file yet)

**Interfaces:**
- Consumes: `lock_in.presets.GAVV_MICRO_SPRINT` (Task 1).
- Produces: `Config.micro_sprint_mode: bool` (new field, default `False`). `Config.phase_seconds(phase_name)` now checks it first.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config.py`:

```python
from lock_in.config import Config
from lock_in.presets import GAVV_MICRO_SPRINT


def test_phase_seconds_uses_normal_settings_by_default():
    config = Config(focus_minutes=25, short_break_minutes=5, long_break_minutes=15)
    assert config.phase_seconds("focus") == 25 * 60
    assert config.phase_seconds("short_break") == 5 * 60
    assert config.phase_seconds("long_break") == 15 * 60


def test_phase_seconds_uses_gavv_values_when_micro_sprint_mode_is_on():
    config = Config(focus_minutes=25, short_break_minutes=5, long_break_minutes=15,
                     micro_sprint_mode=True)
    assert config.phase_seconds("focus") == GAVV_MICRO_SPRINT.focus_minutes * 60
    assert config.phase_seconds("short_break") == GAVV_MICRO_SPRINT.short_break_minutes * 60
    assert config.phase_seconds("long_break") == GAVV_MICRO_SPRINT.long_break_minutes * 60


def test_micro_sprint_mode_defaults_to_off():
    assert Config().micro_sprint_mode is False


def test_turning_micro_sprint_mode_off_restores_normal_settings():
    """Flipping the switch back never has to "remember" anything -- your
    real settings were never touched in the first place."""
    config = Config(focus_minutes=25, micro_sprint_mode=True)
    assert config.phase_seconds("focus") == GAVV_MICRO_SPRINT.focus_minutes * 60
    config.micro_sprint_mode = False
    assert config.phase_seconds("focus") == 25 * 60
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `TypeError: Config.__init__() got an unexpected keyword argument 'micro_sprint_mode'`

- [ ] **Step 3: Write the implementation**

In `lock_in/config.py`, add the import near the top:

```python
from .presets import GAVV_MICRO_SPRINT
```

Add the new field to the `Config` dataclass, right after the existing `blocks_until_long_break` line:

```python
    blocks_until_long_break: int = 4      # focus rounds before a big break
    # Gavv's toggle: while this is on, phase_seconds() below hands back
    # GAVV_MICRO_SPRINT's short values instead of the 4 lines above --
    # your real numbers are never overwritten, just temporarily ignored.
    micro_sprint_mode: bool = False
```

Replace `phase_seconds()`:

```python
    def phase_seconds(self, phase_name: str) -> int:
        """Turn a phase's name into how many seconds it should last."""
        if self.micro_sprint_mode:
            minutes = {
                "focus": GAVV_MICRO_SPRINT.focus_minutes,
                "short_break": GAVV_MICRO_SPRINT.short_break_minutes,
                "long_break": GAVV_MICRO_SPRINT.long_break_minutes,
            }[phase_name]
            return minutes * 60
        return {
            "focus": self.focus_minutes * 60,
            "short_break": self.short_break_minutes * 60,
            "long_break": self.long_break_minutes * 60,
        }[phase_name]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS — all 4 tests.

Then run the full suite to make sure nothing that already depended on `phase_seconds()` broke:

Run: `pytest -q`
Expected: PASS — full suite (this only adds a new default-off field and an early-return branch, existing behavior is unchanged when `micro_sprint_mode` is `False`).

- [ ] **Step 5: Commit**

```bash
git add lock_in/config.py tests/test_config.py
git commit -m "feat: add Gavv's micro-sprint mode override to Config.phase_seconds"
```

---

### Task 3: Kuuga & Super-1 preset button rows in Settings

**Files:**
- Modify: `lock_in/ui.py`

**Interfaces:**
- Consumes: `lock_in.presets.TimerPreset`, `KUUGA_PRESETS`, `SUPER1_PRESETS` (Task 1). `self.spinners: dict[str, ctk.CTkEntry]` (already exists, built earlier in `_build_settings_tab`). `self._is_tokusatsu()` (already exists).
- Produces: `self._build_timer_preset_row(parent, presets: list[TimerPreset], heading: str) -> None`, `self._apply_timer_preset(preset: TimerPreset) -> None` — both used by Task 4 too (Gavv's row doesn't call these, but reuses the same section-heading style).

- [ ] **Step 1: Add the import**

In `lock_in/ui.py`, add to the existing import block near the top:

```python
from .presets import GAVV_MICRO_SPRINT, KUUGA_PRESETS, SUPER1_PRESETS, TimerPreset
```

- [ ] **Step 2: Insert the conditional preset row**

In `_build_settings_tab()`, right after the Rider-theme dropdown block (find the lines ending in `self.rider_menu.pack(side="left")`), insert:

```python
        self.rider_menu.set(self.config_obj.rider_theme)
        self.rider_menu.pack(side="left")

        # Kuuga/Super-1's preset buttons and Gavv's toggle only show up
        # for their own Rider -- this whole tab already gets rebuilt
        # from scratch every time you pick a different Rider (see
        # _rebuild_tabs), so there's nothing to hide/show here, we just
        # build whichever ONE row (if any) actually matches right now.
        if self.config_obj.rider_theme == "Kamen Rider Kuuga (2000)":
            self._build_timer_preset_row(
                frame, KUUGA_PRESETS,
                "Kuuga presets" if self._is_tokusatsu() else "Interval presets",
            )
        elif self.config_obj.rider_theme == "Kamen Rider Super-1 (1980)":
            self._build_timer_preset_row(
                frame, SUPER1_PRESETS,
                "Super-1's Five Hands" if self._is_tokusatsu() else "Task-type presets",
            )
        elif self.config_obj.rider_theme == "Kamen Rider Gavv (2024)":
            self._build_gavv_toggle_row(frame)
```

- [ ] **Step 3: Add `_build_timer_preset_row` and `_apply_timer_preset`**

Add these as new methods on `LockInApp` (anywhere in the Settings-tab-building section of the file, e.g. right after `_build_settings_tab`):

```python
    def _build_timer_preset_row(
        self, parent, presets: list[TimerPreset], heading: str,
    ) -> None:
        """
        One row of small buttons, one per preset. Clicking a button
        calls _apply_timer_preset with THAT preset -- the button itself
        doesn't know or care what the numbers mean, it just hands over
        the whole bundle.
        """
        ctk.CTkLabel(parent, text=heading, text_color=COLOR_TIMER_ACCENT,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(14, 4))

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 4))

        for preset in presets:
            button_name = preset.name_tokusatsu if self._is_tokusatsu() else preset.name_professional
            column = ctk.CTkFrame(row, fg_color="transparent")
            column.pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                column, text=button_name, width=90,
                fg_color=COLOR_TIMER_ACCENT,
                command=lambda p=preset: self._apply_timer_preset(p),
            ).pack()
            if preset.description:
                ctk.CTkLabel(
                    column, text=preset.description, font=ctk.CTkFont(size=9),
                    text_color=COLOR_IDLE, wraplength=90,
                ).pack(pady=(2, 0))

    def _apply_timer_preset(self, preset: TimerPreset) -> None:
        """
        Copies one preset's 4 numbers into Config, updates the number
        boxes on screen so they show what just happened, and saves --
        same save path _save_settings() already uses, so this behaves
        exactly like typing the numbers in yourself.
        """
        self.config_obj.focus_minutes = preset.focus_minutes
        self.config_obj.short_break_minutes = preset.short_break_minutes
        self.config_obj.long_break_minutes = preset.long_break_minutes
        self.config_obj.blocks_until_long_break = preset.blocks_until_long_break
        self.config_obj.save()

        for key, value in (
            ("focus_minutes", preset.focus_minutes),
            ("short_break_minutes", preset.short_break_minutes),
            ("long_break_minutes", preset.long_break_minutes),
            ("blocks_until_long_break", preset.blocks_until_long_break),
        ):
            if key in self.spinners:
                self.spinners[key].delete(0, "end")
                self.spinners[key].insert(0, str(value))

        name = preset.name_tokusatsu if self._is_tokusatsu() else preset.name_professional
        self._show_banner(
            f"Applied: {name} — {preset.focus_minutes}m focus. Applies from the next phase.",
            "low",
        )
```

- [ ] **Step 4: Manual check (no automated GUI test — see Task 5)**

Run: `python -c "import lock_in.ui as ui; print('import ok')"`
Expected: prints `import ok`, no `SyntaxError`/`ImportError`.

Then: `pytest -q`
Expected: PASS — full suite (this task only adds new methods; nothing existing was changed).

- [ ] **Step 5: Commit**

```bash
git add lock_in/ui.py
git commit -m "feat: add Kuuga and Super-1 preset buttons to Settings"
```

---

### Task 4: Gavv's micro-sprint toggle in Settings

**Files:**
- Modify: `lock_in/ui.py`

**Interfaces:**
- Consumes: `lock_in.presets.GAVV_MICRO_SPRINT` (Task 1), `Config.micro_sprint_mode` (Task 2).
- Produces: `self._build_gavv_toggle_row(parent) -> None`, `self._on_micro_sprint_toggled() -> None`.

- [ ] **Step 1: Add the methods**

Add these new methods on `LockInApp`, near `_build_timer_preset_row` from Task 3:

```python
    def _build_gavv_toggle_row(self, parent) -> None:
        """
        A single switch, not a row of buttons -- Gavv's gimmick stays on
        until you turn it off, it isn't a one-click-and-done preset.
        """
        heading = "Bite-Sized Mode" if self._is_tokusatsu() else "Micro-Sprint Mode"
        ctk.CTkLabel(parent, text=heading, text_color=COLOR_TIMER_ACCENT,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(14, 4))

        self.micro_sprint_switch = ctk.CTkSwitch(
            parent, text=f"{GAVV_MICRO_SPRINT.focus_minutes}m focus / "
                         f"{GAVV_MICRO_SPRINT.short_break_minutes}m break, repeating",
            progress_color=COLOR_TIMER_ACCENT,
            command=self._on_micro_sprint_toggled,
        )
        if self.config_obj.micro_sprint_mode:
            self.micro_sprint_switch.select()
        else:
            self.micro_sprint_switch.deselect()
        self.micro_sprint_switch.pack(anchor="w", pady=4)

        ctk.CTkLabel(
            parent,
            text="Overrides your timer lengths above until you turn this back off.",
            font=ctk.CTkFont(size=10), text_color=COLOR_IDLE,
        ).pack(anchor="w")

    def _on_micro_sprint_toggled(self) -> None:
        """Called when you click the Micro-Sprint switch itself."""
        self.config_obj.micro_sprint_mode = self.micro_sprint_switch.get() == 1
        self.config_obj.save()
        name = GAVV_MICRO_SPRINT.name_tokusatsu if self._is_tokusatsu() else GAVV_MICRO_SPRINT.name_professional
        state = "on" if self.config_obj.micro_sprint_mode else "off"
        self._show_banner(f"{name}: {state}. Applies from the next phase.", "low")
```

- [ ] **Step 2: Manual check**

Run: `python -c "import lock_in.ui as ui; print('import ok')"`
Expected: prints `import ok`.

Then: `pytest -q`
Expected: PASS — full suite.

- [ ] **Step 3: Commit**

```bash
git add lock_in/ui.py
git commit -m "feat: add Gavv's micro-sprint toggle to Settings"
```

---

### Task 5: Manual screenshot verification

**Files:**
- Create (scratch, not committed): a throwaway verification script, same pattern as Tier 1's `verify_tier1.py`.

- [ ] **Step 1: Write and run a verification script**

Create a script in your scratch/temp directory (NOT inside the repo) that launches `ui.LockInApp()`, and for each of `"Kamen Rider Kuuga (2000)"`, `"Kamen Rider Super-1 (1980)"`, `"Kamen Rider Gavv (2024)"`, and one control Rider (e.g. `"Kamen Rider V3 (1973)"`):

1. Sets `app.config_obj.rider_theme` and calls `app._on_rider_theme_change(rider)`.
2. Switches to the Settings tab (`app.tabs.set("Settings")`).
3. Screenshots the window (same `ImageGrab.grab` + `-topmost`/`lift()`/`focus_force()` pattern used for every prior round's verification).

Confirm: Kuuga shows exactly 4 buttons (Mighty/Dragon/Pegasus/Titan or their professional names depending on the wording switch), Super-1 shows exactly 5 with captions underneath, Gavv shows one switch plus the override note, and the control Rider shows none of the three rows.

- [ ] **Step 2: Click-test the preset buttons and the toggle**

Still in the same script: call `app._apply_timer_preset(KUUGA_PRESETS[1])` (Dragon) directly, then check `app.config_obj.focus_minutes == 10` and that `app.spinners["focus_minutes"].get() == "10"`. Call `app._on_micro_sprint_toggled()` after manually flipping `app.micro_sprint_switch` (select/deselect), and check `app.config_obj.micro_sprint_mode` matches.

- [ ] **Step 3: Fix anything that looks wrong, then delete the scratch script and screenshots**

They're verification-only, not part of the app — don't commit them.

---

### Task 6: Docs and version

**Files:**
- Modify: `README.md`
- Modify: `.gitignore` (only if Task 5 needs a new generated-file pattern — check first, don't add speculatively)
- Modify: `lock_in/__init__.py`

- [ ] **Step 1: Update the README's Kamen Rider theme section**

In `README.md`, under the Tier 1 gimmick list added previously (search for "Tier 1: 9 Riders with their own gimmick"), add a new subsection right after it:

```markdown
### Tier 2: 3 Riders with quick-access settings presets

Three more Riders add controls to the Settings tab itself, above the
Timer lengths section:

- **Kuuga** — 4 buttons (Mighty/Dragon/Pegasus/Titan) that each set
  focus/break lengths in one click, from a quick 10-minute sprint to a
  90-minute endurance block.
- **Super-1** — 5 task-type buttons (Super Hand/Power Hand/Elek Hand/
  Cold-Thermal Hand/Radar Hand), each tuned for a different kind of
  work (development, hardware, admin, logic/AI, research).
- **Gavv** — a toggle that overrides your timer lengths toward repeated
  10-minute "snackable" sprints with longer, more frequent breaks, for
  days when a normal-length focus block isn't realistic. Stays on until
  you turn it back off; your real settings are never overwritten.

See `docs/superpowers/specs/2026-08-10-tier2-settings-presets-design.md`
for the full design.
```

- [ ] **Step 2: Check `.gitignore`**

This feature doesn't introduce any new generated file type in the repo — confirm no edit is actually needed rather than adding one speculatively.

- [ ] **Step 3: Bump the version**

In `lock_in/__init__.py`, change `__version__ = "2.0.2"` to `__version__ = "2.1.0"` — a minor bump, since this adds a real new feature (not just a bug fix), matching this session's versioning convention (Tier 1 was `2.0.0`, the same kind of jump).

- [ ] **Step 4: Run the full test suite one final time, in both environments**

Run: `venv\Scripts\python.exe -m pytest -q` and `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS in both — full suite, no failures.

- [ ] **Step 5: Commit**

```bash
git add README.md lock_in/__init__.py
git commit -m "docs: document Tier 2 settings presets, bump to v2.1.0"
```

---

## Self-Review Notes

- **Spec coverage:** Kuuga's 4 presets and Super-1's 5 presets (Task 1, with exact values pinned in tests), Gavv's toggle and its non-destructive read-side override (Task 2, with an explicit test proving turning it off restores normal values without any restore logic), the shared apply mechanism (Task 3), wording-aware labels everywhere (`self._is_tokusatsu()` used in every new label), and per-Rider visibility (Task 3's conditional block) are all covered.
- **Architecture correction from the spec:** the spec described reusing Tier 1's `_sync_progress_widget_visibility()` pack-toggle pattern. While writing this plan, reading `_rebuild_tabs()`/`_on_rider_theme_change()` showed the Settings tab is fully destroyed and rebuilt on every Rider change already — so Tier 2 needed no persistent widgets or visibility syncing at all, just a conditional at build time. This is simpler than the spec assumed and doesn't change any user-facing behavior described in it.
- **Placeholder scan:** no TBD/TODO; every step has real, runnable code.
- **Type consistency:** `TimerPreset`'s fields (Task 1) are used identically in `Config` (Task 2, via `GAVV_MICRO_SPRINT.focus_minutes` etc.) and in `ui.py` (Tasks 3–4, via `preset.focus_minutes` etc.) — no naming drift.
