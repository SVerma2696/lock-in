# Lock In: Tier 3 — Enforcement/interaction tweaks

Date: 2026-08-11
Status: Approved by user, ready for implementation plan

## Goal

Tier 3 of the larger 38-Rider project (Tier 1 shipped in v2.0.0, Tier 2
in v2.1.0). Give 5 Riders (X, Amazon, ZX, Gaim, 555) their own
enforcement or interaction behavior — not just a color or a progress
shape. Unlike Tier 1/2, these touch real behavior: what happens before
a focus block starts, what the grace period is, whether sound/toasts
fire, and how the existing Lockdown screen can be exited early.

The 5 Riders in Tier 3, and nothing else: **X, Amazon, ZX, Gaim, 555.**

## Shared architecture

New `RiderTheme.tier3_effect: str = "none"` field in `rider_themes.py`,
mirroring `tier1_effect` exactly — same pattern, new tier, defaulting to
`"none"` for all 33 Riders outside it. The 5 Riders get one of:
`"goal_gate"` (X), `"zero_ui"` (Amazon), `"stealth_mute"` (ZX),
`"lock_overlay"` (Gaim), `"code_unlock"` (555).

## 1. X — goal-entry gate

Clicking Henshin/Start while idle, with X as the active theme, doesn't
start the session immediately. Instead a full-screen overlay appears
(same `CTkToplevel` pattern the existing Lockdown screen already uses —
see `_show_lockdown()` in `ui.py`) asking what you're working on, with
a text entry and a "Begin" button. Submitting empty text does nothing
(a small hint appears, no countdown/timeout — putting time pressure on
defining the work would defeat the point). Submitting real text closes
the overlay and starts the focus block exactly as `_on_toggle()` always
has. The submitted text becomes `self.current_goal_text`, and replaces
the driver label (which normally shows the Rider name) for the
duration of that focus block only — reverting to the Rider name on
break/idle.

This only gates a **fresh** start from idle — resuming from pause never
shows the gate again (`self.session.phase is Phase.IDLE` is the check).

## 2. Amazon — zero-UI + zero grace period

Two independent pieces:

- **`Config`-level:** a new `zero_grace_mode: bool` field and an
  `effective_grace_seconds()` method (`return 0 if self.zero_grace_mode
  else self.grace_seconds`), replacing the one direct
  `self.config.grace_seconds` read in `enforcer.py`'s `judge()`
  (currently line 286). Same non-destructive, read-side pattern Gavv's
  `micro_sprint_mode` already established for `phase_seconds()` — your
  real `grace_seconds` value is never touched.
- **UI-level:** during an Amazon focus block, the phase label, streak
  label, driver label, and tab bar all hide — just a solid `#33691e`
  field remains where the header content was, Pillow-rendered so it
  visibly drains (a shrinking fill, like a tank emptying) as
  `session.progress` advances. Pause/Skip/Reset shrink to small
  icon-only buttons rather than disappearing — "zero UI" as a look, not
  a trap you can't get out of. Reverts to the normal header on
  break/idle.

## 3. ZX — stealth mode

Two independent pieces:

- **`Config`-level:** a new `stealth_mute_mode: bool` field and
  `effective_sound_enabled()`/`effective_toast_enabled()` methods,
  replacing the direct `self.config.sound_enabled`/`toast_enabled`
  reads in `notifier.py` (`notify()`, `phase_chime()`, `alert_sound()`).
  Same read-side pattern as above — your real Sounds/Desktop
  notifications switches in Settings are never touched or overwritten.
- **UI-level:** when a ZX focus block starts, the window auto-minimizes
  using `minimize_window()` (already exists, used today for blocking).
  Separately, and NOT gated to focus-only: whenever ZX is the selected
  theme at all, the whole UI renders in monochrome. Mechanism: a new
  `desaturate(hex_color) -> str` pure function in `rider_themes.py`
  (same luminosity-weighted formula `readable_text_color()` already
  uses: `R*299 + G*587 + B*114`, so contrast between primary/secondary
  survives conversion to grayscale). In `_apply_rider_theme()`, when
  `theme.tier3_effect == "stealth_mute"`, replace `theme` with
  `dataclasses.replace(theme, primary=(desaturate(...), desaturate(...)),
  secondary=(desaturate(...), desaturate(...)))` **before** anything
  reads `theme.primary_pair`/`surface_pair`/`primary_text_pair`/etc. —
  every one of those already derives from `self.primary`/`self.secondary`,
  so the swap cascades to every native widget color and every
  Pillow-rendered piece of art (glow, background, divider) with zero
  changes needed anywhere else. Not phase-reactive on purpose: ZX also
  auto-minimizes at focus start, so re-deriving every color every tick
  for a window you're not even looking at buys nothing.

## 4. Gaim — lock overlay

UI-only, no real window-switch blocking — matches the project's
existing documented stance (README's "On 'stop me from leaving'"
section: no elevated APIs, every escalation always has a visible exit).
During a Gaim focus block: the window sets `self.attributes("-topmost",
True)` (same attribute the Lockdown overlay already uses), a padlock
icon (new small Pillow-rendered glyph in `visuals.py`) appears
composited into the header, and the background art dims — reusing the
exact compositing mechanism Kiva's `night_overlay` already built in
Tier 1 (`apply_tier1_background_effect`-style: one more Pillow layer
blended into the background image before it reaches a widget, never a
second overlapping widget). Skip/Reset stay clickable the whole time —
a heavier deterrent, not a trap. Reverts (topmost off, overlay gone) on
break/idle, same `in_focus` gating Stronger/Kiva already use.

## 5. 555 — code-entry early unlock

The existing Lockdown screen (`_show_lockdown()`) already has a
countdown and an "Abort Mission"/"End Session" button that ends the
*whole session*. 555 adds a second, different way out: when
`current_tier3_effect == "code_unlock"`, a small `CTkEntry` appears on
the lockdown overlay. Typing `555` and pressing Enter calls
`self._close_lockdown()` directly (**not**
`_end_session_from_lockdown()`) — the lockdown screen goes away and you
return to your focus block early, exactly like the countdown finishing
naturally, just sooner. Any other input clears the field and shows a
brief "Incorrect code" hint — no penalty, no strike added, no lockout.

## Architecture summary (files)

- **`lock_in/rider_themes.py`**: `tier3_effect` field, `desaturate()`
  helper, the 5 Riders' assignments.
- **`lock_in/config.py`**: `zero_grace_mode`, `stealth_mute_mode`
  fields; `effective_grace_seconds()`, `effective_sound_enabled()`,
  `effective_toast_enabled()` methods.
- **`lock_in/enforcer.py`**: one call-site change (`grace_seconds` →
  `effective_grace_seconds()`).
- **`lock_in/notifier.py`**: every `sound_enabled`/`toast_enabled` read
  site swapped for the `effective_*` method.
- **`lock_in/visuals.py`**: Amazon's draining-fill renderer, Gaim's
  padlock glyph + dim-overlay compositing function.
- **`lock_in/ui.py`**: `_show_goal_gate()` (X), zero-UI header
  hide/show + drain rendering (Amazon), monochrome theme swap in
  `_apply_rider_theme()` (ZX) + auto-minimize at focus start, topmost +
  padlock/dim wiring gated by `in_focus` (Gaim), the code-entry widget
  added to `_show_lockdown()` (555).

## Testing

- Pure-function tests: `desaturate()` (grayscale, luminosity-correct,
  contrast preserved between two different inputs), Amazon's drain
  renderer (`visuals.py`, same alpha-sum-increases-with-progress
  pattern every Tier 1 shape test already uses), Gaim's padlock/dim
  compositing function.
- `Config.effective_grace_seconds()` / `effective_sound_enabled()` /
  `effective_toast_enabled()`: on by default (normal value), overridden
  correctly when the relevant mode flag is set, restores instantly when
  unset — same shape as the existing `micro_sprint_mode` tests in
  `tests/test_config.py`.
- `ui.py` wiring (goal-gate overlay, zero-UI header swap, monochrome
  cascade, lock overlay, lockdown code entry): screenshot-driven manual
  verification of the real running app, consistent with every prior
  tier's GUI-wiring testing approach — no automated GUI test.

## Out of scope for this pass

- The other 3 tiers (Tier 0's vanilla baseline mode, Tier 4's display
  modes, Tiers 5-6's new subsystems) — separate specs.
- Real system tray integration for ZX — scoped down to reusing the
  existing window-minimize, explicitly agreed during design.
- Any genuine window-switch/Alt-Tab blocking for Gaim — explicitly
  ruled out, matches the project's existing documented stance.
- Persisting `current_goal_text` across app restarts — in-memory only,
  same rule already applied to Fourze's constellation state in Tier 1.
- Any git/GitHub action taken by the assistant — the user runs every
  command themselves.

## File-by-file change list

- Edit: `lock_in/rider_themes.py`, `lock_in/config.py`,
  `lock_in/enforcer.py`, `lock_in/notifier.py`, `lock_in/visuals.py`,
  `lock_in/ui.py`.
- Edit: `tests/test_rider_themes.py`, `tests/test_config.py`,
  `tests/test_visuals.py`, `tests/test_enforcer.py`,
  `tests/test_notifier.py`.
- Edit: `README.md`, `.gitignore` as needed once implementation lands.
