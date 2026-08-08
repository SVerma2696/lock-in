"""
visuals.py
==========
This file makes the pretty pictures: a soft glow behind the timer and the
Henshin button, and a faint patterned picture behind the whole window. It
also picks a nicer-looking font name for whatever computer you're on.

This file doesn't know anything about timers, Kamen Riders, or buttons —
it just makes pictures when asked. `ui.py` is the one that asks for a
picture and decides where to put it on the screen.
"""

from __future__ import annotations

import sys

from PIL import Image, ImageDraw


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
) -> Image.Image:
    """
    Make a faint, wallpaper-like picture with soft diagonal stripes in
    the Rider's two colors.

    This is meant to sit behind everything else in the whole window, so
    it has to stay quiet and low-key — like wallpaper, not a poster —
    or it would make the words on top of it hard to read.
    """
    r1, g1, b1 = _hex_to_rgb(primary)
    r2, g2, b2 = _hex_to_rgb(secondary)
    base = (17, 19, 23) if dark else (245, 246, 248)
    stripe_alpha = 20 if dark else 12

    image = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(image, "RGBA")

    stripe_width = 90
    colors = [(r1, g1, b1, stripe_alpha), (r2, g2, b2, stripe_alpha)]
    # Draw wide diagonal bands across the whole picture, alternating
    # between the two Rider colors, going from bottom-left to top-right.
    start = -height
    for i, x in enumerate(range(start, width, stripe_width)):
        draw.polygon(
            [
                (x, height),
                (x + height, 0),
                (x + height + stripe_width, 0),
                (x + stripe_width, height),
            ],
            fill=colors[i % 2],
        )

    return image
