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
