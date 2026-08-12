from lock_in.config import Config
from lock_in.presets import GAVV_MICRO_SPRINT


def test_phase_seconds_uses_normal_settings_by_default():
    config = Config(focus_minutes=25, short_break_minutes=5, long_break_minutes=15)
    assert config.phase_seconds("focus") == 25 * 60
    assert config.phase_seconds("short_break") == 5 * 60
    assert config.phase_seconds("long_break") == 15 * 60


def test_phase_seconds_uses_gavv_values_when_micro_sprint_mode_is_on():
    config = Config(focus_minutes=25, short_break_minutes=5, long_break_minutes=15,
                     micro_sprint_mode=True)
    assert config.phase_seconds("focus") == GAVV_MICRO_SPRINT.focus_minutes * 60
    assert config.phase_seconds("short_break") == GAVV_MICRO_SPRINT.short_break_minutes * 60
    assert config.phase_seconds("long_break") == GAVV_MICRO_SPRINT.long_break_minutes * 60


def test_micro_sprint_mode_defaults_to_off():
    assert Config().micro_sprint_mode is False


def test_turning_micro_sprint_mode_off_restores_normal_settings():
    """Flipping the switch back never has to "remember" anything -- your
    real settings were never touched in the first place."""
    config = Config(focus_minutes=25, micro_sprint_mode=True)
    assert config.phase_seconds("focus") == GAVV_MICRO_SPRINT.focus_minutes * 60
    config.micro_sprint_mode = False
    assert config.phase_seconds("focus") == 25 * 60


def test_effective_grace_seconds_uses_normal_value_by_default():
    config = Config(grace_seconds=8)
    assert config.effective_grace_seconds() == 8


def test_effective_grace_seconds_is_zero_when_zero_grace_mode_is_on():
    config = Config(grace_seconds=8, zero_grace_mode=True)
    assert config.effective_grace_seconds() == 0


def test_zero_grace_mode_defaults_to_off():
    assert Config().zero_grace_mode is False


def test_effective_sound_and_toast_use_normal_values_by_default():
    config = Config(sound_enabled=True, toast_enabled=True)
    assert config.effective_sound_enabled() is True
    assert config.effective_toast_enabled() is True


def test_effective_sound_and_toast_are_off_when_stealth_mute_mode_is_on():
    config = Config(sound_enabled=True, toast_enabled=True, stealth_mute_mode=True)
    assert config.effective_sound_enabled() is False
    assert config.effective_toast_enabled() is False


def test_stealth_mute_mode_defaults_to_off():
    assert Config().stealth_mute_mode is False


def test_turning_stealth_mute_mode_off_restores_normal_values():
    """Same non-destructive rule as micro_sprint_mode -- your real Sounds
    and Desktop notifications switches were never touched."""
    config = Config(sound_enabled=True, stealth_mute_mode=True)
    assert config.effective_sound_enabled() is False
    config.stealth_mute_mode = False
    assert config.effective_sound_enabled() is True
