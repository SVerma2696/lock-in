"""
rider_themes.py
================
This file is a big list of Kamen Rider costume colors. When you pick a
Rider in Settings, the app paints itself with that Rider's two colors:
one main color (`primary`, used for the timer and the Henshin button)
and one helper color (`secondary`, used for a small label and the
button's outline). Nothing else changes — same buttons, same words,
just different colors, like changing a costume.

For every Rider we only write down ONE shade of each color. The
`lighten()` helper below makes a second, paler shade automatically for
dark mode, so we don't have to pick 76 colors by hand.

Where these colors came from: checked each Rider's real suit
and made a list. A few Riders had more than two colors listed; 
where that happened, one color was picked to keepthings simple — see
docs/superpowers/specs/2026-08-07-lock-in-rebrand-design.md if a color
here looks surprising.
"""

from __future__ import annotations

from dataclasses import dataclass


def lighten(hex_color: str, factor: float = 0.35) -> str:
    """
    Mix a color with white to make a paler version of it.

    `factor` says how much white to mix in: 0 means "no change at all",
    1 means "turn it all the way to white". Dark mode needs paler colors
    so text is still easy to read on a dark background.
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = round(r + (255 - r) * factor)
    g = round(g + (255 - g) * factor)
    b = round(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def darken(hex_color: str, factor: float = 0.35) -> str:
    """
    Mix a color with black to make a much dimmer version of it.

    `factor` says how much black to mix in: 0 means "no change at all",
    1 means "turn it all the way to black". This is `lighten()`'s
    opposite twin -- used for backgrounds instead of text, since a
    background needs to go the other way (darker, not paler) to stay
    readable behind light-colored text in dark mode.
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = round(r * (1 - factor))
    g = round(g * (1 - factor))
    b = round(b * (1 - factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def readable_text_color(hex_color: str) -> str:
    """
    Pick plain black or white, whichever one shows up more clearly on
    top of `hex_color`.

    This uses a well-known trick for "how bright does this color LOOK
    to a person" — green looks much brighter than blue even at the same
    number, so we weigh each color a different amount instead of just
    averaging them.
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    perceived_brightness = (r * 299 + g * 587 + b * 114) / 1000
    return "#000000" if perceived_brightness > 150 else "#ffffff"


@dataclass(frozen=True)
class RiderTheme:
    """One Rider's two colors, plus which era and year they're from."""

    era: str
    year: int
    primary: str
    secondary: str

    @property
    def primary_pair(self) -> tuple[str, str]:
        """The normal color, and a paler one for dark mode."""
        return (self.primary, lighten(self.primary))

    @property
    def secondary_pair(self) -> tuple[str, str]:
        return (self.secondary, lighten(self.secondary))

    @property
    def surface_pair(self) -> tuple[str, str]:
        """
        A panel-background color tinted by this Rider's primary color —
        pale for light mode, dark for dark mode. Both come from the
        exact same starting color, just pushed toward opposite ends, so
        a Rider's theme reads as "the same theme" whichever mode you're
        in, not two unrelated colors.

        0.72 (not closer to 1.0) is chosen on purpose: push it much
        darker than that and almost every color collapses toward the
        same near-black, and dark mode stops looking like it has a
        theme applied at all.
        """
        return (lighten(self.primary, 0.90), darken(self.primary, 0.72))

    @property
    def primary_text_pair(self) -> tuple[str, str]:
        """
        A version of `primary` that's always safe to use as TEXT sitting
        on top of this theme's own `surface_pair` — unlike `primary_pair`
        (which is the plain, vivid color, meant for things like the
        progress bar), this one is always darkened for light mode and
        lightened for dark mode.

        Without this, a Rider whose primary color is already very pale
        (like Fourze's pure white) would have text that's the EXACT
        same color as its own pale light-mode background — invisible.
        Pushing the text color further in the opposite direction from
        the surface color fixes that for every Rider, not just the
        obviously pale ones.
        """
        return (darken(self.primary, 0.35), lighten(self.primary, 0.35))

    @property
    def secondary_text_pair(self) -> tuple[str, str]:
        """The same idea as `primary_text_pair`, but for `secondary`."""
        return (darken(self.secondary, 0.35), lighten(self.secondary, 0.35))

    @property
    def button_text_pair(self) -> tuple[str, str]:
        """
        The right text color to sit directly ON TOP of `secondary_pair`
        (used for the words on the Henshin button itself).

        This is a different problem than the two pairs above: those mix
        in some black or white to create a paler/darker VARIANT of a
        color for text to sit *near*. This one has to sit *directly on
        top of* secondary_pair's exact color, so a tinted variant isn't
        enough — it needs plain black or white, whichever actually
        shows up, picked separately for each of light and dark mode
        since secondary_pair itself is a different shade in each.
        """
        light_fill, dark_fill = self.secondary_pair
        return (readable_text_color(light_fill), readable_text_color(dark_fill))


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

# The very first Kamen Rider show. A good, neutral starting theme.
DEFAULT_RIDER_THEME = "Kamen Rider (1971)"
