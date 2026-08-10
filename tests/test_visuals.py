from lock_in.visuals import (
    APP_ICON_PATH,
    display_font_family,
    load_app_icon,
    make_background_texture,
    make_glow,
    make_panel_divider,
)


def test_display_font_family_returns_a_non_empty_name():
    assert isinstance(display_font_family(), str)
    assert display_font_family()


def test_make_glow_returns_the_requested_size():
    image = make_glow(100, 60, "#ff0000")
    assert image.size == (100, 60)
    assert image.mode == "RGBA"


def test_make_glow_is_brightest_in_the_middle():
    image = make_glow(100, 60, "#ff0000")
    center_alpha = image.getpixel((50, 30))[3]
    partway_alpha = image.getpixel((50, 12))[3]   # 60% of the way to the edge
    corner_alpha = image.getpixel((0, 0))[3]       # past the edge of the glow
    assert center_alpha > partway_alpha > corner_alpha
    # The very corner should be so faint it's practically invisible —
    # this is what keeps the glow from showing a hard rectangle border.
    assert corner_alpha == 0


def test_make_background_texture_returns_the_requested_size():
    image = make_background_texture(200, 150, "#ff0000", "#00ff00", dark=True)
    assert image.size == (200, 150)
    assert image.mode == "RGB"


def test_dark_texture_is_darker_than_light_texture():
    dark = make_background_texture(50, 50, "#ff0000", "#00ff00", dark=True, era="Heisei")
    light = make_background_texture(50, 50, "#ff0000", "#00ff00", dark=False, era="Heisei")
    # Compare a corner pixel far from any stripe seam, where both should
    # be close to their plain base color.
    dark_brightness = sum(dark.getpixel((0, 0)))
    light_brightness = sum(light.getpixel((0, 0)))
    assert dark_brightness < light_brightness


def test_default_era_matches_heisei():
    """Not passing an era at all should read exactly like asking for Heisei."""
    default = make_background_texture(200, 200, "#ff0000", "#00ff00", dark=True)
    heisei = make_background_texture(200, 200, "#ff0000", "#00ff00", dark=True, era="Heisei")
    assert default.tobytes() == heisei.tobytes()


def test_each_era_has_a_visibly_different_pattern():
    """The whole point is that each era looks different, not just re-tinted."""
    showa = make_background_texture(300, 300, "#ff0000", "#00ff00", dark=True, era="Showa")
    heisei = make_background_texture(300, 300, "#ff0000", "#00ff00", dark=True, era="Heisei")
    reiwa = make_background_texture(300, 300, "#ff0000", "#00ff00", dark=True, era="Reiwa")

    assert showa.tobytes() != heisei.tobytes()
    assert heisei.tobytes() != reiwa.tobytes()
    assert showa.tobytes() != reiwa.tobytes()


def test_unknown_era_falls_back_to_heisei_pattern():
    unknown = make_background_texture(200, 200, "#ff0000", "#00ff00", dark=True, era="Not A Real Era")
    heisei = make_background_texture(200, 200, "#ff0000", "#00ff00", dark=True, era="Heisei")
    assert unknown.tobytes() == heisei.tobytes()


def test_app_icon_file_exists_where_load_app_icon_expects_it():
    assert APP_ICON_PATH.exists()


def test_load_app_icon_returns_a_square_see_through_image():
    icon = load_app_icon()
    assert icon is not None
    width, height = icon.size
    assert width == height
    assert icon.mode == "RGBA"


def test_load_app_icon_pads_instead_of_stretching():
    """Padding to a square must not squash the original artwork."""
    from PIL import Image
    original = Image.open(APP_ICON_PATH)
    icon = load_app_icon()
    assert icon.size[0] == max(original.size)


def test_load_app_icon_survives_a_missing_file(monkeypatch):
    from pathlib import Path
    import lock_in.visuals as visuals
    monkeypatch.setattr(visuals, "APP_ICON_PATH", Path("nonexistent_file.png"))
    assert visuals.load_app_icon() is None


def test_make_panel_divider_returns_the_requested_size():
    image = make_panel_divider(400, 14, "#ff0000", "#00ff00", era="Heisei")
    assert image.size == (400, 14)
    assert image.mode == "RGBA"


def test_each_era_has_a_visibly_different_divider():
    showa = make_panel_divider(400, 14, "#ff0000", "#00ff00", era="Showa")
    heisei = make_panel_divider(400, 14, "#ff0000", "#00ff00", era="Heisei")
    reiwa = make_panel_divider(400, 14, "#ff0000", "#00ff00", era="Reiwa")

    assert showa.tobytes() != heisei.tobytes()
    assert heisei.tobytes() != reiwa.tobytes()
    assert showa.tobytes() != reiwa.tobytes()


def test_panel_divider_default_era_matches_heisei():
    default = make_panel_divider(400, 14, "#ff0000", "#00ff00")
    heisei = make_panel_divider(400, 14, "#ff0000", "#00ff00", era="Heisei")
    assert default.tobytes() == heisei.tobytes()


def test_panel_divider_unknown_era_falls_back_to_heisei():
    unknown = make_panel_divider(400, 14, "#ff0000", "#00ff00", era="Not A Real Era")
    heisei = make_panel_divider(400, 14, "#ff0000", "#00ff00", era="Heisei")
    assert unknown.tobytes() == heisei.tobytes()


def test_panel_divider_is_not_blank():
    """The whole point is a visible design, not an empty strip."""
    image = make_panel_divider(400, 14, "#ff0000", "#00ff00", era="Showa")
    # A fully see-through strip would mean every pixel has alpha 0 --
    # the highest alpha value anywhere in the picture should be above
    # that, or there's nothing actually visible.
    _, max_alpha = image.getchannel("A").getextrema()
    assert max_alpha > 0
