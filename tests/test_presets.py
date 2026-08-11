from lock_in.presets import GAVV_MICRO_SPRINT, KUUGA_PRESETS, SUPER1_PRESETS, TimerPreset


def test_kuuga_has_exactly_4_presets():
    assert len(KUUGA_PRESETS) == 4


def test_kuuga_preset_values():
    by_name = {p.name_tokusatsu: p for p in KUUGA_PRESETS}
    assert by_name["Mighty"] == TimerPreset("Mighty", "Standard (25m)", 25, 5, 15, 4)
    assert by_name["Dragon"] == TimerPreset("Dragon", "Quick Sprint (10m)", 10, 3, 10, 5)
    assert by_name["Pegasus"] == TimerPreset("Pegasus", "Deep Work (50m)", 50, 10, 20, 3)
    assert by_name["Titan"] == TimerPreset("Titan", "Endurance (90m)", 90, 15, 30, 2)


def test_super1_has_exactly_5_presets():
    assert len(SUPER1_PRESETS) == 5


def test_super1_preset_values():
    by_name = {p.name_tokusatsu: p for p in SUPER1_PRESETS}
    assert by_name["Super Hand"] == TimerPreset(
        "Super Hand", "Development (25m)", 25, 5, 15, 4,
        "General software development",
    )
    assert by_name["Power Hand"] == TimerPreset(
        "Power Hand", "Hardware/Embedded (50m)", 50, 10, 20, 3,
        "Hardware & embedded engineering",
    )
    assert by_name["Elek Hand"] == TimerPreset(
        "Elek Hand", "Admin (15m)", 15, 5, 15, 4,
        "Admin & correspondence",
    )
    assert by_name["Cold/Thermal Hand"] == TimerPreset(
        "Cold/Thermal Hand", "Logic/AI (45m)", 45, 10, 20, 3,
        "Logic & AI implementation",
    )
    assert by_name["Radar Hand"] == TimerPreset(
        "Radar Hand", "Research (30m)", 30, 5, 15, 4,
        "Network analysis & research",
    )


def test_gavv_micro_sprint_values():
    assert GAVV_MICRO_SPRINT == TimerPreset(
        "Bite-Sized Mode", "Micro-Sprint Mode", 10, 8, 15, 2,
    )
