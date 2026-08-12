from lock_in.visuals import (
    APP_ICON_PATH,
    display_font_family,
    load_app_icon,
    make_background_texture,
    make_glow,
    make_panel_divider,
)


def _alpha_sum(image):
    from PIL import ImageStat
    return ImageStat.Stat(image.getchannel("A")).sum[0]


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


# ===================================================================== #
# Tier 1: per-Rider progress bar variants
# See docs/superpowers/specs/2026-08-10-tier1-rider-progress-variants-design.md
# ===================================================================== #

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


def test_windmill_progress_returns_the_requested_size():
    from lock_in.visuals import render_windmill_progress
    image = render_windmill_progress(80, 80, 0.5, "#1b5e3a", "#c0392b", dark=False)
    assert image.size == (80, 80)
    assert image.mode == "RGBA"


def test_windmill_progress_fills_more_blades_at_higher_progress():
    from lock_in.visuals import render_windmill_progress
    quarter = render_windmill_progress(80, 80, 0.25, "#1b5e3a", "#c0392b", dark=False)
    full = render_windmill_progress(80, 80, 1.0, "#1b5e3a", "#c0392b", dark=False)
    assert _alpha_sum(full) > _alpha_sum(quarter)


def test_rising_bar_progress_returns_the_requested_size():
    from lock_in.visuals import render_rising_bar_progress
    image = render_rising_bar_progress(60, 100, 0.5, "#2e7d32", "#8d6e63", dark=False)
    assert image.size == (60, 100)
    assert image.mode == "RGBA"


def test_rising_bar_progress_rises_more_at_higher_progress():
    from lock_in.visuals import render_rising_bar_progress
    low = render_rising_bar_progress(60, 100, 0.1, "#2e7d32", "#8d6e63", dark=False)
    high = render_rising_bar_progress(60, 100, 0.9, "#2e7d32", "#8d6e63", dark=False)
    assert _alpha_sum(high) > _alpha_sum(low)


def test_constellation_progress_returns_the_requested_size():
    from lock_in.visuals import render_constellation_progress
    image = render_constellation_progress(200, 60, 0.5, "#ffffff", "#ef6c00", dark=True)
    assert image.size == (200, 60)
    assert image.mode == "RGBA"


def test_constellation_progress_lights_more_stars_at_higher_progress():
    from lock_in.visuals import render_constellation_progress
    low = render_constellation_progress(200, 60, 0.1, "#ffffff", "#ef6c00", dark=True)
    high = render_constellation_progress(200, 60, 0.9, "#ffffff", "#ef6c00", dark=True)
    assert _alpha_sum(high) > _alpha_sum(low)


def test_constellation_progress_draws_the_exact_color_it_is_given():
    """Color safety now lives in rider_themes.py's hand-tuned per-mode
    data (see test_fourze_light_mode_primary_is_not_pure_white below),
    not in this renderer -- it just draws whatever hex it's handed."""
    from lock_in.visuals import render_constellation_progress
    image = render_constellation_progress(200, 60, 1.0, "#ffffff", "#ef6c00", dark=False)
    opaque_pixels = [p for p in image.getdata() if p[3] > 200]
    assert any(p[:3] == (255, 255, 255) for p in opaque_pixels)


def test_fourze_light_mode_primary_is_not_pure_white():
    """This is where the old vanishing-stars bug is actually prevented
    now: Fourze's light-mode primary itself is a visible grey, not
    white, so it never vanishes against this app's pale light-mode
    background in the first place."""
    from lock_in.rider_themes import RIDER_THEMES
    fourze = RIDER_THEMES["Kamen Rider Fourze (2011)"]
    assert fourze.primary[0] != "#ffffff"


def test_constellation_progress_star_layout_is_stable_between_calls():
    """The stars must sit in the same spots every time, or the picture
    would visibly jump around every 200ms redraw."""
    from lock_in.visuals import render_constellation_progress
    first = render_constellation_progress(200, 60, 0.5, "#ffffff", "#ef6c00", dark=True)
    second = render_constellation_progress(200, 60, 0.5, "#ffffff", "#ef6c00", dark=True)
    assert first.tobytes() == second.tobytes()


def test_vials_progress_returns_the_requested_size():
    from lock_in.visuals import render_vials_progress
    image = render_vials_progress(120, 60, 0.5, "#c62828", "#1565c0", dark=False)
    assert image.size == (120, 60)
    assert image.mode == "RGBA"


def test_vials_progress_fills_more_at_higher_progress():
    from lock_in.visuals import render_vials_progress
    low = render_vials_progress(120, 60, 0.1, "#c62828", "#1565c0", dark=False)
    high = render_vials_progress(120, 60, 0.6, "#c62828", "#1565c0", dark=False)
    assert _alpha_sum(high) > _alpha_sum(low)


def test_vials_progress_combines_near_completion():
    """Best Match: the two vials should visibly merge once nearly full,
    not just sit there as two separate bars forever."""
    from lock_in.visuals import render_vials_progress
    almost_full = render_vials_progress(120, 60, 0.94, "#c62828", "#1565c0", dark=False)
    combined = render_vials_progress(120, 60, 0.98, "#c62828", "#1565c0", dark=False)
    assert _alpha_sum(combined) > _alpha_sum(almost_full)


def test_ease_drive_progress_matches_true_progress_at_the_endpoints():
    from lock_in.visuals import ease_drive_progress
    assert ease_drive_progress(0.0) == 0.0
    assert ease_drive_progress(1.0) == 1.0


def test_ease_drive_progress_lags_behind_early_and_catches_up_late():
    """The whole point: it LOOKS slower than real progress early on,
    then visibly speeds up and catches up near the end."""
    from lock_in.visuals import ease_drive_progress
    assert ease_drive_progress(0.5) < 0.5
    assert ease_drive_progress(0.9) > ease_drive_progress(0.5) * (0.9 / 0.5)


def test_ease_drive_progress_clamps_out_of_range_progress():
    from lock_in.visuals import ease_drive_progress
    assert ease_drive_progress(-1.0) == 0.0
    assert ease_drive_progress(5.0) == 1.0


def test_render_progress_routes_each_shape_effect_to_its_own_renderer():
    from lock_in import visuals

    routing = {
        "windmill": visuals.render_windmill_progress,
        "rising_bar": visuals.render_rising_bar_progress,
        "constellation": visuals.render_constellation_progress,
        "vials": visuals.render_vials_progress,
    }
    for effect, direct_renderer in routing.items():
        via_dispatch = visuals.render_progress(effect, 100, 40, 0.5, "#ff0000", "#00ff00", False)
        direct = direct_renderer(100, 40, 0.5, "#ff0000", "#00ff00", False)
        assert via_dispatch.tobytes() == direct.tobytes(), effect


def test_shape_effects_constant_matches_the_dispatch_table():
    """ui.py relies on this set to decide when to show the picture
    widget instead of the plain bar -- it has to list exactly the
    Riders render_progress actually knows how to draw."""
    from lock_in import visuals
    assert visuals.SHAPE_EFFECTS == {"windmill", "rising_bar", "constellation", "vials"}


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


# ===================================================================== #
# Tier 3: enforcement/interaction tweaks
# See docs/superpowers/specs/2026-08-11-tier3-enforcement-interaction-design.md
# ===================================================================== #

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


def test_render_amazon_drain_returns_the_requested_size():
    from lock_in.visuals import render_amazon_drain
    image = render_amazon_drain(200, 80, 0.5)
    assert image.size == (200, 80)
    assert image.mode == "RGBA"


def test_render_amazon_drain_shrinks_as_progress_increases():
    """The field DRAINS -- less of it is filled as the block finishes,
    not more (opposite direction from a normal progress bar)."""
    from lock_in.visuals import render_amazon_drain

    early = render_amazon_drain(200, 80, 0.1)
    late = render_amazon_drain(200, 80, 0.9)
    assert _alpha_sum(early) > _alpha_sum(late)


def test_render_amazon_drain_is_always_the_same_amazon_green():
    """No primary/secondary color parameter on purpose -- the spec is a
    literal fixed #33691e, not derived from whichever Rider is picked."""
    from lock_in.visuals import render_amazon_drain
    image = render_amazon_drain(200, 80, 0.0)
    # top-left pixel should be fully the Amazon green, fully opaque
    pixel = image.getpixel((0, 0))
    assert pixel == (51, 105, 30, 235)   # 0x33, 0x69, 0x1e
