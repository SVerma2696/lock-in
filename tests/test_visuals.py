from lock_in.visuals import display_font_family, make_background_texture, make_glow


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
    dark = make_background_texture(50, 50, "#ff0000", "#00ff00", dark=True)
    light = make_background_texture(50, 50, "#ff0000", "#00ff00", dark=False)
    # Compare a corner pixel far from any stripe seam, where both should
    # be close to their plain base color.
    dark_brightness = sum(dark.getpixel((0, 0)))
    light_brightness = sum(light.getpixel((0, 0)))
    assert dark_brightness < light_brightness
