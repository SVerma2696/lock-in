"""
visuals.py
==========
This file makes the pretty pictures: a soft glow behind the timer and the
Henshin button, a faint patterned picture behind the whole window, and
the app's own picture (used for the window icon and for notifications).
It also picks a nicer-looking font name for whatever computer you're on.

This file doesn't know anything about timers, Kamen Riders, or buttons —
it just makes pictures when asked. `ui.py` is the one that asks for a
picture and decides where to put it on the screen.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from .rider_themes import darken

# Where the app's own picture lives, and where its title-bar/notification
# icon comes from.
ASSETS_DIR = Path(__file__).parent / "assets"
APP_ICON_PATH = ASSETS_DIR / "app_icon.png"


def display_font_family() -> str:
    """
    Pick a nicer-looking font name for the timer digits and headings.

    Every kind of computer already comes with different fonts built in.
    We pick a good, modern-looking one for whichever kind of computer
    this is. If that font isn't actually there for some reason, the
    computer just quietly uses its own normal font instead — nothing
    breaks.
    """
    if sys.platform == "win32":
        return "Bahnschrift"
    if sys.platform == "darwin":
        return "Avenir Next"
    return "Noto Sans"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def make_glow(width: int, height: int, color: str, strength: float = 180) -> Image.Image:
    """
    Make a soft, see-through blob of color — like a glow-stick sitting
    behind something.

    It's brightest right in the middle, and fades out to fully
    see-through by the time you reach the edge of the picture, so it
    looks like a soft round light with no hard edges, not a glowing
    rectangle.
    """
    r, g, b = _hex_to_rgb(color)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = image.load()
    cx, cy = width / 2, height / 2

    for y in range(height):
        for x in range(width):
            # This measures distance as a fraction of the picture's own
            # half-width and half-height, so it reaches exactly 1.0 (and
            # the glow fully disappears) right at the edge, in every
            # direction — not just at the far corners.
            dx = (x - cx) / cx
            dy = (y - cy) / cy
            dist = (dx ** 2 + dy ** 2) ** 0.5
            closeness = max(0.0, 1.0 - dist)
            # Raised to the 4th power (instead of squared) so the fade-out
            # happens fast near the edge — that keeps even the very last
            # sliver of color too faint to notice, instead of leaving a
            # barely-visible rectangle where the picture ends.
            alpha = int(strength * (closeness ** 4))
            pixels[x, y] = (r, g, b, alpha)

    return image


def make_background_texture(
    width: int, height: int, primary: str, secondary: str, dark: bool,
    era: str = "Heisei",
) -> Image.Image:
    """
    Make a faint, wallpaper-like picture in the Rider's two colors.

    The SHAPE of the pattern depends on which Kamen Rider era this is —
    picking a different era of Rider doesn't just swap colors, it also
    changes the pattern:
      Showa  — thin scanlines and grain, like old analog TV footage.
      Heisei — a grid of diamond facets, like a cut gem.
      Reiwa  — a circuit-board grid of lines and dots, digital-looking.

    Whatever the shape, it has to stay faint and low-key — like
    wallpaper, not a poster — or it would make the words sitting on top
    of it hard to read. That's why every color here gets a very low
    alpha (see-through-ness) number.
    """
    r1, g1, b1 = _hex_to_rgb(primary)
    r2, g2, b2 = _hex_to_rgb(secondary)
    base = (17, 19, 23) if dark else (245, 246, 248)
    stripe_alpha = 20 if dark else 12
    colors = [(r1, g1, b1, stripe_alpha), (r2, g2, b2, stripe_alpha)]

    image = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(image, "RGBA")

    if era == "Showa":
        _draw_scanline_pattern(draw, width, height, colors)
    elif era == "Reiwa":
        _draw_circuit_pattern(draw, width, height, colors)
    else:
        _draw_facet_pattern(draw, width, height, colors)

    return image


def _draw_scanline_pattern(draw: ImageDraw.ImageDraw, width: int, height: int, colors) -> None:
    """
    Showa: thin horizontal lines like an old analog TV or film reel,
    plus a light sprinkle of grain specks — the scratchy, well-worn
    look old tokusatsu footage actually has.
    """
    for y in range(0, height, 4):
        draw.line([(0, y), (width, y)], fill=colors[(y // 4) % 2], width=1)

    # A fixed seed keeps the "random" grain looking the same every time
    # we draw it, instead of flickering to a new pattern on every redraw.
    rng = random.Random(1971)
    speck_r, speck_g, speck_b, speck_a = colors[0]
    for _ in range((width * height) // 900):
        x = rng.randrange(width)
        y = rng.randrange(height)
        draw.point((x, y), fill=(speck_r, speck_g, speck_b, speck_a * 3))


def _draw_facet_pattern(draw: ImageDraw.ImageDraw, width: int, height: int, colors) -> None:
    """
    Heisei: a grid of diamond facets, like looking down at a cut gem —
    matches the gem/jewel look a lot of Heisei-era Rider gear actually
    has (Kuuga's Amadam, Wizard's rings, Zi-O's Ridewatches).
    """
    size = 70
    for row, y in enumerate(range(-size, height + size, size)):
        offset = size // 2 if row % 2 else 0
        for col, x in enumerate(range(-size, width + size, size)):
            cx, cy = x + offset, y
            draw.polygon(
                [
                    (cx, cy - size // 2),
                    (cx + size // 2, cy),
                    (cx, cy + size // 2),
                    (cx - size // 2, cy),
                ],
                fill=colors[(row + col) % 2],
            )


def _draw_circuit_pattern(draw: ImageDraw.ImageDraw, width: int, height: int, colors) -> None:
    """
    Reiwa: a grid of thin lines with little dots at each crossing, like
    traces on a circuit board — matches the digital/AI theme a lot of
    Reiwa-era Riders have (Zero-One's AI partner, Geats' game system).
    """
    step = 60
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=colors[0], width=1)
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=colors[1], width=1)
    for x in range(0, width, step):
        for y in range(0, height, step):
            color = colors[((x // step) + (y // step)) % 2]
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=color)


def make_panel_divider(
    width: int, height: int, primary: str, secondary: str, era: str = "Heisei",
) -> Image.Image:
    """
    Make a thin, good-looking strip for the small gap between two
    panels (like the timer panel and the tab panel sitting under it).

    The background wallpaper's patterns (diamonds, circuit lines,
    scanlines) are too big to actually show up in a strip this thin —
    they'd just look like a flat color. This picture uses a smaller
    version of each era's own look instead, so the thin gap still has
    its own Kamen Rider era personality instead of going plain.

    Unlike the wallpaper, this is meant to be seen clearly, not to stay
    faint in the background — so its colors are much less see-through.
    """
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    r1, g1, b1 = _hex_to_rgb(primary)
    r2, g2, b2 = _hex_to_rgb(secondary)
    colors = [(r1, g1, b1, 210), (r2, g2, b2, 210)]

    if era == "Showa":
        _draw_tick_divider(draw, width, height, colors)
    elif era == "Reiwa":
        _draw_circuit_divider(draw, width, height, colors)
    else:
        _draw_facet_divider(draw, width, height, colors)

    return image


def _draw_tick_divider(draw: ImageDraw.ImageDraw, width: int, height: int, colors) -> None:
    """Showa: short tick marks along a thin line, like an old gauge or a ruler."""
    mid = height // 2
    draw.line([(0, mid), (width, mid)], fill=colors[0], width=1)
    step = 18
    for i, x in enumerate(range(0, width, step)):
        draw.line([(x, mid - 4), (x, mid + 4)], fill=colors[i % 2], width=2)


def _draw_facet_divider(draw: ImageDraw.ImageDraw, width: int, height: int, colors) -> None:
    """Heisei: a row of tiny diamonds, like a thin strip of jeweled trim."""
    size = max(4, height - 2)
    step = size + 8
    for i, x in enumerate(range(0, width, step)):
        cx, cy = x + size // 2, height // 2
        draw.polygon(
            [
                (cx, cy - size // 2),
                (cx + size // 2, cy),
                (cx, cy + size // 2),
                (cx - size // 2, cy),
            ],
            fill=colors[i % 2],
        )


def _draw_circuit_divider(draw: ImageDraw.ImageDraw, width: int, height: int, colors) -> None:
    """Reiwa: a dashed line with little square nodes, like a circuit-board trace."""
    mid = height // 2
    dash, gap = 10, 6
    x = 0
    i = 0
    while x < width:
        draw.line([(x, mid), (min(x + dash, width), mid)], fill=colors[i % 2], width=2)
        x += dash + gap
        i += 1

    node_step = 40
    for i, x in enumerate(range(0, width, node_step)):
        draw.rectangle([x - 3, mid - 3, x + 3, mid + 3], fill=colors[(i + 1) % 2])


def load_app_icon() -> Optional[Image.Image]:
    """
    Load the app's own picture, padded onto a square, see-through canvas.

    Windows and other computers want a SQUARE picture for a title-bar or
    notification icon. Our picture is tall and thin, not square — if we
    squeezed it to fit, it would look squashed. Instead, we place it in
    the middle of a bigger square that's just see-through everywhere
    else, so the picture keeps its real shape.

    Gives back `None` if the picture is missing or broken, so a missing
    file can never crash the app — the window/notifications just won't
    have a custom picture that one time.
    """
    try:
        image = Image.open(APP_ICON_PATH).convert("RGBA")
    except Exception:
        return None

    side = max(image.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    left = (side - image.width) // 2
    top = (side - image.height) // 2
    square.paste(image, (left, top), image)
    return square


# ===================================================================== #
# Tier 1: per-Rider progress bar variants
# See docs/superpowers/specs/2026-08-10-tier1-rider-progress-variants-design.md
# Only 9 specific Riders use anything in this section -- everybody else
# keeps the plain native progress bar ui.py already had.
# ===================================================================== #

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


def ease_drive_progress(progress_fraction: float) -> float:
    """
    Drive's whole gimmick is shifting gears to go faster. So instead of
    the progress bar filling at a steady rate, it reads this through an
    easing curve first: it looks like it's lagging behind early on,
    then visibly speeds up and catches back up right near the end --
    like shifting into top gear. It still reaches exactly 0 and exactly
    1 at the very start and very end, same as real progress.
    """
    progress_fraction = max(0.0, min(1.0, progress_fraction))
    return progress_fraction ** 2


_SHAPE_RENDERERS = {
    "windmill": render_windmill_progress,
    "rising_bar": render_rising_bar_progress,
    "constellation": render_constellation_progress,
    "vials": render_vials_progress,
}

# The only 6 tier1_effect values that need a picture instead of the
# plain native progress bar. ui.py checks a Rider's effect against this
# set to decide whether to show its picture widget at all -- kept here,
# next to the dict it's built from, so the two can never drift apart.
SHAPE_EFFECTS = frozenset(_SHAPE_RENDERERS)


def render_progress(
    effect: str, width: int, height: int, progress_fraction: float,
    primary: str, secondary: str, dark: bool,
) -> Image.Image:
    """
    Draw whichever of the 6 shapes this Rider uses. Only ever called
    for a Rider whose effect is in SHAPE_EFFECTS -- everyone else just
    keeps using the plain native progress bar, which never touches
    this function at all.
    """
    return _SHAPE_RENDERERS[effect](width, height, progress_fraction, primary, secondary, dark)


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


# ===================================================================== #
# Tier 3: enforcement/interaction tweaks
# See docs/superpowers/specs/2026-08-11-tier3-enforcement-interaction-design.md
# ===================================================================== #

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
    # This picture gets stretched across the ENTIRE app window (header
    # AND the tab panel below it), not just the header -- dead center
    # of the picture lands right on the seam between the two, easy to
    # miss. Placing it a bit above that instead keeps it inside the
    # header, roughly where the timer digits are.
    position = ((width - glyph_size) // 2, round(height * 0.22) - glyph_size // 2)
    result.alpha_composite(glyph, position)
    return result


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
