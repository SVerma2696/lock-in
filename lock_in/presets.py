"""
presets.py
==========
This file is a small list of ready-made timer-length bundles. A few
Riders in Settings (Kuuga, Super-1, Gavv) show buttons or a switch that
apply one of these bundles all at once, instead of you typing 4 numbers
in by hand.

This file doesn't know anything about buttons or Settings tabs -- it
just lists the numbers. ui.py is the one that turns these into
something you can click.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimerPreset:
    """One ready-made bundle of timer lengths, with a name in each wording style."""

    name_tokusatsu: str
    name_professional: str
    focus_minutes: int
    short_break_minutes: int
    long_break_minutes: int
    blocks_until_long_break: int
    # A short line explaining what this preset is FOR. Only Super-1's
    # presets use this today -- Kuuga's names are self-explanatory
    # enough on their own (a "25m" button doesn't need extra text).
    description: str = ""


KUUGA_PRESETS: list[TimerPreset] = [
    TimerPreset("Mighty", "Standard (25m)", 25, 5, 15, 4),
    TimerPreset("Dragon", "Quick Sprint (10m)", 10, 3, 10, 5),
    TimerPreset("Pegasus", "Deep Work (50m)", 50, 10, 20, 3),
    TimerPreset("Titan", "Endurance (90m)", 90, 15, 30, 2),
]

SUPER1_PRESETS: list[TimerPreset] = [
    TimerPreset(
        "Super Hand", "Development (25m)", 25, 5, 15, 4,
        "General software development",
    ),
    TimerPreset(
        "Power Hand", "Hardware/Embedded (50m)", 50, 10, 20, 3,
        "Hardware & embedded engineering",
    ),
    TimerPreset(
        "Elek Hand", "Admin (15m)", 15, 5, 15, 4,
        "Admin & correspondence",
    ),
    TimerPreset(
        "Cold/Thermal Hand", "Logic/AI (45m)", 45, 10, 20, 3,
        "Logic & AI implementation",
    ),
    TimerPreset(
        "Radar Hand", "Research (30m)", 30, 5, 15, 4,
        "Network analysis & research",
    ),
]

# Gavv's toggle doesn't pick from a list -- it's always this one bundle,
# read straight off of Config.phase_seconds() while the switch is on.
GAVV_MICRO_SPRINT = TimerPreset("Bite-Sized Mode", "Micro-Sprint Mode", 10, 8, 15, 2)
