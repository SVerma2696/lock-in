# Lock In: Tier 1 Rider Progress Variants Implementation Plan

> **Shipped in v2.0.0.** Implemented inline (not via subagent dispatch),
> with three corrections made along the way, documented in the spec
> (`docs/superpowers/specs/2026-08-10-tier1-rider-progress-variants-design.md`):
> (1) the progress widget swap was rescoped to touch ONLY the 4 Riders
> with a real custom shape, using `pack(before=self.controls)` instead
> of switching all 38 Riders to a picture widget — the other 29,
> including Agito/Black/Stronger/Drive/Kiva, keep the exact native
> `CTkProgressBar` they always had; (2) Black's gimmick was corrected
> from a "faceted" shape to a stricter dark-mode text-contrast tweak;
> (3) Drive's gimmick was corrected from "speedlines" to an
> accelerating-fill easing curve. A real bug was also caught and fixed
> during screenshot verification: Fourze's constellation stars were
> drawn in raw white and vanished against its own near-white light-mode
> background — fixed with a `_visible_shape_color()` helper in
> `visuals.py`, the same darken/lighten trick already used for text.
> The task bodies below describe the ORIGINAL plan (flat-bar renderer,
> 6 shapes, all-38-Rider widget swap) and are kept for history — they do
> not fully match what shipped.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give 9 specific Kamen Riders (1971, Skyrider, Stronger, Black, Fourze, Build, Drive, Agito, Kiva) their own unique visual treatment during a focus block — a custom-shaped progress indicator, a color-behavior tweak, or a chrome-level background effect — while every other Rider keeps today's plain bar unchanged.

**Architecture:** All new drawing lives in `lock_in/visuals.py` as pure functions (no Tkinter, no state) — six new progress-shape renderers, two chrome-level background effects, and small dispatchers that pick the right one from a Rider's new `tier1_effect` field. `ui.py` keeps the existing native `CTkProgressBar` completely unchanged for all 29 non-Tier-1 Riders (including Agito, whose "gimmick" is just a different `progress_color` value passed to that same native bar). Only the 6 Riders with an actual custom shape get a second, picture-based `CTkLabel` sibling widget that's shown instead — toggled with `pack(before=self.controls)` so re-showing it can never scramble the layout order, which is what a naive `pack_forget()`/`pack()` toggle would risk. Stronger and Kiva don't touch the progress bar at all; their effect is composited into the existing background picture in Pillow, entirely inside `visuals.py`, before it ever reaches a widget — never two overlapping semi-transparent widgets, which Tkinter renders incorrectly.

**Tech Stack:** Python 3.11+, Pillow (`PIL.Image`, `PIL.ImageDraw`), CustomTkinter (`CTkImage`, `CTkLabel`), pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-10-tier1-rider-progress-variants-design.md` — this plan implements it in full; no other tier.
- Purely visual — no Config/Settings value, timer length, or blocking behavior changes.
- No git commands as part of any task. The user runs every git step themselves at the end.
- Comments stay "simple enough for a 5 year old to understand" — short, plain-English, explain *why* not *what*, matching every existing comment in `rider_themes.py` and `visuals.py`.
- TDD: every new function gets a failing test first, then the minimal implementation, following this codebase's existing pattern (`session.py`, `enforcer.py`, `classifier.py`, `rider_themes.py`, `visuals.py` are all unit-tested with no display server).
- Only the 9 named Riders get a `tier1_effect` other than `"none"`. Every other Rider's rendered output must be provably unchanged (covered by regression tests in Task 1 and Task 10).

---

### Task 1: `tier1_effect` field on `RiderTheme`

**Files:**
- Modify: `lock_in/rider_themes.py`
- Test: `tests/test_rider_themes.py`

**Interfaces:**
- Produces: `RiderTheme.tier1_effect: str` (dataclass field, default `"none"`). Values used elsewhere in this plan: `"windmill"`, `"rising_bar"`, `"border_glow"`, `"faceted"`, `"constellation"`, `"vials"`, `"speedlines"`, `"color_interpolation"`, `"night_overlay"`, `"none"`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_rider_themes.py`:

```python
def test_tier1_effect_defaults_to_none_for_ordinary_riders():
    assert RIDER_THEMES["Kamen Rider V3 (1973)"].tier1_effect == "none"
    assert RIDER_THEMES["Kamen Rider Gavv (2024)"].tier1_effect == "none"


def test_tier1_effect_is_assigned_to_exactly_the_9_named_riders():
    expected = {
        "Kamen Rider (1971)": "windmill",
        "Kamen Rider Skyrider (1979)": "rising_bar",
        "Kamen Rider Stronger (1975)": "border_glow",
        "Kamen Rider Black (1987)": "faceted",
        "Kamen Rider Fourze (2011)": "constellation",
        "Kamen Rider Build (2017)": "vials",
        "Kamen Rider Drive (2014)": "speedlines",
        "Kamen Rider Agito (2001)": "color_interpolation",
        "Kamen Rider Kiva (2008)": "night_overlay",
    }
    for name, effect in expected.items():
        assert RIDER_THEMES[name].tier1_effect == effect, name

    # Nobody outside this list should have picked up an effect by accident.
    everyone_else = set(RIDER_THEMES) - set(expected)
    for name in everyone_else:
        assert RIDER_THEMES[name].tier1_effect == "none", name
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rider_themes.py -k tier1_effect -v`
Expected: FAIL — `AttributeError: 'RiderTheme' object has no attribute 'tier1_effect'`

- [ ] **Step 3: Add the field and assign the 9 Riders**

In `lock_in/rider_themes.py`, add the field to the `RiderTheme` dataclass (right after `secondary`, before the `@property` methods):

```python
@dataclass(frozen=True)
class RiderTheme:
    """One Rider's two colors, plus which era and year they're from."""

    era: str
    year: int
    primary: str
    secondary: str
    # "none" for every Rider except the 9 with a Tier 1 gimmick (see
    # docs/superpowers/specs/2026-08-10-tier1-rider-progress-variants-design.md).
    # visuals.py reads this to decide what the progress bar/background
    # should look like for this Rider.
    tier1_effect: str = "none"
```

Then edit exactly these 9 lines inside `RIDER_THEMES` to add the keyword argument (every other line is untouched):

```python
    "Kamen Rider (1971)": RiderTheme("Showa", 1971, "#1b5e3a", "#c0392b", tier1_effect="windmill"),
    "Kamen Rider Stronger (1975)": RiderTheme("Showa", 1975, "#c62828", "#212121", tier1_effect="border_glow"),
    "Kamen Rider Skyrider (1979)": RiderTheme("Showa", 1979, "#2e7d32", "#8d6e63", tier1_effect="rising_bar"),
    "Kamen Rider Black (1987)": RiderTheme("Showa", 1987, "#1a1a1a", "#00c853", tier1_effect="faceted"),
    "Kamen Rider Agito (2001)": RiderTheme("Heisei", 2001, "#ffca28", "#212121", tier1_effect="color_interpolation"),
    "Kamen Rider Kiva (2008)": RiderTheme("Heisei", 2008, "#8e0000", "#ffca28", tier1_effect="night_overlay"),
    "Kamen Rider Fourze (2011)": RiderTheme("Heisei", 2011, "#ffffff", "#ef6c00", tier1_effect="constellation"),
    "Kamen Rider Drive (2014)": RiderTheme("Heisei", 2014, "#c62828", "#212121", tier1_effect="speedlines"),
    "Kamen Rider Build (2017)": RiderTheme("Heisei", 2017, "#c62828", "#1565c0", tier1_effect="vials"),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rider_themes.py -v`
Expected: PASS — all tests in the file, including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add lock_in/rider_themes.py tests/test_rider_themes.py
git commit -m "feat: add tier1_effect field for the 9 Tier 1 Rider gimmicks"
```

---

### Task 2: Color helpers — Agito's "awakening" interpolation

**Files:**
- Modify: `lock_in/visuals.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Consumes: `lock_in.rider_themes.darken(hex_color: str, factor: float = 0.35) -> str` (already exists).
- Produces: `interpolate_agito_color(progress_fraction: float, primary: str) -> str`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_visuals.py`:

```python
def test_agito_color_at_zero_progress_is_the_muted_start_color():
    from lock_in.visuals import interpolate_agito_color
    from lock_in.rider_themes import darken
    assert interpolate_agito_color(0.0, "#ffca28") == darken("#ffca28", 0.55)


def test_agito_color_at_full_progress_is_the_real_primary_color():
    from lock_in.visuals import interpolate_agito_color
    assert interpolate_agito_color(1.0, "#ffca28") == "#ffca28"


def test_agito_color_gets_brighter_as_progress_increases():
    """The whole point: it "wakes up" partway through, not just at 0/1."""
    from lock_in.visuals import interpolate_agito_color

    def brightness(hex_color):
        hex_color = hex_color.lstrip("#")
        return sum(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    early = brightness(interpolate_agito_color(0.2, "#ffca28"))
    middle = brightness(interpolate_agito_color(0.5, "#ffca28"))
    late = brightness(interpolate_agito_color(0.8, "#ffca28"))
    assert early < middle < late


def test_agito_color_clamps_out_of_range_progress():
    from lock_in.visuals import interpolate_agito_color
    assert interpolate_agito_color(-1.0, "#ffca28") == interpolate_agito_color(0.0, "#ffca28")
    assert interpolate_agito_color(5.0, "#ffca28") == interpolate_agito_color(1.0, "#ffca28")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -k agito -v`
Expected: FAIL — `ImportError: cannot import name 'interpolate_agito_color'`

- [ ] **Step 3: Implement**

In `lock_in/visuals.py`, add the import and the two functions. Change the top import line:

```python
from .rider_themes import darken
```

Add near `_hex_to_rgb` (after it):

```python
def _lerp_hex(start: str, end: str, fraction: float) -> str:
    """Slide a color from `start` to `end`. fraction=0 gives back
    `start` exactly, fraction=1 gives back `end` exactly, and anything
    in between is a mix -- like a dimmer switch, but for color."""
    r1, g1, b1 = _hex_to_rgb(start)
    r2, g2, b2 = _hex_to_rgb(end)
    r = round(r1 + (r2 - r1) * fraction)
    g = round(g1 + (g2 - g1) * fraction)
    b = round(b1 + (b2 - b1) * fraction)
    return f"#{r:02x}{g:02x}{b:02x}"


def interpolate_agito_color(progress_fraction: float, primary: str) -> str:
    """
    Agito's whole story is a sleeping power waking up. So instead of a
    plain gold progress bar, it starts dim and quietly brightens to the
    real color as the focus block gets closer to done.

    `progress_fraction` is how far through the block we are (0 = just
    started, 1 = finished) -- same number the progress bar itself uses.
    """
    progress_fraction = max(0.0, min(1.0, progress_fraction))
    muted_start = darken(primary, 0.55)
    return _lerp_hex(muted_start, primary, progress_fraction)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS — all tests in the file.

- [ ] **Step 5: Commit**

```bash
git add lock_in/visuals.py tests/test_visuals.py
git commit -m "feat: add Agito's awakening color interpolation"
```

---

### Task 3: The shared flat-bar renderer (today's plain look, as a picture)

**Files:**
- Modify: `lock_in/visuals.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Produces: `render_flat_bar_progress(width: int, height: int, progress_fraction: float, fill_color: str, dark: bool) -> Image.Image`.

- [ ] **Step 1: Write the failing tests**

```python
def test_flat_bar_progress_returns_the_requested_size():
    from lock_in.visuals import render_flat_bar_progress
    image = render_flat_bar_progress(200, 20, 0.5, "#ff0000", dark=False)
    assert image.size == (200, 20)
    assert image.mode == "RGBA"


def test_flat_bar_progress_fills_more_at_higher_progress():
    from lock_in.visuals import render_flat_bar_progress
    from PIL import ImageStat

    def alpha_sum(image):
        return ImageStat.Stat(image.getchannel("A")).sum[0]

    low = render_flat_bar_progress(200, 20, 0.1, "#ff0000", dark=False)
    high = render_flat_bar_progress(200, 20, 0.9, "#ff0000", dark=False)
    assert alpha_sum(high) > alpha_sum(low)


def test_flat_bar_progress_at_zero_has_no_fill_color_pixels():
    from lock_in.visuals import render_flat_bar_progress
    image = render_flat_bar_progress(200, 20, 0.0, "#ff0000", dark=False)
    # Nothing pure-red should be drawn yet -- only the empty track.
    red_pixels = sum(
        1 for pixel in image.getdata() if pixel[0] > 200 and pixel[1] < 50 and pixel[3] > 200
    )
    assert red_pixels == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -k flat_bar -v`
Expected: FAIL — `ImportError: cannot import name 'render_flat_bar_progress'`

- [ ] **Step 3: Implement**

Add to `lock_in/visuals.py`:

```python
def render_flat_bar_progress(
    width: int, height: int, progress_fraction: float, fill_color: str, dark: bool,
) -> Image.Image:
    """
    The plain progress bar look -- a rounded track that fills left to
    right. Every Rider outside Tier 1 uses this exact picture (and so
    does Agito, just with a color that changes over time instead of a
    shape that changes).
    """
    progress_fraction = max(0.0, min(1.0, progress_fraction))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    radius = height // 2

    track_color = (255, 255, 255, 35) if dark else (0, 0, 0, 25)
    draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, fill=track_color)

    filled_width = round((width - 1) * progress_fraction)
    if filled_width > radius:
        r, g, b = _hex_to_rgb(fill_color)
        draw.rounded_rectangle(
            [0, 0, filled_width, height - 1], radius=radius, fill=(r, g, b, 255),
        )

    return image
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lock_in/visuals.py tests/test_visuals.py
git commit -m "feat: add the shared flat-bar progress renderer"
```

---

### Task 4: Kamen Rider (1971) — windmill progress

**Files:**
- Modify: `lock_in/visuals.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Produces: `render_windmill_progress(width: int, height: int, progress_fraction: float, primary: str, secondary: str, dark: bool) -> Image.Image`.

- [ ] **Step 1: Write the failing tests**

```python
def test_windmill_progress_returns_the_requested_size():
    from lock_in.visuals import render_windmill_progress
    image = render_windmill_progress(80, 80, 0.5, "#1b5e3a", "#c0392b", dark=False)
    assert image.size == (80, 80)
    assert image.mode == "RGBA"


def test_windmill_progress_fills_more_blades_at_higher_progress():
    from lock_in.visuals import render_windmill_progress
    from PIL import ImageStat

    def alpha_sum(image):
        return ImageStat.Stat(image.getchannel("A")).sum[0]

    quarter = render_windmill_progress(80, 80, 0.25, "#1b5e3a", "#c0392b", dark=False)
    full = render_windmill_progress(80, 80, 1.0, "#1b5e3a", "#c0392b", dark=False)
    assert alpha_sum(full) > alpha_sum(quarter)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -k windmill -v`
Expected: FAIL — `ImportError: cannot import name 'render_windmill_progress'`

- [ ] **Step 3: Implement**

Add to `lock_in/visuals.py`:

```python
def render_windmill_progress(
    width: int, height: int, progress_fraction: float,
    primary: str, secondary: str, dark: bool,
) -> Image.Image:
    """
    The original Kamen Rider's whole origin is wind power, so his
    progress bar is a 4-bladed turbine. Blades light up one at a time
    as the block gets closer to done, like the turbine spinning up.
    """
    progress_fraction = max(0.0, min(1.0, progress_fraction))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")

    cx, cy = width / 2, height / 2
    radius = min(width, height) / 2 - 4
    r1, g1, b1 = _hex_to_rgb(primary)
    r2, g2, b2 = _hex_to_rgb(secondary)
    dim_blade = (r1, g1, b1, 55 if dark else 70)
    lit_blade = (r1, g1, b1, 230)
    outline = (r2, g2, b2, 200)

    lit_blades = round(progress_fraction * 4)
    bbox = [cx - radius, cy - radius, cx + radius, cy + radius]

    for blade in range(4):
        start = blade * 90
        end = start + 80  # 10-degree gap between blades, like a real turbine
        color = lit_blade if blade < lit_blades else dim_blade
        draw.pieslice(bbox, start=start, end=end, fill=color, outline=outline)

    return image
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lock_in/visuals.py tests/test_visuals.py
git commit -m "feat: add Kamen Rider (1971) windmill progress shape"
```

---

### Task 5: Skyrider — rising bar progress

**Files:**
- Modify: `lock_in/visuals.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Produces: `render_rising_bar_progress(width: int, height: int, progress_fraction: float, primary: str, secondary: str, dark: bool) -> Image.Image`.

- [ ] **Step 1: Write the failing tests**

```python
def test_rising_bar_progress_returns_the_requested_size():
    from lock_in.visuals import render_rising_bar_progress
    image = render_rising_bar_progress(60, 100, 0.5, "#2e7d32", "#8d6e63", dark=False)
    assert image.size == (60, 100)
    assert image.mode == "RGBA"


def test_rising_bar_progress_rises_more_at_higher_progress():
    from lock_in.visuals import render_rising_bar_progress
    from PIL import ImageStat

    def alpha_sum(image):
        return ImageStat.Stat(image.getchannel("A")).sum[0]

    low = render_rising_bar_progress(60, 100, 0.1, "#2e7d32", "#8d6e63", dark=False)
    high = render_rising_bar_progress(60, 100, 0.9, "#2e7d32", "#8d6e63", dark=False)
    assert alpha_sum(high) > alpha_sum(low)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -k rising_bar -v`
Expected: FAIL — `ImportError: cannot import name 'render_rising_bar_progress'`

- [ ] **Step 3: Implement**

Add to `lock_in/visuals.py`:

```python
def render_rising_bar_progress(
    width: int, height: int, progress_fraction: float,
    primary: str, secondary: str, dark: bool,
) -> Image.Image:
    """
    Skyrider's whole thing is gliding. So instead of the usual
    left-to-right bar, this one rises from the bottom, like an
    altimeter climbing as the block gets closer to done.
    """
    progress_fraction = max(0.0, min(1.0, progress_fraction))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")

    r1, g1, b1 = _hex_to_rgb(primary)
    r2, g2, b2 = _hex_to_rgb(secondary)
    track_color = (r2, g2, b2, 50 if dark else 70)
    fill_color = (r1, g1, b1, 230)

    bar_width = max(6, width // 4)
    left = (width - bar_width) // 2
    draw.rectangle([left, 2, left + bar_width, height - 2], fill=track_color)

    filled_height = round((height - 4) * progress_fraction)
    if filled_height > 0:
        top = (height - 2) - filled_height
        draw.rectangle([left, top, left + bar_width, height - 2], fill=fill_color)

    return image
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lock_in/visuals.py tests/test_visuals.py
git commit -m "feat: add Skyrider rising-bar progress shape"
```

---

### Task 6: Fourze — constellation progress

**Files:**
- Modify: `lock_in/visuals.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Produces: `render_constellation_progress(width: int, height: int, progress_fraction: float, primary: str, secondary: str, dark: bool) -> Image.Image`.

- [ ] **Step 1: Write the failing tests**

```python
def test_constellation_progress_returns_the_requested_size():
    from lock_in.visuals import render_constellation_progress
    image = render_constellation_progress(200, 60, 0.5, "#ffffff", "#ef6c00", dark=True)
    assert image.size == (200, 60)
    assert image.mode == "RGBA"


def test_constellation_progress_lights_more_stars_at_higher_progress():
    from lock_in.visuals import render_constellation_progress
    from PIL import ImageStat

    def alpha_sum(image):
        return ImageStat.Stat(image.getchannel("A")).sum[0]

    low = render_constellation_progress(200, 60, 0.1, "#ffffff", "#ef6c00", dark=True)
    high = render_constellation_progress(200, 60, 0.9, "#ffffff", "#ef6c00", dark=True)
    assert alpha_sum(high) > alpha_sum(low)


def test_constellation_progress_star_layout_is_stable_between_calls():
    """The stars must sit in the same spots every time, or the picture
    would visibly jump around every 200ms redraw."""
    from lock_in.visuals import render_constellation_progress
    first = render_constellation_progress(200, 60, 0.5, "#ffffff", "#ef6c00", dark=True)
    second = render_constellation_progress(200, 60, 0.5, "#ffffff", "#ef6c00", dark=True)
    assert first.tobytes() == second.tobytes()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -k constellation -v`
Expected: FAIL — `ImportError: cannot import name 'render_constellation_progress'`

- [ ] **Step 3: Implement**

Add to `lock_in/visuals.py`:

```python
_FOURZE_STAR_COUNT = 8


def _fourze_star_positions(width: int, height: int) -> list[tuple[int, int]]:
    """
    Always the same 8 spots for a given picture size -- a fixed seed
    means the stars never jump around between redraws, they just light
    up one at a time as progress climbs.
    """
    rng = random.Random(2011)  # Fourze's debut year, just a fun fixed seed
    margin = 6
    return [
        (
            rng.randrange(margin, max(margin + 1, width - margin)),
            rng.randrange(margin, max(margin + 1, height - margin)),
        )
        for _ in range(_FOURZE_STAR_COUNT)
    ]


def render_constellation_progress(
    width: int, height: int, progress_fraction: float,
    primary: str, secondary: str, dark: bool,
) -> Image.Image:
    """
    Fourze is a space show, so instead of a normal bar this draws a
    little star-field. As the block gets closer to done, more stars
    light up and draw a line to the one before it -- like a
    constellation slowly completing. Nothing here is saved between
    redraws; it's worked out fresh from progress_fraction every time,
    so it naturally starts over blank on every new focus block.
    """
    progress_fraction = max(0.0, min(1.0, progress_fraction))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")

    r1, g1, b1 = _hex_to_rgb(primary)
    r2, g2, b2 = _hex_to_rgb(secondary)
    stars = _fourze_star_positions(width, height)
    lit_count = round(progress_fraction * _FOURZE_STAR_COUNT)

    line_color = (r2, g2, b2, 170)
    for i in range(1, lit_count):
        draw.line([stars[i - 1], stars[i]], fill=line_color, width=1)

    for index, (x, y) in enumerate(stars):
        lit = index < lit_count
        color = (r1, g1, b1, 235) if lit else (r1, g1, b1, 60)
        size = 3 if lit else 2
        draw.ellipse([x - size, y - size, x + size, y + size], fill=color)

    return image
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lock_in/visuals.py tests/test_visuals.py
git commit -m "feat: add Fourze constellation progress shape"
```

---

### Task 7: Build — vials progress

**Files:**
- Modify: `lock_in/visuals.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Produces: `render_vials_progress(width: int, height: int, progress_fraction: float, primary: str, secondary: str, dark: bool) -> Image.Image`.

- [ ] **Step 1: Write the failing tests**

```python
def test_vials_progress_returns_the_requested_size():
    from lock_in.visuals import render_vials_progress
    image = render_vials_progress(120, 60, 0.5, "#c62828", "#1565c0", dark=False)
    assert image.size == (120, 60)
    assert image.mode == "RGBA"


def test_vials_progress_fills_more_at_higher_progress():
    from lock_in.visuals import render_vials_progress
    from PIL import ImageStat

    def alpha_sum(image):
        return ImageStat.Stat(image.getchannel("A")).sum[0]

    low = render_vials_progress(120, 60, 0.1, "#c62828", "#1565c0", dark=False)
    high = render_vials_progress(120, 60, 0.6, "#c62828", "#1565c0", dark=False)
    assert alpha_sum(high) > alpha_sum(low)


def test_vials_progress_combines_near_completion():
    """Best Match: the two vials should visibly merge once nearly full,
    not just sit there as two separate bars forever."""
    from lock_in.visuals import render_vials_progress
    from PIL import ImageStat

    def alpha_sum(image):
        return ImageStat.Stat(image.getchannel("A")).sum[0]

    almost_full = render_vials_progress(120, 60, 0.94, "#c62828", "#1565c0", dark=False)
    combined = render_vials_progress(120, 60, 0.98, "#c62828", "#1565c0", dark=False)
    assert alpha_sum(combined) > alpha_sum(almost_full)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -k vials -v`
Expected: FAIL — `ImportError: cannot import name 'render_vials_progress'`

- [ ] **Step 3: Implement**

Add to `lock_in/visuals.py`:

```python
def render_vials_progress(
    width: int, height: int, progress_fraction: float,
    primary: str, secondary: str, dark: bool,
) -> Image.Image:
    """
    Build's whole gimmick is combining two Fullbottles. So this draws
    two vials, one per Rider color, that fill up together -- and once
    the block is basically done, a third mixed-color block appears
    between them, like the two bottles' contents just combined.
    """
    progress_fraction = max(0.0, min(1.0, progress_fraction))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")

    r1, g1, b1 = _hex_to_rgb(primary)
    r2, g2, b2 = _hex_to_rgb(secondary)
    vial_width = max(10, width // 6)
    gap = 8
    left1 = width // 2 - gap // 2 - vial_width
    left2 = width // 2 + gap // 2
    top, bottom = 2, height - 2

    outline = (255, 255, 255, 90) if dark else (0, 0, 0, 60)
    draw.rectangle([left1, top, left1 + vial_width, bottom], outline=outline, width=1)
    draw.rectangle([left2, top, left2 + vial_width, bottom], outline=outline, width=1)

    fill_height = round((bottom - top) * progress_fraction)
    if fill_height > 0:
        draw.rectangle(
            [left1, bottom - fill_height, left1 + vial_width, bottom], fill=(r1, g1, b1, 220),
        )
        draw.rectangle(
            [left2, bottom - fill_height, left2 + vial_width, bottom], fill=(r2, g2, b2, 220),
        )

    if progress_fraction >= 0.95:
        mixed = ((r1 + r2) // 2, (g1 + g2) // 2, (b1 + b2) // 2, 235)
        draw.rectangle([left1, top, left2 + vial_width, bottom], fill=mixed)

    return image
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lock_in/visuals.py tests/test_visuals.py
git commit -m "feat: add Build vials progress shape"
```

---

### Task 8: Drive — speed-lines progress

**Files:**
- Modify: `lock_in/visuals.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Produces: `render_speedlines_progress(width: int, height: int, progress_fraction: float, primary: str, secondary: str, dark: bool) -> Image.Image`.

- [ ] **Step 1: Write the failing tests**

```python
def test_speedlines_progress_returns_the_requested_size():
    from lock_in.visuals import render_speedlines_progress
    image = render_speedlines_progress(200, 60, 0.5, "#c62828", "#212121", dark=False)
    assert image.size == (200, 60)
    assert image.mode == "RGBA"


def test_speedlines_progress_adds_more_lines_at_higher_progress():
    from lock_in.visuals import render_speedlines_progress
    from PIL import ImageStat

    def alpha_sum(image):
        return ImageStat.Stat(image.getchannel("A")).sum[0]

    low = render_speedlines_progress(200, 60, 0.1, "#c62828", "#212121", dark=False)
    high = render_speedlines_progress(200, 60, 0.9, "#c62828", "#212121", dark=False)
    assert alpha_sum(high) > alpha_sum(low)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -k speedlines -v`
Expected: FAIL — `ImportError: cannot import name 'render_speedlines_progress'`

- [ ] **Step 3: Implement**

Add to `lock_in/visuals.py`:

```python
def render_speedlines_progress(
    width: int, height: int, progress_fraction: float,
    primary: str, secondary: str, dark: bool,
) -> Image.Image:
    """
    Drive is a racing/speed show, so instead of a normal bar this draws
    motion-blur speed-lines that multiply and stretch further across
    the picture as the block gets closer to done -- like picking up speed.
    """
    progress_fraction = max(0.0, min(1.0, progress_fraction))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")

    r1, g1, b1 = _hex_to_rgb(primary)
    max_lines = 10
    lit_lines = round(progress_fraction * max_lines)
    spacing = height / (max_lines + 1)

    for i in range(lit_lines):
        y = round(spacing * (i + 1))
        line_length = round(width * (0.3 + 0.7 * (i + 1) / max_lines))
        draw.line([(width - line_length, y), (width, y)], fill=(r1, g1, b1, 200), width=2)

    return image
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lock_in/visuals.py tests/test_visuals.py
git commit -m "feat: add Drive speed-lines progress shape"
```

---

### Task 9: Black — faceted progress

**Files:**
- Modify: `lock_in/visuals.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Produces: `render_faceted_progress(width: int, height: int, progress_fraction: float, primary: str, secondary: str, dark: bool) -> Image.Image`.

- [ ] **Step 1: Write the failing tests**

```python
def test_faceted_progress_returns_the_requested_size():
    from lock_in.visuals import render_faceted_progress
    image = render_faceted_progress(200, 40, 0.5, "#1a1a1a", "#00c853", dark=True)
    assert image.size == (200, 40)
    assert image.mode == "RGBA"


def test_faceted_progress_lights_more_segments_at_higher_progress():
    from lock_in.visuals import render_faceted_progress
    from PIL import ImageStat

    def alpha_sum(image):
        return ImageStat.Stat(image.getchannel("A")).sum[0]

    low = render_faceted_progress(200, 40, 0.1, "#1a1a1a", "#00c853", dark=True)
    high = render_faceted_progress(200, 40, 0.9, "#1a1a1a", "#00c853", dark=True)
    assert alpha_sum(high) > alpha_sum(low)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -k faceted -v`
Expected: FAIL — `ImportError: cannot import name 'render_faceted_progress'`

- [ ] **Step 3: Implement**

Add to `lock_in/visuals.py`:

```python
def render_faceted_progress(
    width: int, height: int, progress_fraction: float,
    primary: str, secondary: str, dark: bool,
) -> Image.Image:
    """
    Black's power comes from the Kingstone -- a literal cut gem. So
    instead of one smooth bar, this is a row of hard-edged faceted
    blocks that light up one at a time, like a strip of cut stone.
    """
    progress_fraction = max(0.0, min(1.0, progress_fraction))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")

    r1, g1, b1 = _hex_to_rgb(primary)
    r2, g2, b2 = _hex_to_rgb(secondary)
    dim_color = (r1, g1, b1, 45 if dark else 65)
    lit_color = (r2, g2, b2, 230)

    segment_count = 12
    gap = 3
    segment_width = (width - gap * (segment_count - 1)) / segment_count
    lit_segments = round(progress_fraction * segment_count)

    for i in range(segment_count):
        left = i * (segment_width + gap)
        color = lit_color if i < lit_segments else dim_color
        draw.polygon(
            [
                (left, height * 0.2),
                (left + segment_width * 0.7, 0),
                (left + segment_width, height * 0.2),
                (left + segment_width, height * 0.8),
                (left + segment_width * 0.3, height),
                (left, height * 0.8),
            ],
            fill=color,
        )

    return image
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lock_in/visuals.py tests/test_visuals.py
git commit -m "feat: add Black faceted progress shape"
```

---

### Task 10: `render_progress()` dispatcher

**Files:**
- Modify: `lock_in/visuals.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Consumes: every renderer from Tasks 3–9 (`render_flat_bar_progress`, `render_windmill_progress`, `render_rising_bar_progress`, `render_constellation_progress`, `render_vials_progress`, `render_speedlines_progress`, `render_faceted_progress`).
- Produces: `render_progress(effect: str, width: int, height: int, progress_fraction: float, primary: str, secondary: str, dark: bool, fill_color: str) -> Image.Image`. This is the only progress-drawing function `ui.py` will call (Task 12).

- [ ] **Step 1: Write the failing tests**

```python
def test_render_progress_routes_each_shape_effect_to_its_own_renderer():
    from lock_in import visuals

    routing = {
        "windmill": visuals.render_windmill_progress,
        "rising_bar": visuals.render_rising_bar_progress,
        "constellation": visuals.render_constellation_progress,
        "vials": visuals.render_vials_progress,
        "speedlines": visuals.render_speedlines_progress,
        "faceted": visuals.render_faceted_progress,
    }
    for effect, direct_renderer in routing.items():
        via_dispatch = visuals.render_progress(
            effect, 100, 40, 0.5, "#ff0000", "#00ff00", False, "#ff0000",
        )
        direct = direct_renderer(100, 40, 0.5, "#ff0000", "#00ff00", False)
        assert via_dispatch.tobytes() == direct.tobytes(), effect


def test_render_progress_falls_back_to_flat_bar_for_non_shape_effects():
    from lock_in import visuals

    for effect in ("none", "color_interpolation", "border_glow", "night_overlay"):
        via_dispatch = visuals.render_progress(
            effect, 100, 40, 0.5, "#ff0000", "#00ff00", False, "#ff0000",
        )
        flat = visuals.render_flat_bar_progress(100, 40, 0.5, "#ff0000", False)
        assert via_dispatch.tobytes() == flat.tobytes(), effect
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -k render_progress -v`
Expected: FAIL — `AttributeError: module 'lock_in.visuals' has no attribute 'render_progress'`

- [ ] **Step 3: Implement**

Add to `lock_in/visuals.py`:

```python
_SHAPE_RENDERERS = {
    "windmill": render_windmill_progress,
    "rising_bar": render_rising_bar_progress,
    "constellation": render_constellation_progress,
    "vials": render_vials_progress,
    "speedlines": render_speedlines_progress,
    "faceted": render_faceted_progress,
}


def render_progress(
    effect: str, width: int, height: int, progress_fraction: float,
    primary: str, secondary: str, dark: bool, fill_color: str,
) -> Image.Image:
    """
    Pick the right progress picture for this Rider. The 6 Riders with
    their own shape get that shape; everyone else (including Agito,
    Stronger, and Kiva -- their gimmicks live somewhere other than the
    progress bar's shape) gets today's plain bar.
    """
    renderer = _SHAPE_RENDERERS.get(effect)
    if renderer is not None:
        return renderer(width, height, progress_fraction, primary, secondary, dark)
    return render_flat_bar_progress(width, height, progress_fraction, fill_color, dark)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS — full file.

- [ ] **Step 5: Commit**

```bash
git add lock_in/visuals.py tests/test_visuals.py
git commit -m "feat: add render_progress dispatcher for the 9 Tier 1 Riders"
```

---

### Task 11: Stronger's border glow and Kiva's night overlay

**Files:**
- Modify: `lock_in/visuals.py`
- Test: `tests/test_visuals.py`

**Interfaces:**
- Produces: `render_border_glow_overlay(base_image: Image.Image, color: str, intensity_fraction: float) -> Image.Image`, `render_night_overlay(base_image: Image.Image, color: str, alpha: int = 70) -> Image.Image`, `apply_tier1_background_effect(base_image: Image.Image, effect: str, color: str, intensity_fraction: float = 0.0) -> Image.Image` (this last one is what `ui.py` will call in Task 12).

- [ ] **Step 1: Write the failing tests**

```python
def test_border_glow_overlay_returns_same_size_as_base():
    from lock_in.visuals import render_border_glow_overlay
    from PIL import Image
    base = Image.new("RGB", (100, 150), (20, 20, 20))
    result = render_border_glow_overlay(base, "#c62828", 0.5)
    assert result.size == (100, 150)
    assert result.mode == "RGBA"


def test_border_glow_overlay_is_stronger_at_higher_intensity():
    from lock_in.visuals import render_border_glow_overlay
    from PIL import Image, ImageChops, ImageStat

    def difference_from_base(base, glowed):
        diff = ImageChops.difference(base.convert("RGB"), glowed.convert("RGB"))
        return ImageStat.Stat(diff).sum[0]

    base = Image.new("RGB", (100, 150), (20, 20, 20))
    faint = render_border_glow_overlay(base, "#c62828", 0.2)
    strong = render_border_glow_overlay(base, "#c62828", 0.9)
    assert difference_from_base(base, strong) > difference_from_base(base, faint)


def test_border_glow_overlay_only_touches_the_edges():
    """The whole point is a BORDER glow -- the dead center of a big
    picture should come back basically untouched."""
    from lock_in.visuals import render_border_glow_overlay
    from PIL import Image
    base = Image.new("RGB", (200, 200), (20, 20, 20))
    glowed = render_border_glow_overlay(base, "#c62828", 1.0)
    center = glowed.getpixel((100, 100))
    assert center[:3] == (20, 20, 20)


def test_night_overlay_tints_toward_the_given_color():
    from lock_in.visuals import render_night_overlay
    from PIL import Image
    base = Image.new("RGB", (50, 50), (10, 10, 10))
    washed = render_night_overlay(base, "#ffca28", alpha=255)
    # A full-strength wash should completely replace the base color.
    assert washed.getpixel((25, 25))[:3] == (255, 202, 40)


def test_night_overlay_returns_same_size_as_base():
    from lock_in.visuals import render_night_overlay
    from PIL import Image
    base = Image.new("RGB", (60, 90), (10, 10, 10))
    result = render_night_overlay(base, "#ffca28")
    assert result.size == (60, 90)
    assert result.mode == "RGBA"


def test_apply_tier1_background_effect_routes_correctly():
    from lock_in import visuals
    from PIL import Image
    base = Image.new("RGB", (100, 100), (20, 20, 20))

    glow = visuals.apply_tier1_background_effect(base, "border_glow", "#c62828", 0.8)
    direct_glow = visuals.render_border_glow_overlay(base, "#c62828", 0.8)
    assert glow.tobytes() == direct_glow.tobytes()

    wash = visuals.apply_tier1_background_effect(base, "night_overlay", "#ffca28")
    direct_wash = visuals.render_night_overlay(base, "#ffca28")
    assert wash.tobytes() == direct_wash.tobytes()


def test_apply_tier1_background_effect_none_returns_base_unchanged():
    from lock_in import visuals
    from PIL import Image
    base = Image.new("RGB", (100, 100), (20, 20, 20))
    result = visuals.apply_tier1_background_effect(base, "none", "#c62828")
    assert result.tobytes() == base.convert("RGBA").tobytes()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -k "border_glow or night_overlay or apply_tier1" -v`
Expected: FAIL — `ImportError`/`AttributeError` for the three missing functions.

- [ ] **Step 3: Implement**

Add to `lock_in/visuals.py`:

```python
def render_border_glow_overlay(
    base_image: Image.Image, color: str, intensity_fraction: float,
) -> Image.Image:
    """
    Paint a soft glow around the edge of `base_image`, like Stronger
    charging up his own electricity -- it widens and brightens as
    `intensity_fraction` climbs from 0 (just started) to 1 (about to
    finish).

    This only ever draws a handful of rectangle OUTLINES near the
    edges, never looks at individual pixels in Python -- that's what
    keeps it fast enough to redraw many times a second, even though
    the background picture itself is fairly big.
    """
    intensity_fraction = max(0.0, min(1.0, intensity_fraction))
    width, height = base_image.size
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    r, g, b = _hex_to_rgb(color)

    max_bands = 14
    band_count = max(1, round(max_bands * intensity_fraction))
    max_alpha = 140

    for i in range(band_count):
        inset = i * 2
        alpha = round(max_alpha * (1 - i / max_bands))
        box = [inset, inset, width - 1 - inset, height - 1 - inset]
        if box[0] >= box[2] or box[1] >= box[3]:
            break
        draw.rectangle(box, outline=(r, g, b, alpha))

    return Image.alpha_composite(base_image.convert("RGBA"), overlay)


def render_night_overlay(base_image: Image.Image, color: str, alpha: int = 70) -> Image.Image:
    """
    Wash the whole picture in a translucent color, like Kiva's story
    always happening at night. `alpha` is how strong the tint is (0 is
    invisible, 255 is a solid block of color) -- kept low by default so
    the picture underneath still shows through clearly.
    """
    width, height = base_image.size
    r, g, b = _hex_to_rgb(color)
    wash = Image.new("RGBA", (width, height), (r, g, b, alpha))
    return Image.alpha_composite(base_image.convert("RGBA"), wash)


def apply_tier1_background_effect(
    base_image: Image.Image, effect: str, color: str, intensity_fraction: float = 0.0,
) -> Image.Image:
    """
    The one place that decides whether the background picture needs
    Stronger's border glow, Kiva's night wash, or nothing extra at all.
    Always hands back ONE flat picture -- ui.py never has to stack a
    second see-through picture on top to get this look (Tkinter can't
    blend two overlapping see-through pictures correctly, so all of
    that math happens here instead, before it ever reaches a widget).
    """
    if effect == "border_glow":
        return render_border_glow_overlay(base_image, color, intensity_fraction)
    if effect == "night_overlay":
        return render_night_overlay(base_image, color)
    return base_image.convert("RGBA")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS — full file.

- [ ] **Step 5: Commit**

```bash
git add lock_in/visuals.py tests/test_visuals.py
git commit -m "feat: add Stronger border glow and Kiva night overlay background effects"
```

---

### Task 12: `ui.py` — background effect wiring (Stronger, Kiva)

**Files:**
- Modify: `lock_in/ui.py`

**Interfaces:**
- Consumes: `visuals.apply_tier1_background_effect` (Task 11), `RiderTheme.tier1_effect` (Task 1).
- Produces: `self.current_tier1_effect: str`, `self.rider_primary: str`, `self.rider_secondary: str`, `self.color_tier1_effect: str`, `self._base_bg_light`/`self._base_bg_dark: Image.Image`, `self._refresh_background_effect(progress_fraction: float) -> None` — all used by Task 13.

- [ ] **Step 1: Reorder `__init__` so `self.session` exists before `_apply_rider_theme()` runs**

The background-effect wiring needs to check `self.session.phase`, but today `_apply_rider_theme()` (called at startup) runs *before* `self.session` is created. `PomodoroSession` only needs `self.config_obj`, which is already loaded one line earlier — so this reorder is safe.

In `lock_in/ui.py`, change (around line 104-110):

```python
        # ---------------- The main pieces of the app -------------------- #
        self.config_obj = Config.load()
        self._apply_rider_theme()
        self.model = NaiveBayesClassifier.load(MODEL_PATH)
        self.observations = ObservationStore(OBSERVATIONS_PATH)
        self.claude = ClaudeFallback(self.config_obj)
        self.session = PomodoroSession(self.config_obj)
```

to:

```python
        # ---------------- The main pieces of the app -------------------- #
        self.config_obj = Config.load()
        # The session has to exist BEFORE _apply_rider_theme(), because
        # that method now also has to check what phase we're in (for
        # Stronger/Kiva's background effect).
        self.session = PomodoroSession(self.config_obj)
        self._apply_rider_theme()
        self.model = NaiveBayesClassifier.load(MODEL_PATH)
        self.observations = ObservationStore(OBSERVATIONS_PATH)
        self.claude = ClaudeFallback(self.config_obj)
```

- [ ] **Step 2: Add the new imports**

Change the `from .visuals import (...)` block in `lock_in/ui.py` to:

```python
from .visuals import (
    apply_tier1_background_effect,
    display_font_family,
    load_app_icon,
    make_background_texture,
    make_glow,
    make_panel_divider,
)
```

- [ ] **Step 3: Store the new per-Rider state and add `_refresh_background_effect`**

In `_apply_rider_theme()`, right after the line `self.current_era = theme.era` (around line 258), add:

```python
        self.current_tier1_effect = theme.tier1_effect
        self.rider_primary = theme.primary
        self.rider_secondary = theme.secondary
        # Stronger's glow uses the Rider's own primary (already a red);
        # Kiva's night wash uses the secondary (the amber gold). Every
        # other Rider never reads this, so the value doesn't matter for them.
        self.color_tier1_effect = (
            theme.primary if theme.tier1_effect == "border_glow" else theme.secondary
        )
```

Then, right after the block that builds `bg_dark`/`bg_light` (the `make_background_texture(...)` calls, around lines 262-269), rename their use so we keep the *plain* texture around for later, and add the new helper method. Replace:

```python
        bg_dark = make_background_texture(
            BG_TEXTURE_WIDTH, BG_TEXTURE_HEIGHT, theme.primary, theme.secondary,
            dark=True, era=theme.era,
        )
        bg_light = make_background_texture(
            BG_TEXTURE_WIDTH, BG_TEXTURE_HEIGHT, theme.primary, theme.secondary,
            dark=False, era=theme.era,
        )
```

with:

```python
        bg_dark = make_background_texture(
            BG_TEXTURE_WIDTH, BG_TEXTURE_HEIGHT, theme.primary, theme.secondary,
            dark=True, era=theme.era,
        )
        bg_light = make_background_texture(
            BG_TEXTURE_WIDTH, BG_TEXTURE_HEIGHT, theme.primary, theme.secondary,
            dark=False, era=theme.era,
        )
        # Keep the PLAIN pattern around separately from the picture that
        # actually ends up on screen -- Stronger/Kiva's effect gets
        # painted fresh on top of this every tick, so we always need
        # the untouched original to start from, not last tick's result.
        self._base_bg_dark = bg_dark
        self._base_bg_light = bg_light
```

Then, at the very end of `_apply_rider_theme()` (after the existing `if hasattr(self, "_timer_glow_image"): ... else: ...` block that builds `self._bg_image`), add:

```python

        self._refresh_background_effect(self.session.progress)

    def _refresh_background_effect(self, progress_fraction: float) -> None:
        """
        Redraw the background picture's Stronger-glow or Kiva-wash (if
        this Rider has one) and push it onto the picture already on
        screen. Riders without either effect never call this with
        anything to actually draw, so nothing changes for them.

        Both effects only show up DURING a focus block, and disappear
        the moment it ends -- that's what `in_focus` is for.
        """
        in_focus = self.session.phase is Phase.FOCUS
        active_effect = self.current_tier1_effect if in_focus else "none"
        bg_light = apply_tier1_background_effect(
            self._base_bg_light, active_effect, self.color_tier1_effect, progress_fraction,
        )
        bg_dark = apply_tier1_background_effect(
            self._base_bg_dark, active_effect, self.color_tier1_effect, progress_fraction,
        )
        self._bg_image.configure(light_image=bg_light, dark_image=bg_dark)
```

- [ ] **Step 4: Run the existing test suite to make sure nothing broke**

Run: `pytest -q`
Expected: PASS — this task only adds new state and a new method; it doesn't change any existing tested behavior. (There's no dedicated test file for `ui.py`'s GUI wiring — see the spec's Testing section — so this step is a regression check, not new coverage.)

- [ ] **Step 5: Commit**

```bash
git add lock_in/ui.py
git commit -m "feat: wire Stronger/Kiva background effects into ui.py"
```

---

### Task 13: `ui.py` — progress widget becomes a single picture

**Files:**
- Modify: `lock_in/ui.py`

**Interfaces:**
- Consumes: `visuals.render_progress`, `visuals.interpolate_agito_color` (Tasks 2, 10), `self.current_tier1_effect`/`self.rider_primary`/`self.rider_secondary` (Task 12).
- Produces: `self.progress: ctk.CTkLabel` (replaces the old `ctk.CTkProgressBar`), `self._refresh_progress_image(fill_color) -> None`.

- [ ] **Step 1: Add the new imports and size constants**

Change the `from .visuals import (...)` block again (building on Task 12's edit) to also pull in the two new functions:

```python
from .visuals import (
    apply_tier1_background_effect,
    display_font_family,
    interpolate_agito_color,
    load_app_icon,
    make_background_texture,
    make_glow,
    make_panel_divider,
    render_progress,
)
```

Add two new constants next to `BG_TEXTURE_WIDTH`/`BG_TEXTURE_HEIGHT` (around line 86-92):

```python
# The progress picture's fixed size. Unlike the background wallpaper
# and the divider strip, this one does NOT stretch when you resize the
# window -- it just stays centered at this size, which is simple and
# looks fine since the timer panel itself has a sensible minimum width.
PROGRESS_IMAGE_WIDTH = 340
PROGRESS_IMAGE_HEIGHT = 48
```

- [ ] **Step 2: Replace the `CTkProgressBar` with a picture-based `CTkLabel`**

Change (around line 388-390):

```python
        self.progress = ctk.CTkProgressBar(header, height=8, corner_radius=4)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(12, 14))
```

to:

```python
        # This used to be a plain CTkProgressBar. Now it's a picture --
        # every Rider's progress bar (custom shapes and all) is drawn by
        # visuals.render_progress() and swapped in here, so this one
        # widget works for all 38 Riders instead of needing two
        # different widgets kept in sync.
        self.progress = ctk.CTkLabel(header, text="", image=None)
        self.progress.pack(fill="x", pady=(12, 14))
```

- [ ] **Step 3: Add `_refresh_progress_image` and rewire `_refresh_timer_widgets`**

In `_refresh_timer_widgets()` (around lines 1261-1289), change:

```python
        self.time_label.configure(text=self.session.format_remaining())
        self.progress.set(self.session.progress)

        # The progress bar's fill uses the plain, vivid Rider color -- but
        # the WORDS use the separate, always-readable version instead,
        # since a word-colored-exactly-like-its-own-background is a word
        # nobody can read (this is exactly the bug some Riders, like
        # Fourze's pure white, used to have).
        fill_color = {
            Phase.FOCUS: self.color_focus,
            Phase.SHORT_BREAK: COLOR_BREAK,
            Phase.LONG_BREAK: COLOR_BREAK,
            Phase.IDLE: COLOR_IDLE,
        }[phase]
        text_color = {
            Phase.FOCUS: self.color_focus_text,
            Phase.SHORT_BREAK: COLOR_BREAK,
            Phase.LONG_BREAK: COLOR_BREAK,
            Phase.IDLE: COLOR_IDLE,
        }[phase]

        suffix = " (paused)" if self.session.is_paused and phase is not Phase.IDLE else ""
        self.phase_label.configure(text=label + suffix, text_color=text_color)
        self.time_label.configure(text_color=text_color)
        self.progress.configure(progress_color=fill_color)
```

to:

```python
        self.time_label.configure(text=self.session.format_remaining())

        # The progress bar's fill uses the plain, vivid Rider color -- but
        # the WORDS use the separate, always-readable version instead,
        # since a word-colored-exactly-like-its-own-background is a word
        # nobody can read (this is exactly the bug some Riders, like
        # Fourze's pure white, used to have).
        fill_color = {
            Phase.FOCUS: self.color_focus,
            Phase.SHORT_BREAK: COLOR_BREAK,
            Phase.LONG_BREAK: COLOR_BREAK,
            Phase.IDLE: COLOR_IDLE,
        }[phase]
        text_color = {
            Phase.FOCUS: self.color_focus_text,
            Phase.SHORT_BREAK: COLOR_BREAK,
            Phase.LONG_BREAK: COLOR_BREAK,
            Phase.IDLE: COLOR_IDLE,
        }[phase]

        # Agito's whole gimmick is that its color wakes up over the
        # block instead of staying still -- swap in that shifting color
        # ONLY during a focus block, so break/idle still look normal.
        if phase is Phase.FOCUS and self.current_tier1_effect == "color_interpolation":
            interpolated = interpolate_agito_color(self.session.progress, self.rider_primary)
            fill_color = (interpolated, interpolated)

        suffix = " (paused)" if self.session.is_paused and phase is not Phase.IDLE else ""
        self.phase_label.configure(text=label + suffix, text_color=text_color)
        self.time_label.configure(text_color=text_color)
        self._refresh_progress_image(fill_color)

        if self.current_tier1_effect in ("border_glow", "night_overlay"):
            self._refresh_background_effect(self.session.progress)
```

Then add the new helper method right after `_refresh_timer_widgets()` (or anywhere in the "Helpers that redraw parts of the screen" section):

```python
    def _refresh_progress_image(self, fill_color) -> None:
        """
        Redraw the progress picture (whatever shape this Rider uses) and
        push it onto the label already on screen. `fill_color` can be
        either one plain color, or a (light-mode, dark-mode) pair, same
        as every other color in this file -- either way we render BOTH
        a light-mode and a dark-mode picture, same trick already used
        for the background wallpaper below.
        """
        light_fill = fill_color[0] if isinstance(fill_color, tuple) else fill_color
        dark_fill = fill_color[1] if isinstance(fill_color, tuple) else fill_color

        light_image = render_progress(
            self.current_tier1_effect, PROGRESS_IMAGE_WIDTH, PROGRESS_IMAGE_HEIGHT,
            self.session.progress, self.rider_primary, self.rider_secondary, False, light_fill,
        )
        dark_image = render_progress(
            self.current_tier1_effect, PROGRESS_IMAGE_WIDTH, PROGRESS_IMAGE_HEIGHT,
            self.session.progress, self.rider_primary, self.rider_secondary, True, dark_fill,
        )

        if hasattr(self, "_progress_image"):
            self._progress_image.configure(light_image=light_image, dark_image=dark_image)
        else:
            self._progress_image = ctk.CTkImage(
                light_image=light_image, dark_image=dark_image,
                size=(PROGRESS_IMAGE_WIDTH, PROGRESS_IMAGE_HEIGHT),
            )
            self.progress.configure(image=self._progress_image)
```

- [ ] **Step 4: Run the existing test suite to make sure nothing broke**

Run: `pytest -q`
Expected: PASS. Also confirm no test references `app.progress.set(...)` or `app.progress.cget("progress_color")` anywhere (checked already — there are none in `tests/`), so this widget-type change is safe.

- [ ] **Step 5: Commit**

```bash
git add lock_in/ui.py
git commit -m "feat: render the progress bar as a picture for all 38 Riders"
```

---

### Task 14: Manual screenshot verification

**Files:**
- Create (scratch, not committed): a throwaway verification script, same pattern as prior rounds' `verify_contrast_fix.py`.

- [ ] **Step 1: Write a verification script**

Create `verify_tier1.py` in your scratch/temp directory (NOT inside the repo):

```python
import sys, time
sys.path.insert(0, r"c:\Users\saksh\OneDrive\Desktop\Coding_Projects\Lock_In")

import customtkinter as ctk
import lock_in.ui as ui
from lock_in.session import Event
from PIL import ImageGrab

RIDERS_TO_CHECK = [
    "Kamen Rider (1971)", "Kamen Rider Skyrider (1979)", "Kamen Rider Stronger (1975)",
    "Kamen Rider Black (1987)", "Kamen Rider Fourze (2011)", "Kamen Rider Build (2017)",
    "Kamen Rider Drive (2014)", "Kamen Rider Agito (2001)", "Kamen Rider Kiva (2008)",
    "Kamen Rider V3 (1973)",  # control: NOT a Tier 1 Rider, must look like today
]

app = ui.LockInApp()
app.update()
app.geometry("560x520+40+40")

for rider in RIDERS_TO_CHECK:
    app.config_obj.rider_theme = rider
    app._on_rider_theme_change(rider)
    app.update()

    for event in app.session.start():
        if event is Event.PHASE_STARTED:
            app._on_phase_started()
    # Fast-forward partway through the block so shapes/effects that
    # depend on progress actually show something other than 0%.
    for _ in range(400):
        app.session.tick()
    app._refresh_timer_widgets()
    app.update()

    app.attributes("-topmost", True)
    app.lift()
    app.focus_force()
    for _ in range(8):
        app.update()
        time.sleep(0.05)

    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    safe_name = rider.replace(" ", "_").replace("(", "").replace(")", "")
    img.save(rf"C:\Users\saksh\AppData\Local\Temp\claude\tier1_{safe_name}.png")
    print("saved:", rider)

    app.session.reset()

app._on_close()
```

- [ ] **Step 2: Run it and look at each screenshot**

Run: `python verify_tier1.py` (from your scratchpad directory, with the app's venv active)

For each of the 9 Tier 1 Riders, confirm: the progress area shows that Rider's specific shape/effect (windmill wedges, rising bar, faceted blocks, star-field, vials, speed-lines, Agito's shifted gold, Stronger's edge glow, Kiva's amber wash) and nothing looks broken, cut off, or invisible against its background. For the control Rider (V3), confirm the progress bar still looks like today's plain bar — proof the other 29 Riders are unaffected.

- [ ] **Step 3: Fix anything that looks wrong**

If a shape is too small/cramped inside `PROGRESS_IMAGE_HEIGHT = 48`, or a color is hard to see against that Rider's `surface_pair`, go back to the specific Task (4-11) for that Rider/effect and adjust the drawing code — re-run that task's automated tests afterward to make sure the fix didn't break them.

- [ ] **Step 4: Delete the scratch script and screenshots**

They're verification-only, not part of the app — don't commit them.

---

### Task 15: Docs and version

**Files:**
- Modify: `README.md`
- Modify: `.gitignore` (only if Task 14 needs a new generated-file pattern — check first, don't add speculatively)
- Modify: `lock_in/__init__.py`

- [ ] **Step 1: Update the README's Kamen Rider theme section**

In `README.md`, under `## Kamen Rider theme`, add one short paragraph after the existing era table (find the line starting "In Professional wording, the Voice column above doesn't apply..."):

```markdown
Nine Riders also get their own **progress bar treatment** during a
focus block, on top of the era/color system above: Kamen Rider (1971,
a windmill), Skyrider (a rising bar), Stronger (a border glow that
builds as the block goes on), Black (faceted blocks), Fourze (a
completing constellation), Build (two vials that combine near the
end), Drive (speed-lines), Agito (a color that "wakes up" over the
block), and Kiva (a translucent night-time wash over the whole app).
Every other Rider keeps the plain bar. See
`docs/superpowers/specs/2026-08-10-tier1-rider-progress-variants-design.md`
for the full design.
```

- [ ] **Step 2: Check `.gitignore`**

This feature doesn't introduce any new generated file type in the repo itself (the verification script and screenshots from Task 14 live outside the repo, in your temp/scratch directory) — confirm no edit is actually needed rather than adding one speculatively.

- [ ] **Step 3: Bump the version**

In `lock_in/__init__.py`, change:

```python
__version__ = "1.3.1"
```

to:

```python
__version__ = "2.0.0"
```

This is the version bump the whole 38-Rider project's Tier 1 slice earns — it's the first tier to actually ship code, matching the user's own "v2.0.0" label for this round.

- [ ] **Step 4: Run the full test suite one final time, in both environments**

Run: `venv\Scripts\python.exe -m pytest -q` and `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS in both — full suite, no failures, no skips.

- [ ] **Step 5: Commit**

```bash
git add README.md lock_in/__init__.py
git commit -m "docs: document Tier 1 Rider progress variants, bump to v2.0.0"
```

---

## Self-Review Notes

- **Spec coverage:** all 9 Riders (Tasks 4-11), the `tier1_effect` field (Task 1), the "no widget layering, all compositing in Pillow" constraint (Tasks 11-13, `apply_tier1_background_effect` + `render_progress` are both the single source of truth for their widget), in-memory-only state with no persistence (Task 6's constellation math needs no stored state at all — simpler than the spec even called for, still satisfies "resets on restart" since it's derived fresh from `progress_fraction` every time), testing approach (pure-function tests for every renderer, screenshot-only for the final `ui.py` wiring) are all covered.
- **Placeholder scan:** no TBD/TODO; every step has real, runnable code.
- **Type consistency:** `render_progress`'s signature (Task 10) matches every call site in Task 13; `apply_tier1_background_effect`'s signature (Task 11) matches its call sites in Task 12; `RiderTheme.tier1_effect` (Task 1) is read the same way (`theme.tier1_effect`) everywhere it's used.
- **One deviation worth flagging to the user directly (not just buried here):** the progress indicator changes from a native, width-stretching `CTkProgressBar` to a fixed-size picture (`PROGRESS_IMAGE_WIDTH = 340`) for ALL 38 Riders, not just the 9 in Tier 1. This was necessary to avoid a Tkinter widget-stacking/pack-ordering bug that a two-widget toggle approach would have hit, and it keeps `ui.py` simple (one widget, one dispatcher call) — but it means the progress bar no longer stretches to fill the window on resize, which is a small, real, visible behavior change from today.
