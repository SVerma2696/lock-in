"""
rider_themes.py
================
This file is a big list of Kamen Rider costume colors. When you pick a
Rider in Settings, the app paints itself with that Rider's two colors:
one main color (`primary`, used for the timer and the Henshin button)
and one helper color (`secondary`, used for a small label and the
button's outline). Nothing else changes — same buttons, same words,
just different colors, like changing a costume.

Each color is written down as a PAIR — one hex for light mode, one hex
for dark mode — instead of one hex with the other shade guessed by a
formula. A color that looks great on a white background can wash out or
vanish on a near-black one (and the other way around), so each shade
was hand-picked to stay easy to see in its own mode, not derived from
its twin.

Where these colors came from: checked each Rider's real suit and made a
list, then nudged each shade so it holds up against this app's own
light/dark backgrounds specifically. A few Riders had more than two
colors listed; where that happened, one color was picked to keep things
simple — see docs/superpowers/specs/2026-08-07-lock-in-rebrand-design.md
if a color here looks surprising.
"""

from __future__ import annotations

from dataclasses import dataclass


def lighten(hex_color: str, factor: float = 0.35) -> str:
    """
    Mix a color with white to make a paler version of it.

    `factor` says how much white to mix in: 0 means "no change at all",
    1 means "turn it all the way to white". Used to push a color further
    toward white for text/surfaces that need extra contrast in dark mode.
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


@dataclass(frozen=True)
class RiderTheme:
    """One Rider's two colors, plus which era and year they're from."""

    era: str
    year: int
    # Each color is (light_mode_hex, dark_mode_hex) -- picked by hand for
    # each mode, not one color with the other guessed from it.
    primary: tuple[str, str]
    secondary: tuple[str, str]
    # "none" for every Rider except the 9 with a Tier 1 gimmick (see
    # docs/superpowers/specs/2026-08-10-tier1-rider-progress-variants-design.md).
    # visuals.py and ui.py read this to decide what the progress bar or
    # background should look like for this Rider.
    tier1_effect: str = "none"
    # "none" for every Rider except the 5 with a Tier 3 gimmick (see
    # docs/superpowers/specs/2026-08-11-tier3-enforcement-interaction-design.md).
    # ui.py reads this to decide what enforcement/interaction behavior
    # this Rider needs.
    tier3_effect: str = "none"

    @property
    def primary_pair(self) -> tuple[str, str]:
        """The hand-picked (light mode, dark mode) pair, as-is."""
        return self.primary

    @property
    def secondary_pair(self) -> tuple[str, str]:
        return self.secondary

    @property
    def surface_pair(self) -> tuple[str, str]:
        """
        A panel-background color tinted by this Rider's primary color —
        pale for light mode, dark for dark mode. Each side starts from
        THAT mode's own primary shade, so a Rider's theme reads as "the
        same theme" whichever mode you're in, without the two modes
        having to share one single starting color.

        0.72 (not closer to 1.0) is chosen on purpose: push it much
        darker than that and almost every color collapses toward the
        same near-black, and dark mode stops looking like it has a
        theme applied at all.
        """
        light_primary, dark_primary = self.primary
        return (lighten(light_primary, 0.90), darken(dark_primary, 0.72))

    @property
    def primary_text_pair(self) -> tuple[str, str]:
        """
        A version of `primary` that's always safe to use as TEXT sitting
        on top of this theme's own `surface_pair` — unlike `primary_pair`
        (which is the plain, vivid color, meant for things like the
        progress bar), this one is always darkened for light mode and
        lightened for dark mode, starting from that mode's own shade.

        Without this, a Rider whose primary color is already very pale
        would have text that's too close to its own pale light-mode
        background — hard to read. Pushing the text color further in the
        opposite direction from the surface color fixes that for every
        Rider, not just the obviously pale ones.
        """
        light_primary, dark_primary = self.primary
        return (darken(light_primary, 0.35), lighten(dark_primary, self._dark_mode_text_factor))

    @property
    def secondary_text_pair(self) -> tuple[str, str]:
        """The same idea as `primary_text_pair`, but for `secondary`."""
        light_secondary, dark_secondary = self.secondary
        return (
            darken(light_secondary, 0.35),
            lighten(dark_secondary, self._dark_mode_text_factor),
        )

    @property
    def _dark_mode_text_factor(self) -> float:
        """
        How far dark-mode text gets pushed toward white. Every Rider
        uses the normal amount (0.35) EXCEPT Black, whose whole gimmick
        (see Tier 1) is stricter, higher contrast in dark mode -- so its
        words get pushed further toward pure white, standing out more
        sharply against its own already-near-black primary color.
        """
        return 0.55 if self.tier1_effect == "high_contrast_dark" else 0.35

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
    "Kamen Rider (1971)": RiderTheme(
        "Showa", 1971, ("#154a2e", "#237a4b"), ("#a83225", "#d94436"), tier1_effect="windmill",
    ),
    "Kamen Rider V3 (1973)": RiderTheme(
        "Showa", 1973, ("#225c25", "#4caf50"), ("#a83225", "#d94436"),
    ),
    "Kamen Rider X (1974)": RiderTheme(
        "Showa", 1974, ("#90a4ae", "#cfd8dc"), ("#0f4a8f", "#42a5f5"),
        tier3_effect="goal_gate",
    ),
    "Kamen Rider Amazon (1974)": RiderTheme(
        "Showa", 1974, ("#224714", "#558b2f"), ("#b33f00", "#ff9800"),
        tier3_effect="zero_ui",
    ),
    "Kamen Rider Stronger (1975)": RiderTheme(
        "Showa", 1975, ("#9c1e1e", "#ef5350"), ("#1a1a1a", "#757575"), tier1_effect="border_glow",
    ),
    "Kamen Rider Skyrider (1979)": RiderTheme(
        "Showa", 1979, ("#225c25", "#4caf50"), ("#5d4037", "#8d6e63"), tier1_effect="rising_bar",
    ),
    "Kamen Rider Super-1 (1980)": RiderTheme(
        "Showa", 1980, ("#9e9e9e", "#e0e0e0"), ("#1a1a1a", "#757575"),
    ),
    "Kamen Rider ZX (1982)": RiderTheme(
        "Showa", 1982, ("#9c1e1e", "#ef5350"), ("#78909c", "#b0bec5"),
        tier3_effect="stealth_mute",
    ),
    "Kamen Rider Black (1987)": RiderTheme(
        "Showa", 1987, ("#111111", "#616161"), ("#00903b", "#00e676"), tier1_effect="high_contrast_dark",
    ),
    "Kamen Rider Black RX (1988)": RiderTheme(
        "Showa", 1988, ("#225c25", "#4caf50"), ("#111111", "#616161"),
    ),
    "Kamen Rider Kuuga (2000)": RiderTheme(
        "Heisei", 2000, ("#961d22", "#ef5350"), ("#1a1a1a", "#757575"),
    ),
    "Kamen Rider Agito (2001)": RiderTheme(
        "Heisei", 2001, ("#d49e15", "#ffca28"), ("#1a1a1a", "#757575"), tier1_effect="color_interpolation",
    ),
    "Kamen Rider Ryuki (2002)": RiderTheme(
        "Heisei", 2002, ("#9c1e1e", "#ef5350"), ("#757575", "#b0bec5"),
    ),
    "Kamen Rider 555 (2003)": RiderTheme(
        "Heisei", 2003, ("#111111", "#424242"), ("#a60000", "#ff1744"),
        tier3_effect="code_unlock",
    ),
    "Kamen Rider Blade (2004)": RiderTheme(
        "Heisei", 2004, ("#0f4a8f", "#42a5f5"), ("#78909c", "#b0bec5"),
    ),
    "Kamen Rider Hibiki (2005)": RiderTheme(
        "Heisei", 2005, ("#310d5e", "#7b1fa2"), ("#9c1e1e", "#ef5350"),
    ),
    "Kamen Rider Kabuto (2006)": RiderTheme(
        "Heisei", 2006, ("#9c1e1e", "#ef5350"), ("#607d8b", "#b0bec5"),
    ),
    "Kamen Rider Den-O (2007)": RiderTheme(
        "Heisei", 2007, ("#9c1e1e", "#ef5350"), ("#90a4ae", "#eceff1"),
    ),
    "Kamen Rider Kiva (2008)": RiderTheme(
        "Heisei", 2008, ("#660000", "#d32f2f"), ("#d49e15", "#ffca28"), tier1_effect="night_overlay",
    ),
    "Kamen Rider Decade (2009)": RiderTheme(
        "Heisei", 2009, ("#9e1447", "#f06292"), ("#1a1a1a", "#757575"),
    ),
    "Kamen Rider W (2009)": RiderTheme(
        "Heisei", 2009, ("#225c25", "#4caf50"), ("#111111", "#616161"),
    ),
    "Kamen Rider OOO (2010)": RiderTheme(
        "Heisei", 2010, ("#111111", "#616161"), ("#9c1e1e", "#ef5350"),
    ),
    "Kamen Rider Fourze (2011)": RiderTheme(
        "Heisei", 2011, ("#9e9e9e", "#ffffff"), ("#b33f00", "#ff9800"), tier1_effect="constellation",
    ),
    "Kamen Rider Wizard (2012)": RiderTheme(
        "Heisei", 2012, ("#9c1e1e", "#ef5350"), ("#1a1a1a", "#757575"),
    ),
    "Kamen Rider Gaim (2013)": RiderTheme(
        "Heisei", 2013, ("#b33f00", "#ff9800"), ("#96761c", "#e4c657"),
        tier3_effect="lock_overlay",
    ),
    "Kamen Rider Drive (2014)": RiderTheme(
        "Heisei", 2014, ("#9c1e1e", "#ef5350"), ("#1a1a1a", "#757575"), tier1_effect="accelerating_fill",
    ),
    "Kamen Rider Ghost (2015)": RiderTheme(
        "Heisei", 2015, ("#111111", "#616161"), ("#cc7a00", "#ffb74d"),
    ),
    "Kamen Rider Ex-Aid (2016)": RiderTheme(
        "Heisei", 2016, ("#b3154b", "#f06292"), ("#009e52", "#69f0ae"),
    ),
    "Kamen Rider Build (2017)": RiderTheme(
        "Heisei", 2017, ("#9c1e1e", "#ef5350"), ("#0f4a8f", "#42a5f5"), tier1_effect="vials",
    ),
    "Kamen Rider Zi-O (2018)": RiderTheme(
        "Heisei", 2018, ("#1a1a1a", "#757575"), ("#9e1447", "#f06292"),
    ),
    "Kamen Rider Zero-One (2019)": RiderTheme(
        "Reiwa", 2019, ("#77a100", "#c6ff00"), ("#111111", "#616161"),
    ),
    "Kamen Rider Saber (2020)": RiderTheme(
        "Reiwa", 2020, ("#9c1e1e", "#ef5350"), ("#1a1a1a", "#757575"),
    ),
    "Kamen Rider Revice (2021)": RiderTheme(
        "Reiwa", 2021, ("#b3154b", "#f06292"), ("#0097a7", "#18ffff"),
    ),
    "Kamen Rider Geats (2022)": RiderTheme(
        "Reiwa", 2022, ("#9e9e9e", "#ffffff"), ("#9c1e1e", "#ef5350"),
    ),
    "Kamen Rider Gotchard (2023)": RiderTheme(
        "Reiwa", 2023, ("#008394", "#4dd0e1"), ("#b33f00", "#ffb74d"),
    ),
    "Kamen Rider Gavv (2024)": RiderTheme(
        "Reiwa", 2024, ("#571673", "#ab47bc"), ("#c48000", "#ffee58"),
    ),
    "Kamen Rider Zeztz (2025)": RiderTheme(
        "Reiwa", 2025, ("#225c25", "#4caf50"), ("#111111", "#616161"),
    ),
    "Kamen Rider MY-TH (2026)": RiderTheme(
        "Reiwa", 2026, ("#0f4a8f", "#42a5f5"), ("#78909c", "#b0bec5"),
    ),
}

# The very first Kamen Rider show. A good, neutral starting theme.
DEFAULT_RIDER_THEME = "Kamen Rider (1971)"
