from lock_in.rider_themes import (
    DEFAULT_RIDER_THEME,
    RIDER_THEMES,
    darken,
    lighten,
    readable_text_color,
)


def _brightness(hex_color: str) -> int:
    hex_color = hex_color.lstrip("#")
    return sum(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def test_has_all_38_riders():
    assert len(RIDER_THEMES) == 38


def test_default_theme_is_the_original():
    assert DEFAULT_RIDER_THEME == "Kamen Rider (1971)"
    assert DEFAULT_RIDER_THEME in RIDER_THEMES


def test_spot_check_corrected_palette_values():
    # These pin the user-corrected palette so a future edit can't quietly
    # drift back toward the original (wrong) guesses.
    assert RIDER_THEMES["Kamen Rider (1971)"].primary == "#1b5e3a"
    assert RIDER_THEMES["Kamen Rider (1971)"].secondary == "#c0392b"
    assert RIDER_THEMES["Kamen Rider V3 (1973)"].primary == "#2e7d32"
    assert RIDER_THEMES["Kamen Rider Zero-One (2019)"].primary == "#aeea00"
    assert RIDER_THEMES["Kamen Rider Gavv (2024)"].secondary == "#fbc02d"
    assert RIDER_THEMES["Kamen Rider MY-TH (2026)"].primary == "#1565c0"


def test_every_entry_has_valid_hex_colors():
    for name, theme in RIDER_THEMES.items():
        for value in (theme.primary, theme.secondary):
            assert value.startswith("#") and len(value) == 7, f"{name}: {value!r}"


def test_lighten_moves_toward_white():
    assert lighten("#000000", 0.5) == "#808080"
    assert lighten("#000000", 0.0) == "#000000"
    assert lighten("#000000", 1.0) == "#ffffff"


def test_theme_color_pairs_are_light_dark_tuples():
    theme = RIDER_THEMES["Kamen Rider (1971)"]
    light, dark = theme.primary_pair
    assert light == theme.primary
    assert dark != theme.primary  # the dark-mode variant must actually differ


def test_darken_moves_toward_black():
    assert darken("#ffffff", 0.5) == "#808080"
    assert darken("#ffffff", 0.0) == "#ffffff"
    assert darken("#ffffff", 1.0) == "#000000"


def test_surface_pair_is_pale_for_light_and_near_black_for_dark():
    theme = RIDER_THEMES["Kamen Rider (1971)"]  # primary is a green
    light_surface, dark_surface = theme.surface_pair

    def brightness(hex_color: str) -> int:
        hex_color = hex_color.lstrip("#")
        return sum(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    # Light mode surface should read as "pale" (bright), dark mode as
    # "near-black" (dim) -- same underlying hue, very different brightness.
    assert brightness(light_surface) > 600   # close to white (max 765)
    assert brightness(dark_surface) < 100    # close to black


def test_surface_pair_keeps_the_riders_hue_recognisable():
    """Two different Riders' surfaces shouldn't collapse to the same grey."""
    green_rider = RIDER_THEMES["Kamen Rider (1971)"]
    red_rider = RIDER_THEMES["Kamen Rider Kuuga (2000)"]
    assert green_rider.surface_pair != red_rider.surface_pair


def test_readable_text_color_picks_black_on_light_backgrounds():
    assert readable_text_color("#ffffff") == "#000000"
    assert readable_text_color("#ffca28") == "#000000"   # a light gold


def test_readable_text_color_picks_white_on_dark_backgrounds():
    assert readable_text_color("#000000") == "#ffffff"
    assert readable_text_color("#1a1a1a") == "#ffffff"   # a near-black


def test_primary_text_pair_is_never_the_same_as_its_own_light_mode_surface():
    """
    This is the exact bug this pair exists to fix: Fourze's primary is
    pure white, so its plain primary_pair light-mode value (white) was
    literally identical to its own pale surface -- invisible text.
    """
    fourze = RIDER_THEMES["Kamen Rider Fourze (2011)"]
    light_text, _ = fourze.primary_text_pair
    light_surface, _ = fourze.surface_pair
    assert light_text != light_surface


def test_primary_text_pair_is_readable_against_its_own_surface_both_modes():
    for name, theme in RIDER_THEMES.items():
        light_text, dark_text = theme.primary_text_pair
        light_surface, dark_surface = theme.surface_pair
        # A gap of at least ~150 (out of a max possible 765) between the
        # text and the surface it sits on is enough that they can never
        # be mistaken for the same color, in either mode.
        assert abs(_brightness(light_text) - _brightness(light_surface)) > 150, name
        assert abs(_brightness(dark_text) - _brightness(dark_surface)) > 150, name


def test_secondary_text_pair_is_readable_against_its_primary_surface_both_modes():
    for name, theme in RIDER_THEMES.items():
        light_text, dark_text = theme.secondary_text_pair
        light_surface, dark_surface = theme.surface_pair
        assert abs(_brightness(light_text) - _brightness(light_surface)) > 100, name
        assert abs(_brightness(dark_text) - _brightness(dark_surface)) > 100, name


def test_button_text_pair_is_readable_against_the_secondary_fill_both_modes():
    """The Henshin button's own text sits directly on secondary_pair --
    it needs to contrast against THAT color, not a tinted version of it."""
    for name, theme in RIDER_THEMES.items():
        light_fill, dark_fill = theme.secondary_pair
        light_text, dark_text = theme.button_text_pair
        # 150 matches readable_text_color()'s own perceived-brightness
        # cutoff, so this checks the choice is never a coin-flip-close
        # call, rather than an arbitrary made-up number.
        assert abs(_brightness(light_text) - _brightness(light_fill)) > 150, name
        assert abs(_brightness(dark_text) - _brightness(dark_fill)) > 150, name
