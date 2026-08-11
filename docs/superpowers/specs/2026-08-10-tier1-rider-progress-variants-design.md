# Lock In: Tier 1 — per-Rider progress bar variants

Date: 2026-08-10
Status: Approved by user, ready for implementation plan

## Goal

Tier 1 of the larger "38 per-Rider workflow gimmicks" project (see the
decomposition discussion — 6 tiers total, this spec covers only Tier 1).
Give 9 specific Kamen Riders their own unique **visual** treatment during
a focus block — either a custom-shaped progress indicator, a color
behavior tweak, or a chrome-level effect around the timer — instead of
the current shared progress bar shape used by all 38 themes. Purely
visual: nothing in this spec changes timer lengths, blocking behavior,
or any existing Config/Settings value. Behavior-changing per-Rider
gimmicks (if pursued) are later tiers, out of scope here.

The 9 Riders in Tier 1, and nothing else: **Kamen Rider (1971), Skyrider,
Stronger, Black, Fourze, Build, Drive, Agito, Kiva.** Every other Rider
keeps today's plain progress bar, unchanged.

## 1. The 4 custom-shaped progress renderers

Each of these fully replaces the plain progress bar with its own Pillow
drawing for that Rider only. All are pure functions in `visuals.py`,
following the file's existing pattern: `(size, progress_fraction,
primary_color, secondary_color, appearance_mode) -> PIL.Image`. Only
these 4 Riders get a second, picture-based widget at all — every other
Rider (including Agito, Black, Stronger, Drive, Kiva) keeps the native
progress bar widget untouched.

- **Kamen Rider (1971) — "Windmill Dynamo".** A 4-bladed turbine/windmill.
  Progress fills the blades proportionally (like a pie chart with 4
  wedges), evoking the original Rider's wind-power origin.
- **Skyrider — "Sailing Jump".** A vertical rising bar, like a glider's
  altimeter climbing, instead of the usual horizontal fill — Skyrider's
  whole motif is gliding.
- **Fourze — "Cosmic State".** A small star-field. As progress advances,
  stars light up one at a time and draw connecting lines between them,
  like a constellation slowly completing — matching Fourze's space
  switches. Which stars are "lit" is worked out fresh from
  progress_fraction every time, not saved anywhere — so it naturally
  starts over blank on every new focus block, with no save file needed.
- **Build — "Best Match".** Two vial shapes (primary color, secondary
  color) that fill with liquid as progress advances, and visually
  "combine" into one mixed color once progress nears 100% — matching
  Build's Best Match bottle-combining gimmick.

## 2. Agito — color interpolation (not a new shape)

Agito keeps the normal bar shape, but its fill color **interpolates**
across the session instead of staying static: it starts as a muted,
desaturated version of Agito's gold and gradually intensifies to the
full vivid `#ffca28` as the block nears completion — "awakening," matching
Agito's core premise of dormant power waking up. Implemented as a plain
color lerp driven by the same progress fraction the bar already tracks;
no new asset, no new shape.

## 3. Drive — accelerating fill (revised during implementation, not a new shape)

> **Revision note:** this originally specced a 5th custom shape
> ("Top Gear" speed-line streaks). During implementation the user
> clarified the intended gimmick was actually an accelerating fill
> animation, not a new shape — this section reflects the corrected,
> final design.

Drive keeps the normal progress bar shape and color. Instead, the
NUMBER fed into it is bent through an easing curve
(`progress_fraction ** 2`): the bar appears to lag behind real progress
early on, then visibly speeds up and catches back up right at the end —
like shifting into top gear. It still reaches exactly empty and exactly
full at the true start/end. Same pattern as Agito (Task 2 above), just
bending the fraction instead of the color.

## 4. Black — stricter dark-mode contrast (revised during implementation)

> **Revision note:** this originally specced a "faceted, segmented"
> progress bar shape. During implementation the user clarified the
> intended gimmick was actually a dark-mode contrast boost, not a shape
> change — this section reflects the corrected, final design.

Black keeps the normal progress bar entirely unchanged. Instead, its
dark-mode TEXT (the phase label, timer digits, driver label — anywhere
`primary_text_pair`/`secondary_text_pair` are used) gets pushed further
toward white than every other Rider: 0.55 instead of the normal 0.35.
Light mode is unaffected. Lives entirely in `rider_themes.py`; no
picture, no `ui.py` wiring needed at all.

## 5. Stronger — border glow (chrome-level, outside the bar)

Not a progress-bar change at all. A soft red glow along the **outer
window edge**, separate from the existing per-theme glow-behind-the-timer
effect, that widens and brightens as the focus timer counts up — reading
as Stronger "charging up" his own electricity over the course of a
block — then resets at the next phase change. Painted directly onto the
existing background image inside `visuals.py` (see Architecture below) —
never a second widget layered on top of the window.

## 6. Kiva — translucent night overlay (chrome-level, outside the bar)

Also not a progress-bar change. A **translucent amber overlay** tinting
the whole app window during focus blocks, evoking Kiva's night/vampire
motif. This is a real semi-transparent color wash over the UI, not just
Kiva's existing (already-shipped) palette — confirmed during design.
Same rule as Stronger: blended into the background image with Pillow
before it ever reaches a widget, not stacked as a see-through widget on
top of the real one.

## Architecture

**One new field on `RiderTheme`** (`rider_themes.py`): `tier1_effect:
str = "none"`, defaulting to `"none"` for all 29 Riders outside this
tier. The 9 Tier 1 Riders get one of: `"windmill"`, `"rising_bar"`,
`"constellation"`, `"vials"` (the 4 custom shapes), `"color_interpolation"`
(Agito), `"accelerating_fill"` (Drive), `"high_contrast_dark"` (Black),
`"border_glow"` (Stronger), `"night_overlay"` (Kiva). This mirrors how
`primary`/`secondary` already work — one small piece of per-instance
data, no parallel lookup table to keep in sync.

**`visuals.py`** gains one pure-function renderer per shape above
(`render_windmill_progress`, etc.), a `render_progress(effect, ...)`
dispatcher covering just those 4 shapes (`visuals.SHAPE_EFFECTS` lists
exactly which effects need it), plus small standalone functions for the
other 5 effects (`interpolate_agito_color`, `ease_drive_progress`, the
`primary_text_pair`/`secondary_text_pair` contrast tweak for Black in
`rider_themes.py`, and the two background-compositing functions for
Stronger/Kiva below). Only the 4-shape Riders need a second widget in
`ui.py` at all — every other Rider, including the other 5 Tier 1
Riders, keeps the plain native progress bar completely untouched.

**All alpha compositing happens inside `visuals.py`, in Pillow, never as
overlapping Tkinter widgets.** Tkinter/CustomTkinter has no real z-index
alpha blending between separate widgets — a semi-transparent widget drawn
on top of another one renders its alpha against the root window's solid
background and simply blocks whatever is underneath, rather than tinting
it. So `border_glow` and `night_overlay` are never a second widget placed
over the real one. Instead, the existing background-art renderer in
`visuals.py` gains an optional `tier1_effect` argument: for Stronger it
paints the glow onto the edges of that same background image with
`Image.alpha_composite()`; for Kiva it blends the amber wash across the
whole background image the same way. Either way, the function still
returns one flat `PIL.Image` — the tinting is baked into the pixels
before anything is wrapped in a `CTkImage`.

**`ui.py`**: `_refresh_timer_widgets()` (already touched by the recent
contrast fix) calls `visuals.render_progress(...)` instead of configuring
`self.progress` directly with a flat color, and wraps the result in a
`CTkImage` the same way the existing glow art already is. Each 200ms
`_pump()` tick, `ui.py` pushes exactly one new `CTkImage` into the one
background-art widget and one new `CTkImage` into the one progress
widget — never more than that, and never two images stacked on the same
spot. This keeps the UI thread's per-tick work to two cheap image swaps,
with all the actual compositing math already done in `visuals.py`.

**State**: only Fourze's lit-star progress needs any state beyond the
existing progress fraction, and it's a plain in-memory attribute on
`LockInApp`, reset on every app restart — same rule already agreed for
Tier 1's streak/constellation state generally. Nothing here touches
`config.json` or `model.json`.

## Testing

- One test per new `visuals.py` renderer in `test_visuals.py`, following
  the file's existing pattern (pure function, no display server): correct
  image size, correct light/dark contrast, and — where relevant — that
  the rendered content actually changes as `progress_fraction` increases
  (e.g. more windmill blades filled, more stars lit, more speed-lines
  drawn).
- `render_progress()` dispatch: one test confirming each of the 4
  shape effects routes to its own renderer, and a `SHAPE_EFFECTS`
  regression test confirming that set matches the dispatch table
  exactly — `ui.py` relies on it to decide which Riders get the
  picture widget at all.
- The chrome-level effects (border glow, night overlay) get the same
  pure-function tests as the 5 shapes — since they're just Pillow
  compositing in `visuals.py`, they don't need a display server either.
  Only the final `ui.py` wiring (pushing the right `CTkImage` into the
  right widget each tick) is verified the same way the recent contrast
  fix was: screenshot-driven manual verification of the real running
  app, not an automated GUI test — consistent with how this codebase
  already treats anything downstream of actual widget rendering.

## Out of scope for this pass

- The other 8 tiers of the 38-Rider project (behavior-changing gimmicks,
  new data models, networking, hotkeys, etc.) — separate specs, separate
  brainstorming passes.
- Any git/GitHub action taken by the assistant — the user runs every
  command themselves.
- Persisting Fourze's constellation state (or any Tier 1 state) across
  restarts — explicitly agreed to be in-memory only, this pass.

## File-by-file change list

- Edit: `lock_in/rider_themes.py` (`tier1_effect` field + the 9 values,
  Black's stricter dark-mode text contrast).
- Edit: `lock_in/visuals.py` (4 shape renderers, Agito's color
  interpolation, Drive's easing curve, Stronger/Kiva chrome effects,
  `render_progress()` dispatcher + `SHAPE_EFFECTS` constant).
- Edit: `lock_in/ui.py` (a second picture-based widget shown only for
  the 4 shape Riders, toggled with `pack(before=self.controls)`;
  `_refresh_timer_widgets()` branches to it or the native bar; per-tick
  background-effect refresh for Stronger/Kiva).
- Edit: `tests/test_rider_themes.py`, `tests/test_visuals.py` (new
  renderer/effect tests + dispatch tests).
- Edit: `README.md` (done), `.gitignore` (checked, no change needed).
