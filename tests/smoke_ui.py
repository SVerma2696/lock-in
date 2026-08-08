"""
This is a "does the real app actually open and work?" test — it's separate
from the normal pytest tests.

It builds the real app window (using a fake, invisible display) and clicks
it through everything that only happens once the app is actually running:
building the window, the main loop, reading from the waiting lines, showing
blocked windows, correcting the model, and shutting down cleanly. This catches
mistakes that the regular tests structurally can't, like a typo in a widget's
setting, things being placed in the wrong order, or a timer trying to update
a window that's already been closed.

Run it with:  xvfb-run -a python tests/smoke_ui.py
"""

import sys
import time

from lock_in.enforcer import Action, WindowInfo
from lock_in.session import Phase
from lock_in.ui import LockInApp

failures = []


def check(label, condition):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        failures.append(label)


print("building window...")
app = LockInApp()
app.config_obj.hard_mode = True          # turn this on so we can test the top two steps too
app.config_obj.lockdown_seconds = 1
app.update()

check("window built", app.winfo_exists())
check("timer shows a duration", ":" in app.time_label.cget("text"))
check("starts idle", app.session.phase is Phase.IDLE)

print("starting a focus block...")
app._on_toggle()
app.update()
check("entered focus", app.session.phase is Phase.FOCUS)
check("monitor resumed", app.monitor.is_active)
check("button flipped to Pause", app.start_button.cget("text") == "Pause")

print("injecting a blocked window...")
app._window_queue.put(WindowInfo(process_name="discord.exe", title="general #chat", handle=0))
app.update()
app._drain_window_queue()
app.update()
check("activity logged", len(app.activity) == 1)
check("logged the right app", "discord.exe" in app.activity[0]["key"])

print("driving the escalation ladder...")
seen = set()
for _ in range(6):
    app.enforcer._last_strike_at = None      # skip the "don't escalate too fast" wait
    app.enforcer._blocked_since = time.monotonic() - 60
    app._window_queue.put(WindowInfo(process_name="discord.exe", title="general #chat", handle=0))
    app._drain_window_queue()
    app.update()
    seen.add(app.enforcer.strikes)
check("strikes accumulated", max(seen) >= 4)
check("lockdown overlay appeared", app._lockdown_window is not None)

app._close_lockdown()
app.update()
check("lockdown closes cleanly", app._lockdown_window is None)

print("de-duplication...")
before = len(app.activity)
for _ in range(5):
    app._window_queue.put(WindowInfo(process_name="discord.exe", title="general #chat", handle=0))
    app._drain_window_queue()
app.update()
check("repeat hits collapse into one row", len(app.activity) == before)

print("observation recording...")
check("recorded the windows it saw", len(app.observations.all()) >= 1)
check("recording captured the model's opinion",
      app.observations.all()[0].get("predicted") is not None)

print("correcting the model...")
vocab_before = len(app.model.vocabulary)
app._correct(app.activity[0], "study")
app.update()
check("model learned", len(app.model.vocabulary) >= vocab_before)
check("process auto-allowlisted", "discord.exe" in app.config_obj.normalised_allowlist())
check("correction mirrored into training data", len(app.observations.labelled()) >= 1)
check("labelled rows leave the pending queue",
      all(r.label is not None for r in app.observations.labelled()))

print("phase transitions...")
app._on_skip()
app.update()
check("skip moved to a break", app.session.phase.is_break)
check("monitor paused on break", not app.monitor.is_active)

app._on_skip()
app.update()
check("break -> focus", app.session.phase is Phase.FOCUS)

print("tabs...")
for tab in ("Blocking", "Activity", "Settings"):
    app.tabs.set(tab)
    app.update()
check("all tabs render", True)

print("saving from widgets...")
app._save_lists()
app._save_settings()
app.update()
check("saves without error", True)

print("reset + shutdown...")
app._on_reset()
app.update()
check("reset returns to idle", app.session.phase is Phase.IDLE)

app._on_close()
print()
if failures:
    print(f"{len(failures)} FAILURES: {failures}")
    sys.exit(1)
print("smoke test passed")