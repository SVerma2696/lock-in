# Lock In: Tier 2 — Settings presets & quick toggles

Date: 2026-08-10
Status: Approved by user, ready for implementation plan

## Goal

Tier 2 of the larger "38 per-Rider workflow gimmicks" project (Tier 1
shipped in v2.0.0 — see that tier's spec for the earlier 9 Riders).
Give 3 Riders (Kuuga, Super-1, Gavv) quick-access controls in Settings
that adjust the Pomodoro timer's interval lengths — extending `Config`
with one new toggle field and a small table of preset values. Purely a
settings/UX feature: no blocking-logic changes, no new persisted data
model beyond the one new `Config` field.

The 3 Riders in Tier 2, and nothing else: **Kuuga, Super-1, Gavv.**

## 1. Shared preset mechanism (Kuuga + Super-1)

Both write the same bundle of 4 fields into `Config` — `focus_minutes`,
`short_break_minutes`, `long_break_minutes`, `blocks_until_long_break` —
the exact fields the Settings tab's existing number entries already
control. One shared backend function applies a preset (sets the 4
fields, saves, updates the visible spinner entries, shows a
confirmation banner); Kuuga and Super-1 are just two different arrays
of labeled presets calling that same function. No duplicated logic.

This is safe to do mid-block: `session.py`'s `_advance()` captures a
phase's end time once, at the moment that phase starts
(`_phase_ends_at = self._clock() + duration`). Changing `Config`'s
timer fields never retroactively changes an already-running phase — it
applies "from the next phase," identical to today's existing
settings-save behavior (the save banner already says exactly that).

Applying a preset does **not** revert when you later switch to a
different Rider theme. Presets write real settings, same as if you'd
typed the numbers in yourself — they aren't "active only while that
Rider is selected."

## 2. Kuuga's 4 interval presets

| Tokusatsu label | Professional label | Focus | Short break | Long break | Blocks |
|---|---|---|---|---|---|
| Mighty | Standard (25m) | 25 | 5 | 15 | 4 |
| Dragon | Quick Sprint (10m) | 10 | 3 | 10 | 5 |
| Pegasus | Deep Work (50m) | 50 | 10 | 20 | 3 |
| Titan | Endurance (90m) | 90 | 15 | 30 | 2 |

Mighty matches today's existing defaults exactly, as the "standard"
baseline every other preset is a variation on.

## 3. Super-1's 5 Hand presets

| Tokusatsu label | Professional label | Task type | Focus | Short break | Long break | Blocks |
|---|---|---|---|---|---|---|
| Super Hand | Development (25m) | General software development | 25 | 5 | 15 | 4 |
| Power Hand | Hardware/Embedded (50m) | Hardware & embedded engineering | 50 | 10 | 20 | 3 |
| Elek Hand | Admin (15m) | Admin & correspondence | 15 | 5 | 15 | 4 |
| Cold/Thermal Hand | Logic/AI (45m) | Logic & AI implementation | 45 | 10 | 20 | 3 |
| Radar Hand | Research (30m) | Network analysis & research | 30 | 5 | 15 | 4 |

The "task type" column is shown as a short subtitle under each button
in the UI, so the buttons are self-explanatory without needing to
already know what an "Elek Hand" is.

## 4. Gavv's micro-sprint toggle

A switch (same pattern as Hard mode), not a one-shot button:
**Bite-Sized Mode** (tokusatsu) / **Micro-Sprint Mode** (professional).

While on, `Config.phase_seconds()` returns fixed values instead of your
saved ones — it's a priority check at the read side, not a write to
your real settings:

| | Focus | Short break | Long break | Blocks |
|---|---|---|---|---|
| Gavv override | 10 | 8 | 15 | 2 |

Note the short-break:focus ratio (8:10) is deliberately much richer
than every other preset (which sit around 1:5) — matching "longer,
frequent breaks" for days when even a 10-minute block needs real
recovery time in between.

Flipping it off is instant and lossless — nothing was ever overwritten,
so there's no restore/undo logic needed at all. While it's on, the
Settings tab's timer-length number fields keep showing your real
saved values (unchanged, not grayed out — kept simple for this pass);
a small note under the switch says it's overriding them until turned
off, so the mismatch isn't a mystery.

## Architecture

**New file `lock_in/presets.py`** — pure data, same role
`rider_themes.py` plays for colors. A frozen `TimerPreset` dataclass
(`name_tokusatsu`, `name_professional`, `focus_minutes`,
`short_break_minutes`, `long_break_minutes`, `blocks_until_long_break`,
`description`), plus three constants: `KUUGA_PRESETS` (4 entries),
`SUPER1_PRESETS` (5 entries), and `GAVV_MICRO_SPRINT` (one instance,
not a list). Zero dependencies, so both `config.py` and `ui.py` can
import from it without any risk of a circular import.

**`config.py`**: one new field, `micro_sprint_mode: bool = False`.
`phase_seconds()` gets a priority check at the top: if
`self.micro_sprint_mode` is true, look up the answer in
`GAVV_MICRO_SPRINT` instead of `self.focus_minutes`/etc.

**`ui.py`**: three frames built once in the Settings tab, right below
the Rider-theme dropdown, none packed initially —
`self.kuuga_preset_frame`, `self.super1_preset_frame`,
`self.gavv_toggle_frame`. A new `_sync_tier2_gimmick_visibility()`
method checks `self.config_obj.rider_theme` by **exact match** against
the 3 relevant theme names, and packs whichever one frame matches (if
any), hiding the others — same `pack_forget()`/`pack(before=...)`
pattern already used for Tier 1's `_sync_progress_widget_visibility()`,
called from the same two hook points (once at startup, again from
`_on_rider_theme_change()`).

A shared `_apply_timer_preset(preset: TimerPreset)` method: sets the 4
`Config` fields from the preset, updates the matching entries in
`self.spinners`, saves, and shows a confirmation banner (e.g. "Applied:
Dragon — 10m sprints. Applies from the next phase."). Every Kuuga/
Super-1 button is bound to this same method with a different preset.

A `_on_micro_sprint_toggled()` method flips `config_obj.micro_sprint_mode`,
saves, and refreshes the banner/note text.

Every button/switch label reads `self._is_tokusatsu()` (already exists)
to pick the tokusatsu or professional name — same mechanism every other
wording-aware label in this app already uses.

## Testing

- **`tests/test_presets.py`** (new): `KUUGA_PRESETS` has exactly 4
  entries matching the table above; `SUPER1_PRESETS` has exactly 5;
  `GAVV_MICRO_SPRINT`'s values match its table. Pure data, no display
  server.
- **`tests/test_config.py`** (new — `Config` has no dedicated test file
  yet): `phase_seconds()` returns the normal calculated values when
  `micro_sprint_mode` is `False`, and `GAVV_MICRO_SPRINT`'s values when
  `True`, for all three phases.
- **`ui.py` wiring** (the 3 frames, visibility sync, button clicks): verified
  the same way Tier 1's was — screenshot-driven manual verification of
  the real running app, not an automated GUI test, consistent with how
  this codebase already treats anything downstream of actual widget
  rendering.

## Out of scope for this pass

- The other 4 tiers of the 38-Rider project — separate specs, separate
  brainstorming passes.
- Persisting *which* preset produced the current timer lengths (e.g. no
  "Currently: Dragon" indicator saved anywhere). `Config` only stores
  the resulting raw minute values, same as if you'd typed them in by
  hand — not which button produced them.
- Graying out/disabling the timer-length spinners while Gavv's toggle
  is active — a text note instead, to keep this pass simple.
- Any git/GitHub action taken by the assistant — the user runs every
  command themselves.

## File-by-file change list

- New: `lock_in/presets.py`.
- New: `tests/test_presets.py`, `tests/test_config.py`.
- Edit: `lock_in/config.py` (`micro_sprint_mode` field, `phase_seconds()`
  override check).
- Edit: `lock_in/ui.py` (3 new frames, `_apply_timer_preset()`,
  `_on_micro_sprint_toggled()`, `_sync_tier2_gimmick_visibility()`,
  wiring into `__init__` and `_on_rider_theme_change()`).
- Edit: `README.md`, `.gitignore` as needed once implementation lands.
