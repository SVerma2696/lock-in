# Lock In: Tier 3 Enforcement/Interaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give 5 Riders (X, Amazon, ZX, Gaim, 555) their own enforcement/interaction behavior — a goal-entry gate, zero-UI + zero grace period, stealth monochrome + mute, a visual lock overlay, and a code-entry early-unlock — on top of the existing Tier 1/2 systems.

**Architecture:** A new `RiderTheme.tier3_effect` field (mirrors `tier1_effect`). Two `Config` fields (`zero_grace_mode`, `stealth_mute_mode`) with read-side `effective_*()` methods, replacing the raw attribute reads in `enforcer.py`/`notifier.py` — same non-destructive pattern `micro_sprint_mode` already established. ZX's monochrome reuses `dataclasses.replace()` to swap in desaturated colors before the existing color-derivation pipeline runs. Gaim's dim+padlock reuses the exact `_refresh_background_effect()`/`apply_tier1_background_effect` compositing Stronger/Kiva already built. X's goal-gate and 555's code-entry both reuse the `CTkToplevel` full-screen overlay pattern `_show_lockdown()` already established.

**Tech Stack:** Python 3.11+, Pillow, CustomTkinter, pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-11-tier3-enforcement-interaction-design.md` — this plan implements it in full; no other tier.
- No git commands as part of any task. The user runs every git step themselves.
- Comments stay "simple enough for a 5 year old to understand" — short, plain-English, explain *why* not *what*.
- TDD: every new pure function/method gets a failing test first.
- Gaim never blocks real window-switching (topmost + visual dimming only). X's goal screen has no timeout. 555's wrong-code entry has no penalty.
- Only these 5 Riders get a `tier3_effect` other than `"none"`. Every other Rider's behavior must be provably unchanged.

---

### Task 1: `tier3_effect` field + `desaturate()` helper

**Files:**
- Modify: `lock_in/rider_themes.py`
- Test: `tests/test_rider_themes.py`

**Interfaces:**
- Produces: `RiderTheme.tier3_effect: str` (default `"none"`), `desaturate(hex_color: str) -> str`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_rider_themes.py`:

```python
def test_desaturate_produces_equal_rgb_channels():
    from lock_in.rider_themes import desaturate
    gray = desaturate("#ff0000").lstrip("#")
    r, g, b = gray[0:2], gray[2:4], gray[4:6]
    assert r == g == b


def test_desaturate_preserves_relative_brightness():
    from lock_in.rider_themes import desaturate

    def brightness(hex_color):
        hex_color = hex_color.lstrip("#")
        return sum(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    bright = desaturate("#ffff00")   # yellow -- perceived as bright
    dark = desaturate("#000080")     # navy -- perceived as dark
    assert brightness(bright) > brightness(dark)


def test_desaturate_keeps_two_different_colors_visually_distinct():
    from lock_in.rider_themes import desaturate
    assert desaturate("#ff0000") != desaturate("#0000ff")


def test_tier3_effect_defaults_to_none_for_ordinary_riders():
    assert RIDER_THEMES["Kamen Rider V3 (1973)"].tier3_effect == "none"
    assert RIDER_THEMES["Kamen Rider Kuuga (2000)"].tier3_effect == "none"


def test_tier3_effect_is_assigned_to_exactly_the_5_named_riders():
    expected = {
        "Kamen Rider X (1974)": "goal_gate",
        "Kamen Rider Amazon (1974)": "zero_ui",
        "Kamen Rider ZX (1982)": "stealth_mute",
        "Kamen Rider Gaim (2013)": "lock_overlay",
        "Kamen Rider 555 (2003)": "code_unlock",
    }
    for name, effect in expected.items():
        assert RIDER_THEMES[name].tier3_effect == effect, name

    everyone_else = set(RIDER_THEMES) - set(expected)
    for name in everyone_else:
        assert RIDER_THEMES[name].tier3_effect == "none", name
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rider_themes.py -k "desaturate or tier3_effect" -v`
Expected: FAIL — `ImportError`/`AttributeError`.

- [ ] **Step 3: Implement**

In `lock_in/rider_themes.py`, add near `readable_text_color`:

```python
def desaturate(hex_color: str) -> str:
    """
    Turn a color into its plain grey equivalent -- same perceived
    brightness as the original, but with all the color washed out.

    Uses the same "how bright does this look to a person" weights as
    readable_text_color() (green looks brighter than blue at the same
    number), so two different colors still end up as two different
    greys instead of collapsing to the exact same grey.
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    gray = round((r * 299 + g * 587 + b * 114) / 1000)
    return f"#{gray:02x}{gray:02x}{gray:02x}"
```

Add the field to `RiderTheme`, right after `tier1_effect`:

```python
    # "none" for every Rider except the 5 with a Tier 3 gimmick (see
    # docs/superpowers/specs/2026-08-11-tier3-enforcement-interaction-design.md).
    # ui.py reads this to decide what enforcement/interaction behavior
    # this Rider needs.
    tier3_effect: str = "none"
```

Edit exactly these 5 lines in `RIDER_THEMES` to add the keyword argument:

```python
    "Kamen Rider X (1974)": RiderTheme("Showa", 1974, ("#90a4ae", "#cfd8dc"), ("#0f4a8f", "#42a5f5"), tier3_effect="goal_gate"),
    "Kamen Rider Amazon (1974)": RiderTheme("Showa", 1974, ("#224714", "#558b2f"), ("#b33f00", "#ff9800"), tier3_effect="zero_ui"),
    "Kamen Rider ZX (1982)": RiderTheme("Showa", 1982, ("#9c1e1e", "#ef5350"), ("#78909c", "#b0bec5"), tier3_effect="stealth_mute"),
    "Kamen Rider 555 (2003)": RiderTheme("Heisei", 2003, ("#111111", "#424242"), ("#a60000", "#ff1744"), tier3_effect="code_unlock"),
    "Kamen Rider Gaim (2013)": RiderTheme("Heisei", 2013, ("#b33f00", "#ff9800"), ("#96761c", "#e4c657"), tier3_effect="lock_overlay"),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rider_themes.py -v`
Expected: PASS — full file.

- [ ] **Step 5: Commit**

```bash
git add lock_in/rider_themes.py tests/test_rider_themes.py
git commit -m "feat: add tier3_effect field and desaturate() helper"
```

---

### Task 2: `Config` read-side overrides

**Files:**
- Modify: `lock_in/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config.zero_grace_mode: bool`, `Config.stealth_mute_mode: bool`, `Config.effective_grace_seconds() -> int`, `Config.effective_sound_enabled() -> bool`, `Config.effective_toast_enabled() -> bool`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
def test_effective_grace_seconds_uses_normal_value_by_default():
    config = Config(grace_seconds=8)
    assert config.effective_grace_seconds() == 8


def test_effective_grace_seconds_is_zero_when_zero_grace_mode_is_on():
    config = Config(grace_seconds=8, zero_grace_mode=True)
    assert config.effective_grace_seconds() == 0


def test_zero_grace_mode_defaults_to_off():
    assert Config().zero_grace_mode is False


def test_effective_sound_and_toast_use_normal_values_by_default():
    config = Config(sound_enabled=True, toast_enabled=True)
    assert config.effective_sound_enabled() is True
    assert config.effective_toast_enabled() is True


def test_effective_sound_and_toast_are_off_when_stealth_mute_mode_is_on():
    config = Config(sound_enabled=True, toast_enabled=True, stealth_mute_mode=True)
    assert config.effective_sound_enabled() is False
    assert config.effective_toast_enabled() is False


def test_stealth_mute_mode_defaults_to_off():
    assert Config().stealth_mute_mode is False


def test_turning_stealth_mute_mode_off_restores_normal_values():
    """Same non-destructive rule as micro_sprint_mode -- your real Sounds
    and Desktop notifications switches were never touched."""
    config = Config(sound_enabled=True, stealth_mute_mode=True)
    assert config.effective_sound_enabled() is False
    config.stealth_mute_mode = False
    assert config.effective_sound_enabled() is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -k "effective_grace or effective_sound or effective_toast or zero_grace_mode or stealth_mute_mode" -v`
Expected: FAIL — `TypeError`/`AttributeError`.

- [ ] **Step 3: Implement**

In `lock_in/config.py`, add the two new fields right after `micro_sprint_mode`:

```python
    micro_sprint_mode: bool = False
    # Amazon's zero-UI gimmick: while this is on, effective_grace_seconds()
    # below hands back 0 instead of your real grace_seconds -- same
    # read-only trick as micro_sprint_mode, your real number is untouched.
    zero_grace_mode: bool = False
    # ZX's stealth gimmick: while this is on, effective_sound_enabled()
    # and effective_toast_enabled() below both hand back False, no
    # matter what your real Sounds/Desktop notifications switches say.
    stealth_mute_mode: bool = False
```

Add the three new methods, right after `phase_seconds()`:

```python
    def effective_grace_seconds(self) -> int:
        """Amazon's zero_grace_mode override -- see the field comment above."""
        return 0 if self.zero_grace_mode else self.grace_seconds

    def effective_sound_enabled(self) -> bool:
        """ZX's stealth_mute_mode override -- see the field comment above."""
        return False if self.stealth_mute_mode else self.sound_enabled

    def effective_toast_enabled(self) -> bool:
        """The same idea as effective_sound_enabled, for Desktop notifications."""
        return False if self.stealth_mute_mode else self.toast_enabled
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS — full file.

- [ ] **Step 5: Commit**

```bash
git add lock_in/config.py tests/test_config.py
git commit -m "feat: add Amazon/ZX read-side Config overrides"
```

---

### Task 3: Wire `enforcer.py` and `notifier.py` to the new methods

**Files:**
- Modify: `lock_in/enforcer.py:286`, `lock_in/notifier.py` (4 read sites: `notify()`, `phase_chime()`, `alert_sound()`)
- Test: `tests/test_enforcer.py`, `tests/test_notifier.py`

**Interfaces:**
- Consumes: `Config.effective_grace_seconds()`, `Config.effective_sound_enabled()`, `Config.effective_toast_enabled()` (Task 2).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_enforcer.py` (uses the existing `config`/`clock`/`enforcer`/`win` fixtures already in the file):

```python
def test_zero_grace_mode_skips_the_grace_period_entirely(clock, model):
    config = Config(
        grace_seconds=8, strike_interval_seconds=10, strike_decay_seconds=30,
        hard_mode=False, use_classifier=True, classifier_threshold=0.8,
        blocklist=["discord.exe"], allowlist=[], zero_grace_mode=True,
    )
    e = Enforcer(config, clock=clock)
    # With normal grace_seconds=8, the very first check would return
    # Action.NONE (still inside the grace period) -- zero_grace_mode
    # should skip straight to a real strike instead.
    action = e.update(win(process="discord.exe"), model)
    assert action is not Action.NONE
```

Add to `tests/test_notifier.py`:

```python
def test_stealth_mute_mode_silences_sound_and_toast_checks():
    config = Config(sound_enabled=True, toast_enabled=True, stealth_mute_mode=True)
    assert config.effective_sound_enabled() is False
    assert config.effective_toast_enabled() is False
    # Notifier itself shells out to real OS sound/toast calls, which
    # these tests deliberately never touch (see the file's own docstring)
    # -- this just confirms the Config methods Notifier's real code
    # calls actually report muted, matching the existing file's style
    # of testing pure logic only.
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_enforcer.py -k zero_grace_mode -v`
Expected: FAIL — with normal `grace_seconds=8` still being read, the first check returns `Action.NONE`, so `assert action is not Action.NONE` fails.

- [ ] **Step 3: Implement**

In `lock_in/enforcer.py`, change line 286:

```python
        if elapsed < self.config.grace_seconds:
```

to:

```python
        if elapsed < self.config.effective_grace_seconds():
```

In `lock_in/notifier.py`, change every read of `self.config.toast_enabled`/`self.config.sound_enabled` to the `effective_*` equivalent. In `notify()`:

```python
        if urgency != "low" and self.config.effective_toast_enabled():
            self._toast(title, body, urgency)

        if urgency == "high" and self.config.effective_sound_enabled():
            self.alert_sound()
```

In `phase_chime()`:

```python
        if not self.config.effective_sound_enabled():
            return
```

In `alert_sound()`:

```python
        if not self.config.effective_sound_enabled():
            return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_enforcer.py tests/test_notifier.py -v`
Expected: PASS — full files.

Then run the full suite to make sure nothing else that reads these fields broke:

Run: `pytest -q`
Expected: PASS — full suite (both new fields default to `False`, so existing behavior is unchanged when they're off).

- [ ] **Step 5: Commit**

```bash
git add lock_in/enforcer.py lock_in/notifier.py tests/test_enforcer.py tests/test_notifier.py
git commit -m "feat: wire grace/sound/toast reads through the new effective_* overrides"
```

---

### Task 4: ZX — monochrome desaturation cascade + auto-minimize

**Files:**
- Modify: `lock_in/ui.py`

**Interfaces:**
- Consumes: `desaturate()` (Task 1), `theme.tier3_effect` (Task 1).
- Produces: `self.current_tier3_effect: str` (read by every later task in this plan).

- [ ] **Step 1: Add the import**

At the top of `lock_in/ui.py`, add:

```python
import dataclasses
```

Change the `from .rider_themes import ...` line to also pull in `desaturate`:

```python
from .rider_themes import DEFAULT_RIDER_THEME, RIDER_THEMES, desaturate
```

- [ ] **Step 2: Desaturate the theme before anything reads its colors**

In `_apply_rider_theme()`, right after the theme lookup:

```python
        theme = RIDER_THEMES.get(
            self.config_obj.rider_theme, RIDER_THEMES[DEFAULT_RIDER_THEME]
        )
```

add:

```python
        # ZX's whole gimmick is going monochrome. Swapping in a
        # desaturated copy of the theme HERE, before anything below
        # reads theme.primary_pair/surface_pair/etc, means every one of
        # those (which all derive from primary/secondary) comes out
        # grey automatically -- no separate grayscale step needed
        # anywhere else, for widgets OR the Pillow-rendered art.
        if theme.tier3_effect == "stealth_mute":
            theme = dataclasses.replace(
                theme,
                primary=(desaturate(theme.primary[0]), desaturate(theme.primary[1])),
                secondary=(desaturate(theme.secondary[0]), desaturate(theme.secondary[1])),
            )
```

- [ ] **Step 3: Store `current_tier3_effect`**

Right after the existing line `self.current_tier1_effect = theme.tier1_effect` (inside `_apply_rider_theme()`), add:

```python
        # Which Tier 3 gimmick (if any) this Rider has -- read by the
        # goal-gate, zero-UI, lock-overlay, and code-unlock code later
        # in this file.
        self.current_tier3_effect = theme.tier3_effect
```

- [ ] **Step 4: Auto-minimize at the start of a ZX focus block**

In `_on_phase_started()`, right after `self.enforcer.reset()`:

```python
        if phase is Phase.FOCUS and self.current_tier3_effect == "stealth_mute":
            # Ninja Stealth: get out of the way the moment focus starts.
            # iconify() is Tkinter's own cross-platform minimize -- no
            # need for the OS-specific minimize_window() helper, since
            # that one is built for minimizing OTHER apps' windows, not
            # this app's own.
            self.iconify()
```

- [ ] **Step 5: Manual check**

Run: `python -c "import lock_in.ui as ui; print('import ok')"`
Expected: prints `import ok`.

Then: `pytest -q`
Expected: PASS — full suite (no existing test reads `theme.primary` directly through `_apply_rider_theme()`'s internals, so this is safe).

- [ ] **Step 6: Commit**

```bash
git add lock_in/ui.py
git commit -m "feat: add ZX monochrome desaturation and auto-minimize"
```

---

### Task 5: Gaim — padlock overlay + always-on-top

**Files:**
- Modify: `lock_in/visuals.py`, `lock_in/ui.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Consumes: `apply_tier1_background_effect` pattern (existing), `self.current_tier3_effect` (Task 4).
- Produces: `render_padlock_glyph(size: int) -> Image.Image`, `apply_gaim_lock_overlay(base_image: Image.Image, active: bool) -> Image.Image`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_visuals.py`:

```python
def test_render_padlock_glyph_returns_a_square_image():
    from lock_in.visuals import render_padlock_glyph
    image = render_padlock_glyph(60)
    assert image.size == (60, 60)
    assert image.mode == "RGBA"


def test_apply_gaim_lock_overlay_inactive_returns_base_unchanged():
    from lock_in.visuals import apply_gaim_lock_overlay
    from PIL import Image
    base = Image.new("RGB", (100, 100), (20, 20, 20))
    result = apply_gaim_lock_overlay(base, active=False)
    assert result.tobytes() == base.convert("RGBA").tobytes()


def test_apply_gaim_lock_overlay_active_dims_the_picture():
    from lock_in.visuals import apply_gaim_lock_overlay
    from PIL import Image
    base = Image.new("RGB", (100, 100), (200, 200, 200))
    result = apply_gaim_lock_overlay(base, active=True)
    # A corner far from the centered padlock should just be dimmed,
    # not covered by the glyph -- confirms the dim wash covers the
    # whole picture, not just a patch.
    corner = result.getpixel((2, 2))
    assert corner[:3] != (200, 200, 200)
    assert sum(corner[:3]) < sum((200, 200, 200))


def test_apply_gaim_lock_overlay_active_returns_same_size():
    from lock_in.visuals import apply_gaim_lock_overlay
    from PIL import Image
    base = Image.new("RGB", (120, 80), (50, 50, 50))
    result = apply_gaim_lock_overlay(base, active=True)
    assert result.size == (120, 80)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -k "padlock or gaim" -v`
Expected: FAIL — `ImportError`/`AttributeError`.

- [ ] **Step 3: Implement**

Add to `lock_in/visuals.py`:

```python
def render_padlock_glyph(size: int) -> Image.Image:
    """A simple padlock shape -- a rounded body with a curved shackle on top."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    body_top = size * 0.45
    draw.rounded_rectangle(
        [size * 0.2, body_top, size * 0.8, size * 0.95], radius=size * 0.08,
        fill=(230, 230, 230, 235),
    )
    draw.arc(
        [size * 0.3, size * 0.05, size * 0.7, body_top + size * 0.15],
        start=180, end=360, fill=(230, 230, 230, 235), width=max(2, round(size * 0.08)),
    )
    return image


def apply_gaim_lock_overlay(base_image: Image.Image, active: bool) -> Image.Image:
    """
    Dim the picture and paint a padlock in the middle of it, like Gaim
    sealing the UI shut for the block. `active` is whether this
    Rider's effect should show at all right now (only during a focus
    block) -- when it's False, this just hands back the picture
    exactly as it came in, same contract as apply_tier1_background_effect.
    """
    if not active:
        return base_image.convert("RGBA")
    width, height = base_image.size
    dimmed = Image.new("RGBA", (width, height), (0, 0, 0, 90))
    result = Image.alpha_composite(base_image.convert("RGBA"), dimmed)
    glyph_size = min(width, height) // 4
    glyph = render_padlock_glyph(glyph_size)
    position = ((width - glyph_size) // 2, (height - glyph_size) // 2)
    result.alpha_composite(glyph, position)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS — full file.

- [ ] **Step 5: Wire it into `ui.py`**

Add `apply_gaim_lock_overlay` to the `from .visuals import (...)` block in `lock_in/ui.py`.

In `_refresh_background_effect()`, change:

```python
        bg_dark = apply_tier1_background_effect(
            self._base_bg_dark, active_effect, effect_color_dark, progress_fraction,
        )
        self._bg_image.configure(light_image=bg_light, dark_image=bg_dark)
```

to:

```python
        bg_dark = apply_tier1_background_effect(
            self._base_bg_dark, active_effect, effect_color_dark, progress_fraction,
        )

        if self.current_tier3_effect == "lock_overlay":
            bg_light = apply_gaim_lock_overlay(bg_light, in_focus)
            bg_dark = apply_gaim_lock_overlay(bg_dark, in_focus)

        self._bg_image.configure(light_image=bg_light, dark_image=bg_dark)
```

In `_refresh_timer_widgets()`, change the call-site condition:

```python
        if self.current_tier1_effect in ("border_glow", "night_overlay"):
            self._refresh_background_effect(progress_fraction)
```

to:

```python
        if self.current_tier1_effect in ("border_glow", "night_overlay") or self.current_tier3_effect == "lock_overlay":
            self._refresh_background_effect(progress_fraction)
```

In `_on_phase_started()`, right after the ZX auto-minimize check added in Task 4:

```python
        if self.current_tier3_effect == "lock_overlay":
            # Locks the window in front of everything else for the
            # whole block, then lets go the moment it's not FOCUS
            # anymore -- never a permanent always-on-top, just for the
            # duration of the lock.
            self.attributes("-topmost", phase is Phase.FOCUS)
```

In `_on_phase_ended()`, right after `self._close_lockdown()`:

```python
        if self.current_tier3_effect == "lock_overlay":
            self.attributes("-topmost", False)
```

- [ ] **Step 6: Manual check**

Run: `python -c "import lock_in.ui as ui; print('import ok')"` then `pytest -q`
Expected: both pass, full suite green.

- [ ] **Step 7: Commit**

```bash
git add lock_in/visuals.py lock_in/ui.py tests/test_visuals.py
git commit -m "feat: add Gaim's padlock overlay and always-on-top lock"
```

---

### Task 6: Amazon — zero-UI header + zero grace period wiring

**Files:**
- Modify: `lock_in/visuals.py`, `lock_in/ui.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Consumes: `Config.zero_grace_mode` (Task 2 — set/unset here, not read here), `self.current_tier3_effect` (Task 4).
- Produces: `render_amazon_drain(width: int, height: int, progress_fraction: float) -> Image.Image`, `self._sync_zero_ui_visibility() -> None`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_visuals.py`:

```python
def test_render_amazon_drain_returns_the_requested_size():
    from lock_in.visuals import render_amazon_drain
    image = render_amazon_drain(200, 80, 0.5)
    assert image.size == (200, 80)
    assert image.mode == "RGBA"


def test_render_amazon_drain_shrinks_as_progress_increases():
    """The field DRAINS -- less of it is filled as the block finishes,
    not more (opposite direction from a normal progress bar)."""
    from lock_in.visuals import render_amazon_drain
    from PIL import ImageStat

    def alpha_sum(image):
        return ImageStat.Stat(image.getchannel("A")).sum[0]

    early = render_amazon_drain(200, 80, 0.1, )
    late = render_amazon_drain(200, 80, 0.9)
    assert alpha_sum(early) > alpha_sum(late)


def test_render_amazon_drain_is_always_the_same_amazon_green():
    """No primary/secondary color parameter on purpose -- the spec is a
    literal fixed #33691e, not derived from whichever Rider is picked."""
    from lock_in.visuals import render_amazon_drain
    image = render_amazon_drain(200, 80, 0.0)
    # top-left pixel should be fully the Amazon green, fully opaque
    pixel = image.getpixel((0, 0))
    assert pixel == (51, 105, 30, 235)   # 0x33, 0x69, 0x1e
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_visuals.py -k amazon_drain -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement the renderer**

Add to `lock_in/visuals.py`:

```python
_AMAZON_GREEN = "#33691e"


def render_amazon_drain(width: int, height: int, progress_fraction: float) -> Image.Image:
    """
    A solid Amazon-green field that drains from full to empty as the
    block goes on -- like a tank running dry. No text, no numbers, on
    purpose; that's Amazon's whole "zero UI" gimmick. Always this one
    fixed green, not derived from the Rider's own primary/secondary --
    the spec calls for a literal #33691e, full stop.
    """
    progress_fraction = max(0.0, min(1.0, progress_fraction))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    r, g, b = _hex_to_rgb(_AMAZON_GREEN)
    remaining_height = round(height * (1 - progress_fraction))
    if remaining_height > 0:
        draw.rectangle([0, 0, width, remaining_height], fill=(r, g, b, 235))
    return image
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS — full file.

- [ ] **Step 5: Restructure the header for a single toggle point**

The header currently packs `phase_label`, `time_label`, `streak_label`,
and `driver_label` directly into `header`. Wrap them in one frame so
hiding/showing all four is a single, safe `pack_forget()`/`pack()`
instead of four (which would risk the same reordering bug Tier 1
already solved once). In `_build_header()`, change:

```python
        self.phase_label = ctk.CTkLabel(
            header, text="Standing By",
            font=ctk.CTkFont(family=DISPLAY_FONT, size=16, weight="bold"),
            text_color=COLOR_IDLE,
        )
        self.phase_label.pack(pady=(4, 0))

        self.time_label = ctk.CTkLabel(
            header, text="25:00", font=ctk.CTkFont(family=DISPLAY_FONT, size=76, weight="bold"),
        )
        self.time_label.pack(pady=(0, 4))

        self.streak_label = ctk.CTkLabel(
            header, text="0 blocks done", font=ctk.CTkFont(size=12),
            text_color=COLOR_IDLE,
        )
        self.streak_label.pack()

        self.driver_label = ctk.CTkLabel(
            header, text=self.config_obj.rider_theme.upper(),
            font=ctk.CTkFont(family=DISPLAY_FONT, size=10, weight="bold"),
            text_color=self.color_driver_text,
        )
        self.driver_label.pack(pady=(2, 0))
```

to:

```python
        # Wrapped in one frame so Amazon's zero-UI mode can hide all 4
        # of these at once, safely, instead of hiding and restoring
        # each one individually. Not packed here -- self.controls
        # doesn't exist yet at this point in the method, so packing
        # happens a little further down, right after self.controls is
        # created (see the next edit below).
        self.normal_header_content = ctk.CTkFrame(header, fg_color="transparent")

        self.phase_label = ctk.CTkLabel(
            self.normal_header_content, text="Standing By",
            font=ctk.CTkFont(family=DISPLAY_FONT, size=16, weight="bold"),
            text_color=COLOR_IDLE,
        )
        self.phase_label.pack(pady=(4, 0))

        self.time_label = ctk.CTkLabel(
            self.normal_header_content, text="25:00",
            font=ctk.CTkFont(family=DISPLAY_FONT, size=76, weight="bold"),
        )
        self.time_label.pack(pady=(0, 4))

        self.streak_label = ctk.CTkLabel(
            self.normal_header_content, text="0 blocks done", font=ctk.CTkFont(size=12),
            text_color=COLOR_IDLE,
        )
        self.streak_label.pack()

        self.driver_label = ctk.CTkLabel(
            self.normal_header_content, text=self.config_obj.rider_theme.upper(),
            font=ctk.CTkFont(family=DISPLAY_FONT, size=10, weight="bold"),
            text_color=self.color_driver_text,
        )
        self.driver_label.pack(pady=(2, 0))
```

`self.controls` doesn't exist yet at this point in `_build_header()` (it's
created further down), so the conditional `.pack()` above won't fire —
remove that line entirely and instead add a plain
`self.normal_header_content.pack()` **after** `self.controls` is created
later in the same method (right after `self.controls.pack()`):

```python
        self.controls = ctk.CTkFrame(header, fg_color="transparent")
        self.controls.pack()
        controls = self.controls
```

becomes:

```python
        self.controls = ctk.CTkFrame(header, fg_color="transparent")
        self.normal_header_content.pack(before=self.controls)
        self.controls.pack()
        controls = self.controls
```

(This re-parents the pack ORDER correctly: `normal_header_content` was
already created earlier and is now explicitly placed right before
`controls`, which is also where `progress`/`progress_shape` already
sit in between — matching the original visual order exactly:
phase/time/streak/driver, then progress, then controls.)

- [ ] **Step 6: Add the zero-UI widget and sync method**

In `_build_header()`, right after `self.progress_shape = ctk.CTkLabel(header, text="", image=None)`, add:

```python
        # Amazon's "zero UI" picture -- only shown instead of everything
        # else in the header, and only during an actual focus block
        # (see _sync_zero_ui_visibility). Not packed yet on purpose.
        self.zero_ui_label = ctk.CTkLabel(header, text="", image=None)
```

Add two new module-level constants next to `PROGRESS_SHAPE_WIDTH`/`PROGRESS_SHAPE_HEIGHT`:

```python
# Amazon's zero-UI picture is bigger than the other progress pictures
# on purpose -- it's meant to dominate the header, not sit in a thin strip.
ZERO_UI_WIDTH = 340
ZERO_UI_HEIGHT = 120
```

Add the new method, near `_sync_progress_widget_visibility()`:

```python
    def _sync_zero_ui_visibility(self) -> None:
        """
        Amazon's "zero UI" look replaces the normal timer words and
        progress bar with just a draining color field, and shrinks the
        buttons to icons -- but ONLY during an actual focus block. Any
        other time (break, idle, or before you've even started) you
        see the normal UI, same as every other Rider.
        """
        active = (
            self.current_tier3_effect == "zero_ui"
            and self.session.phase is Phase.FOCUS
        )

        if active:
            self.normal_header_content.pack_forget()
            self.progress.pack_forget()
            self.progress_shape.pack_forget()
            self._timer_glow_label.place_forget()
            self.tabs.pack_forget()
            self.zero_ui_label.pack(pady=(20, 20), before=self.controls)
            self.start_button.configure(text="⏸" if self.session.is_running else "▶", width=44)
            self.skip_button.configure(text="⏭", width=44)
            self.reset_button.configure(text="⟲", width=44)
        else:
            self.zero_ui_label.pack_forget()
            if not self.normal_header_content.winfo_ismapped():
                self.normal_header_content.pack(before=self.controls)
                self._timer_glow_label.place(relx=0.5, rely=0.33, anchor="center")
                self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 16), after=self._divider_label)
                self._sync_progress_widget_visibility()
                self.start_button.configure(
                    text="Pause" if self.session.is_running else self._henshin_word(), width=140,
                )
                self.skip_button.configure(text="Skip", width=80)
                self.reset_button.configure(text="Reset", width=80)

    def _refresh_zero_ui_drain(self, progress_fraction: float) -> None:
        """Redraw Amazon's draining field and push it onto the label already
        on screen -- same light/dark-both-the-same trick as the button glow,
        since this picture's color never depends on appearance mode."""
        drain = render_amazon_drain(ZERO_UI_WIDTH, ZERO_UI_HEIGHT, progress_fraction)
        if hasattr(self, "_zero_ui_image"):
            self._zero_ui_image.configure(light_image=drain, dark_image=drain)
        else:
            self._zero_ui_image = ctk.CTkImage(
                light_image=drain, dark_image=drain, size=(ZERO_UI_WIDTH, ZERO_UI_HEIGHT),
            )
            self.zero_ui_label.configure(image=self._zero_ui_image)
```

`skip_button`/`reset_button` don't exist as named attributes yet (the
Skip/Reset buttons are currently anonymous, created inline). Find, in
`_build_header()`:

```python
        ctk.CTkButton(controls, text="Skip", width=80, height=40,
                      fg_color="transparent", border_width=2,
                      border_color=COLOR_TIMER_ACCENT, text_color=COLOR_TIMER_ACCENT,
                      hover_color=("#d0ebff", "#173a5e"),
                      command=self._on_skip).grid(row=0, column=1, padx=6)

        ctk.CTkButton(controls, text="Reset", width=80, height=40,
```

and give both a `self.` name so `_sync_zero_ui_visibility()` can
reconfigure them:

```python
        self.skip_button = ctk.CTkButton(
            controls, text="Skip", width=80, height=40,
            fg_color="transparent", border_width=2,
            border_color=COLOR_TIMER_ACCENT, text_color=COLOR_TIMER_ACCENT,
            hover_color=("#d0ebff", "#173a5e"),
            command=self._on_skip,
        )
        self.skip_button.grid(row=0, column=1, padx=6)

        self.reset_button = ctk.CTkButton(
            controls, text="Reset", width=80, height=40,
```

(keep that button's remaining existing options/`.grid(...)` call as they are, just capture it as `self.reset_button = ctk.CTkButton(...)` the same way).

- [ ] **Step 7: Wire it into the tick loop and phase transitions**

Add `render_amazon_drain` to the `from .visuals import (...)` block.

In `_refresh_timer_widgets()`, right after the existing block that
handles `border_glow`/`night_overlay`/`lock_overlay` background
refresh (added in Task 5), add:

```python
        if self.current_tier3_effect == "zero_ui" and phase is Phase.FOCUS:
            self._refresh_zero_ui_drain(progress_fraction)
```

In `_on_phase_started()`, after the ZX/Gaim checks added in Tasks 4-5,
add:

```python
        if self.current_tier3_effect == "zero_ui":
            self._sync_zero_ui_visibility()
            self.config_obj.zero_grace_mode = phase is Phase.FOCUS
```

In `_on_phase_ended()`, after `self._close_lockdown()`, add:

```python
        if self.current_tier3_effect == "zero_ui":
            self._sync_zero_ui_visibility()
            self.config_obj.zero_grace_mode = False
```

**Edge case:** switching Rider themes mid-focus-block, while Amazon's
zero-UI is showing, would otherwise leave `normal_header_content` and
`self.tabs` stuck hidden under the new Rider (nothing else re-shows
them, since `_rebuild_tabs()` only rebuilds the tab contents, not the
header). In `_on_rider_theme_change()`, right after the line
`self.current_tier3_effect = theme.tier3_effect` runs (inside the
`_apply_rider_theme()` call already made from here), add one more call
at the end of `_on_rider_theme_change()`, alongside the existing
`self._sync_progress_widget_visibility()` line:

```python
        self._sync_progress_widget_visibility()
        self._sync_zero_ui_visibility()
```

This safely does nothing for the other 37 Riders (the `active` check
inside `_sync_zero_ui_visibility()` is `False` for anything but
Amazon), and correctly restores the header if you switch away from
Amazon while it was showing.

- [ ] **Step 8: Manual check**

Run: `python -c "import lock_in.ui as ui; print('import ok')"` then `pytest -q`
Expected: both pass, full suite green.

- [ ] **Step 9: Commit**

```bash
git add lock_in/visuals.py lock_in/ui.py tests/test_visuals.py
git commit -m "feat: add Amazon's zero-UI header and zero-grace wiring"
```

---

### Task 7: X — goal-entry gate

**Files:**
- Modify: `lock_in/ui.py`

**Interfaces:**
- Consumes: `self.current_tier3_effect` (Task 4).
- Produces: `self.current_goal_text: str`, `self._show_goal_gate() -> None`, `self._do_toggle() -> None` (renamed from the body of the old `_on_toggle()`).

- [ ] **Step 1: Initialize `current_goal_text`**

In `__init__`, near where other `self.current_*` state is first set up
(right after `self._apply_rider_theme()` is a reasonable spot), add:

```python
        # X's goal-entry gate stores what you typed here -- in-memory
        # only, same rule as Fourze's constellation state: it resets
        # every time the app restarts, no save file needed.
        self.current_goal_text = ""
```

- [ ] **Step 2: Split `_on_toggle()` into a gate check + the real toggle**

Find:

```python
    def _on_toggle(self) -> None:
        was_running = self.session.is_running
        for event in self.session.toggle():
            if event is Event.PHASE_STARTED:
                self._on_phase_started()

        # Resuming a phase that was already started doesn't send an event,
        # so we check and update things ourselves here.
        if not was_running and self.session.is_running:
            if self.session.phase is Phase.FOCUS:
                self.monitor.resume()
        else:
            self.monitor.pause()

        self._refresh_timer_widgets()
```

Replace with:

```python
    def _on_toggle(self) -> None:
        # X's gimmick: starting fresh (not resuming from pause) needs a
        # goal typed in first. Resuming never shows the gate again --
        # only self.session.phase is Phase.IDLE catches "about to
        # start a brand new block."
        if self.current_tier3_effect == "goal_gate" and self.session.phase is Phase.IDLE:
            self._show_goal_gate()
            return
        self._do_toggle()

    def _do_toggle(self) -> None:
        was_running = self.session.is_running
        for event in self.session.toggle():
            if event is Event.PHASE_STARTED:
                self._on_phase_started()

        # Resuming a phase that was already started doesn't send an event,
        # so we check and update things ourselves here.
        if not was_running and self.session.is_running:
            if self.session.phase is Phase.FOCUS:
                self.monitor.resume()
        else:
            self.monitor.pause()

        self._refresh_timer_widgets()

    def _show_goal_gate(self) -> None:
        """
        X's gimmick: before you can even start, you have to say what
        you're working on. Mirrors _show_lockdown()'s full-screen
        overlay trick, but this one asks a question instead of
        enforcing a wait -- no countdown, no timeout, just a text box.
        """
        overlay = ctk.CTkToplevel(self)
        overlay.attributes("-topmost", True)
        try:
            overlay.attributes("-fullscreen", True)
        except Exception:
            overlay.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        overlay.configure(fg_color="#121417")
        overlay.protocol("WM_DELETE_WINDOW", lambda: None)

        title = "DEEP SETUP" if self._is_tokusatsu() else "Set your goal"
        ctk.CTkLabel(overlay, text=title, font=ctk.CTkFont(size=40, weight="bold"),
                     text_color=self.color_lockdown_text).pack(pady=(220, 20))
        ctk.CTkLabel(overlay, text="What are you working on this block?",
                     font=ctk.CTkFont(size=16), text_color="#9aa4b2").pack(pady=(0, 16))

        entry = ctk.CTkEntry(overlay, width=420, height=44, font=ctk.CTkFont(size=15))
        entry.pack(pady=(0, 8))
        entry.focus_set()

        hint = ctk.CTkLabel(overlay, text="", font=ctk.CTkFont(size=12), text_color=COLOR_DANGER)
        hint.pack()

        def submit(event=None) -> None:
            text = entry.get().strip()
            if not text:
                hint.configure(text="Type something before you begin.")
                return
            self.current_goal_text = text
            overlay.destroy()
            self._do_toggle()

        entry.bind("<Return>", submit)
        begin_word = "Begin" if self._is_tokusatsu() else "Start"
        ctk.CTkButton(overlay, text=begin_word, width=200, command=submit).pack(pady=20)
```

- [ ] **Step 3: Show the goal text during the block**

In `_refresh_timer_widgets()`, right after the line
`progress_fraction = self.session.progress`, add:

```python
        driver_text = self.config_obj.rider_theme.upper()
        if phase is Phase.FOCUS and self.current_tier3_effect == "goal_gate" and self.current_goal_text:
            driver_text = self.current_goal_text.upper()
        self.driver_label.configure(text=driver_text)
```

- [ ] **Step 4: Manual check**

Run: `python -c "import lock_in.ui as ui; print('import ok')"` then `pytest -q`
Expected: both pass, full suite green.

- [ ] **Step 5: Commit**

```bash
git add lock_in/ui.py
git commit -m "feat: add X's goal-entry gate before starting a block"
```

---

### Task 8: 555 — code-entry early unlock

**Files:**
- Modify: `lock_in/ui.py`

**Interfaces:**
- Consumes: `self.current_tier3_effect` (Task 4), `self._close_lockdown()` (already exists).

- [ ] **Step 1: Add the code-entry widgets to `_show_lockdown()`**

Find, in `_show_lockdown()`:

```python
        end_button_text = "Abort Mission" if self._is_tokusatsu() else "End Session"
        ctk.CTkButton(overlay, text=end_button_text, width=200,
                      fg_color="transparent", border_width=1,
                      text_color="#6b7480", hover_color="#1d2026",
                      command=self._end_session_from_lockdown).pack()
```

Add, right before it:

```python
        if self.current_tier3_effect == "code_unlock":
            code_entry = ctk.CTkEntry(overlay, width=140, justify="center",
                                       font=ctk.CTkFont(size=16))
            code_entry.pack(pady=(4, 4))
            code_hint = ctk.CTkLabel(overlay, text="Enter code to unlock early",
                                      font=ctk.CTkFont(size=11), text_color="#6b7480")
            code_hint.pack(pady=(0, 12))

            def check_code(event=None) -> None:
                if code_entry.get().strip() == "555":
                    self._close_lockdown()
                else:
                    code_entry.delete(0, "end")
                    code_hint.configure(text="Incorrect code", text_color=COLOR_DANGER)

            code_entry.bind("<Return>", check_code)
```

- [ ] **Step 2: Manual check**

Run: `python -c "import lock_in.ui as ui; print('import ok')"` then `pytest -q`
Expected: both pass, full suite green.

- [ ] **Step 3: Commit**

```bash
git add lock_in/ui.py
git commit -m "feat: add 555's code-entry early unlock to the lockdown screen"
```

---

### Task 9: Manual screenshot verification

**Files:**
- Create (scratch, not committed): a throwaway verification script, same pattern as Tier 1/2's.

- [ ] **Step 1: Screenshot check for each of the 5 Riders + one control**

Write a script (in your scratch/temp directory, NOT the repo) that
launches `ui.LockInApp()` and, for each of `"Kamen Rider X (1974)"`,
`"Kamen Rider Amazon (1974)"`, `"Kamen Rider ZX (1982)"`,
`"Kamen Rider Gaim (2013)"`, `"Kamen Rider 555 (2003)"`, and one
control Rider (`"Kamen Rider V3 (1973)"`):

1. Sets the theme via `app._on_rider_theme_change(rider)` (remember
   the extra `app.update()` immediately after, before touching
   `app.tabs` — `_rebuild_tabs()` recreates the `CTkTabview` object,
   and skipping this exact call caused a blank-tab bug during Tier 2's
   verification).
2. For X: click `app.start_button.invoke()` while idle, confirm the
   goal-gate overlay appears (check `app.winfo_children()` for a new
   `CTkToplevel`), type a goal into its entry, submit, confirm
   `app.current_goal_text` is set and the session actually started.
3. For Amazon: force a focus block via `app.session.start()` +
   `app._on_phase_started()`, confirm `app.zero_ui_label` is packed
   (`winfo_ismapped()`) and `app.normal_header_content` is not.
   Screenshot it. Confirm `app.config_obj.zero_grace_mode` is `True`
   while focused, `False` after `app._on_phase_ended()`.
4. For ZX: confirm the header/background render in grayscale
   (screenshot, eyeball it) and that starting a focus block calls
   `app.iconify()` (check `app.state()` afterward — should be
   `"iconic"`; call `app.deiconify()` before continuing the script).
5. For Gaim: force a focus block, confirm `app.attributes("-topmost")`
   is `1`, screenshot the dimmed background + padlock, confirm it
   reverts to `0` after `_on_phase_ended()`.
6. For 555: trigger `app._show_lockdown()` directly, type `555` into
   the code entry, confirm the lockdown overlay closes; repeat with a
   wrong code, confirm it stays open and shows "Incorrect code".
7. For the control Rider: confirm none of the above widgets/behaviors
   appear — plain lockdown screen, plain header, no monochrome, no
   auto-minimize, no goal gate.

- [ ] **Step 2: Fix anything that looks wrong, then delete the scratch script and screenshots**

They're verification-only, not part of the app — don't commit them.
Also reset the real `config.json` back to defaults afterward if the
script's `zero_grace_mode`/`stealth_mute_mode` toggling wrote to it
(same caveat flagged in every prior tier's verification step) — run:

```bash
python -c "from lock_in.config import Config; Config().save()"
```

---

### Task 10: Docs and version

**Files:**
- Modify: `README.md`
- Modify: `.gitignore` (only if needed — check first, don't add speculatively)
- Modify: `lock_in/__init__.py`

- [ ] **Step 1: Update the README**

Under the Tier 2 section added previously, add a new subsection:

```markdown
### Tier 3: 5 Riders with enforcement/interaction tweaks

Five more Riders change actual behavior, not just looks:

- **X** — before a fresh focus block can start, a full-screen prompt
  asks what you're working on. No timeout — type when you're ready.
  Your answer replaces the Rider-name label for that block.
- **Amazon** — during a focus block, the whole UI strips down to a
  solid draining green field (Pause/Skip/Reset shrink to icons instead
  of disappearing), and the grace period drops to 0 seconds.
- **ZX** — the whole app renders in monochrome for as long as ZX is
  selected, and auto-minimizes the moment a focus block starts, with
  Sounds and Desktop notifications silenced for that block.
- **Gaim** — during a focus block, the window stays always-on-top, the
  background dims, and a padlock appears — a strong visual deterrent,
  never a real block on switching windows.
- **555** — the existing Lockdown screen gets a second way out: type
  `555` to skip the rest of the countdown and return to work early.

See `docs/superpowers/specs/2026-08-11-tier3-enforcement-interaction-design.md`
for the full design, and `docs/superpowers/plans/2026-08-11-tier3-enforcement-interaction.md`
for the implementation plan.
```

- [ ] **Step 2: Check `.gitignore`**

No new generated file type is introduced by this feature — confirm no
edit is actually needed.

- [ ] **Step 3: Bump the version**

In `lock_in/__init__.py`, change `__version__ = "2.1.0"` to
`__version__ = "2.2.0"` — a minor bump for a real new feature tier,
matching this session's convention (Tier 1 → 2.0.0, Tier 2 → 2.1.0).

- [ ] **Step 4: Run the full test suite one final time, in both environments**

Run: `venv\Scripts\python.exe -m pytest -q` and `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS in both — full suite, no failures.

- [ ] **Step 5: Commit**

```bash
git add README.md lock_in/__init__.py
git commit -m "docs: document Tier 3 enforcement/interaction tweaks, bump to v2.2.0"
```

---

## Self-Review Notes

- **Spec coverage:** all 5 Riders' items (Tasks 4-8), the shared
  `tier3_effect` field (Task 1), the two `Config` read-side overrides
  (Task 2) and their real call-site wiring (Task 3), the desaturation
  cascade's exact mechanism (Task 4), Gaim's reuse of Tier 1's
  background-compositing (Task 5), and testing approach (pure-function
  tests for everything in `visuals.py`/`rider_themes.py`/`config.py`,
  screenshot verification for `ui.py` wiring) are all covered.
- **Correction made while grounding this plan in the real code:** the
  spec said ZX's auto-minimize would "reuse `minimize_window()`
  (already exists, used today for blocking)" — reading the actual call
  sites showed `minimize_window()` is built to minimize *other*
  windows via an OS-level handle (used when a blocked app needs
  minimizing), not this app's own window. `self.iconify()` (Tkinter's
  own built-in, cross-platform) is the correct call for the app
  minimizing itself, and is what Task 4 actually uses.
- **Placeholder scan:** no TBD/TODO; every step has real, runnable code.
- **Type consistency:** `current_tier3_effect` (Task 4) is read with
  the same 5 string values (`"goal_gate"`, `"zero_ui"`,
  `"stealth_mute"`, `"lock_overlay"`, `"code_unlock"`) everywhere it's
  checked in Tasks 5-8, matching exactly what Task 1 assigns in
  `rider_themes.py`.
