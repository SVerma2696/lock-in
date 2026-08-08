# Lock In

A Pomodoro timer that notices when you've drifted onto Discord and does
something about it — Henshin into a focus block, and Lock In makes
leaving it a deliberate decision, not an absent-minded one.

Three things, from the original sketch:

1. **Pomodoro cycles** — focus / short break / long break, configurable, with
   pause, skip, and a streak counter.
2. **App blocking during focus** — a block list, an allow list, and an
   escalating response when you're somewhere you said you didn't want to be.
3. **A learned model** that recognises non-study apps you never listed, and
   gets better every time you correct it.

---

## Quick start

```bat
pip install -r requirements.txt
python main.py
```

Or double-click `run.bat`. To produce a standalone `.exe`, run `build.bat`.
Training happens through a separate CLI — see [Training it](#training-it):

```bat
python train.py label
```

`customtkinter` and `Pillow` are required for the app to *open* — Pillow
draws the glow and background art. On Windows, `pywin32` and `psutil` are
what let it actually see which window you're in — without them, blocking
silently does nothing at all, all day, and the app just becomes a plain
(very good) timer.

This is an easy trap to fall into: `run.bat` launches with `pythonw.exe` on
purpose, so no black console window sits behind the app — but that also
means the "these packages are missing" warning that normally prints to the
console is thrown away and nobody ever sees it. If blocking doesn't seem to
be doing anything, run `pip install -r requirements.txt` again and make sure
it installs `pywin32` and `psutil` without errors. The app also now shows a
red banner on startup, and a note on the Blocking tab, if it can't detect
windows — but it's worth checking directly if you're not sure.

---

## How the blocking actually works

Every second during a focus block, Lock In reads the foreground window's
process name and title and runs it through three layers, in strict order:

```
allow list  →  block list  →  learned model  →  allowed
```

Explicit rules always beat the model. If you allow-list `chrome.exe`, the
classifier never gets to veto that.

When a window is judged blocked, escalation is by **intensity, not frequency**,
and the ladder depends on whether Hard mode is on:

**Soft mode (default — Hard mode off):**

| Time on the app | What happens |
|---|---|
| 0–8s | Nothing. You might be closing it. |
| first strike | Toast notification. |
| every strike after that | Toast + alert sound. |

**Hard mode (Blocking tab → "Hard mode"):** no warnings first — it acts
immediately, since the whole point of turning this on is that you don't
want to be asked nicely.

| Time on the app | What happens |
|---|---|
| 0–8s | Nothing. You might be closing it. |
| first strike | Window minimised, timer pulled to the front. |
| every strike after that | Full-screen cover for 15 seconds. |

Strikes decay after 45 seconds of clean work, so one slip at minute 3 doesn't
leave you one click from a screen takeover at minute 20. Hopping between two
blocked apps restarts the grace period but *keeps* your strikes — app-hopping
to dodge the nag isn't a valid strategy.

All timings are configurable in the Settings tab.

### If a window's program name can't be read

A few programs (Steam is a common one, when it's running "as administrator")
hide their process name from a program that isn't also elevated. When that
happens, Lock In still checks the *window's title text* for the name of a
listed program before falling back to the guessing model — so `steam.exe`
being on the block list still catches a window titled "Steam" even if we
never learned its process name. If blocking still doesn't seem to be working
at all, check the Blocking tab: if it says "App detection unavailable" (or
you see a red banner about `pywin32`/`psutil` when the app starts), those two
packages aren't installed and nothing can be detected — see Quick start.

### On "spam notifications"

Firing a toast every second is the intuitive read of the idea and the wrong
implementation: it trains you to dismiss notifications, which burns the exact
channel the app depends on, and Windows starts collapsing rapid toasts into
Action Center anyway. So there's one alert per strike interval, each louder
than the last.

### On "stop me from leaving"

Windows has no supported way for an ordinary user-space program to genuinely
prevent app switching — the APIs that could (global input hooks that swallow
Alt-Tab, foreground locks) need elevation, are what malware uses, and can wedge
a machine if the process dies at the wrong moment.

So Lock In enforces through **friction and attention**, not force. It makes
opening Discord annoying and impossible to do absentmindedly, which is the
actual failure mode — nobody deliberately decides to lose forty minutes.

Every escalation rung, including the full-screen lockdown, has a visible exit.
That's deliberate. An app that can trap you is an app you uninstall the first
time it misfires during something that mattered.

---

## The model

`classifier.py` is a multinomial Naive Bayes classifier over the active window
title plus process name, with Laplace smoothing.

**Why titles instead of screenshots.** The original idea was to train a vision
model on screen captures. Titles win on all three axes that matter:

- **Signal.** `"Lecture 12: Pipelining.pdf - Adobe Acrobat"` vs
  `"general #chat - Discord"` — the OS hands you a near-perfect description of
  what you're doing for free. A CNN on raw pixels would burn enormous capacity
  rediscovering text.
- **Cost.** Titles are a handful of tokens once a second. Screenshots are
  megabytes per second through a vision model.
- **Privacy.** Nothing leaves your machine. An app you run *all day while
  working* becomes a very different thing to trust the moment it starts
  shipping screenshots anywhere.

**Why Naive Bayes instead of something bigger.** It trains on 40 examples,
updates online in microseconds, needs zero dependencies, and its per-token
weights are directly inspectable — `model.explain()` tells you a window was
flagged because of `youtube`, `mv`, `official`. When the app's entire job is to
be trusted enough to interrupt you, a black box is a liability.

It ships pre-trained on a 64-example seed corpus so it's useful on first
launch, and every correction is a real online update — the next poll already
uses the new model.

If you *do* want pixels later, the seam is clean: swap in anything that returns
`(label, confidence)` from `judge()` and nothing downstream changes.

---

## Kamen Rider theme

Settings → "Kamen Rider theme" picks from all 38 Rider series (Showa,
Heisei, and Reiwa era), each with its own accent-color pair pulled from
that Rider's actual suit colors. This only changes colors — the Henshin
button, the timer digits/progress bar during a focus block, and a small
"DRIVER: <name>" label — not any copy or behavior. Defaults to the
original 1971 series. See `lock_in/rider_themes.py` for the full palette.

### Look and feel

`lock_in/visuals.py` generates the app's art at runtime with Pillow, tinted
to whichever Rider is picked:

- **A display font** for the timer digits and headings, instead of the
  toolkit's plain default — a different one per OS (`Bahnschrift` on
  Windows, `Avenir Next` on macOS, `Noto Sans` on Linux), falling back
  quietly to the system default if that font isn't installed.
- **A soft glow** behind the timer digits (the Rider's primary color) and
  behind the Henshin button (its secondary color).
- **A faint diagonal-stripe wallpaper** behind the whole window, tinted
  with both of the Rider's colors, with separate light- and dark-mode
  versions so it never fights with the appearance-mode setting.

None of this touches copy or behavior — turn the window into any Rider's
colors and the words stay exactly the same.

---

## Training it

There are three ways in, in increasing order of how much data they get you.

### 1. The correction buttons

The Activity tab logs **every** window seen during a focus block, not just
the ones that got blocked — each row has a colored dot (red = blocked, green
= allowed) and says why. Click **distraction** / **was studying** on any row
to correct it. Writes `model.json` immediately; no retrain step. Correcting
to "was studying" also auto-allow-lists that process, since that's almost
always what you meant.

Because it shows everything, not just flagged windows, you can catch both
kinds of mistake here: something that got wrongly blocked, *and* something
distracting that slipped through as "allowed" — like Steam showing up green
when it should've been red, which tells you the block list or model needs a
correction. For bulk labelling instead of one-off corrections, use `train.py`.

### 2. `train.py` — the real loop

Recording is on by default, so the app logs every distinct window it sees during
focus (not just flagged ones) to `observations.jsonl`. Then:

```bat
python train.py label      :: one keypress each, most-seen windows first
python train.py rebuild    :: fold your labels into the model
python train.py eval       :: check you didn't make it worse
```

`label` shows you the model's current guess and the tokens behind it, so you can
sanity-check before agreeing:

```
[3/47] chrome.exe — Khan Academy linear algebra practice
     seen 22×  ·  model says study (89%)
     signal: khan-, academy-, algebra-, practice-
     > _
```

`s` = study, `d` = distraction, `enter` = accept the guess, `k` = skip,
`q` = quit. Saves after every answer, so quitting halfway loses nothing.

Full command list:

| Command | What it does |
|---|---|
| `record` | Poll and log windows without running Pomodoro blocks |
| `label` | Interactive labelling loop |
| `rebuild` | Retrain from seed + all your labels (`--no-seed` to use yours alone) |
| `stats` | Model size, class balance, most informative tokens |
| `eval` | Hold-out accuracy, per-class precision/recall, vocabulary overlap |
| `test "<title>"` | Predict one string and show why |
| `import <file>` | Bulk import `label,text` rows from CSV/TSV |
| `export <file>` | Dump your labelled data to CSV |
| `purge` | Drop unlabelled observations, keep the labels |

### 3. Bulk import (fastest start)

Writing forty lines in a text editor beats waiting to encounter forty apps:

```csv
label,text
d,"Ryujinnie bot server - Discord discord.exe"
d,"F1 2026 Silverstone highlights - YouTube chrome.exe"
s,"ECE 232 Lecture 9 pipelining.pdf sumatrapdf.exe"
s,"Overleaf honors thesis draft - Google Chrome chrome.exe"
```

```bat
python train.py import mine.csv && python train.py rebuild
```

Or edit `SEED_DATA` in `classifier.py` directly, if you want your examples to
ship with the app rather than live in your profile.

### Reading `eval` honestly

```
Accuracy:              81.8%
distraction   precision 90.5%   recall 77.3%
study         precision 80.0%   recall 90.3%
Vocabulary overlap:    41%
```

**Overlap is the number to watch first.** It's the share of test-title words the
model had seen before. Below ~60%, the model is guessing on vocabulary it has
never encountered, and no amount of threshold tuning fixes that — you just need
more labelled windows. `eval` says so explicitly when it detects this.

**Accuracy alone is misleading**, which is why it's not reported alone. During
development an earlier configuration scored *higher* accuracy (63% vs 59%) while
flagging 70% of legitimate work — high distraction recall, catastrophic study
recall. It looked better and was unusable. The per-class split is what caught it.
The two fixes that followed (skipping out-of-vocabulary tokens, and dropping
browser boilerplate like `chrome`/`google` from the tokenizer) traded a little
accuracy for balance, then thickening the seed corpus took accuracy to 82%.
The ablation is documented in the comments in `classifier.py`.

Rough guide:

- **Low distraction recall** → it's missing things. Label more distraction
  examples, or lower `classifier_threshold` in `config.json`.
- **Low study precision** → it's interrupting you while you work. Label more
  study examples, or raise the threshold.
- **Low overlap** → neither. Collect more data.

Until the model has a few hundred examples, the block and allow lists carry the
real load — they're exact matches and need no training at all.

## Claude fallback (optional, off by default)

A fourth tier, behind everything else:

```
allowlist  →  blocklist  →  Naive Bayes (confident)  →  Claude  →  allowed
```

When the local model has no confident opinion — confidence below
`classifier_threshold` either way — that's the genuinely ambiguous case Claude
exists for. Confidently-judged windows (the vast majority) never touch it.

### Setup

**1. Get an API key.** [console.anthropic.com](https://console.anthropic.com) →
Settings → API Keys → Create Key. Copy it immediately; you can't view it again.

**2. Set it as an environment variable — never in a file.**

```powershell
[System.Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', 'your-key-here', 'User')
```

Or Windows Settings → search "environment variables" → Edit environment
variables for your account → New. Restart any open terminal or VS Code window
afterward.

**3. Install the SDK.**

```bat
pip install anthropic
```

**4. Turn it on.** Blocking tab → "Enable Claude fallback for ambiguous
windows". The status line underneath tells you immediately if something's
missing (`no ANTHROPIC_API_KEY environment variable found`,
`anthropic package not installed`, or `ready (claude-haiku-4-5-20251001)`).

The model is `claude-haiku-4-5-20251001` — fast and cheap, which is what
"study or distraction" needs. Not user-configurable from the UI on purpose;
edit `Config.claude_model` in `config.json` if you want a different one.

### What actually gets sent

One string: the window title plus process name, e.g.
`"Overleaf thesis draft - Google Chrome chrome.exe"`. Nothing else — no
history, no other window titles, no identifying information. `test_judge_sends_only_the_window_text`
in `tests/test_claude_fallback.py` pins this down so a future edit can't
accidentally widen it.

### How it stays out of the way

- **Non-blocking.** The enforcer polls once a second; an API call is never
  fast enough to sit in that loop. `judge()` only ever peeks an in-memory
  cache — a dict read. On a cache miss, `ui.py` fires a background thread and
  uses the local model's answer for *that* poll. Since a window you're on for
  one second is usually still open a second later, the real answer is
  typically ready by the next poll.
- **Cached per session.** Same ambiguous title won't be billed twice within
  `claude_cache_minutes` (default 30).
- **Teaches the local model.** Every real answer is folded into
  `observations.jsonl` as a labelled example — same mechanism `train.py` uses.
  Run `python train.py rebuild` afterward and the local model absorbs it,
  needing Claude less over time.
- **Fails silent, not broken.** No key, no package, rate-limited, network
  down, malformed reply — all of it degrades to "no opinion, allow it," never
  a crash. A misconfigured key can't turn into a broken Pomodoro timer.

## Project structure

```
Lock In/
│
├── main.py                     Entry point. Checks dependencies, launches the UI.
├── train.py                    Training CLI (record / label / rebuild / eval / …).
│
├── lock_in/                    The application package.
│   ├── __init__.py             Marks this folder as a package.
│   │
│   │   ── pure logic, stdlib only, fully unit-tested ──
│   ├── config.py               Settings dataclass, JSON persistence, block/allow
│   │                           defaults, and the %APPDATA% path resolution.
│   ├── session.py              Pomodoro state machine. Injectable clock, so tests
│   │                           run four-hour sessions instantly.
│   ├── classifier.py           Naive Bayes study/distraction model, tokenizer,
│   │                           seed corpus, explain(), JSON persistence.
│   ├── enforcer.py             judge() applies allowlist → blocklist → model.
│   │                           Enforcer() runs the strike/escalation ladder.
│   ├── observations.py         Records every window seen during focus and tracks
│   │                           which have been labelled. Backs train.py.
│   ├── rider_themes.py         Kamen Rider color palettes for the theme toggle.
│   ├── visuals.py               Display font pick, plus Pillow-generated glow
│   │                           and background art, tinted by the Rider theme.
│   │
│   │   ── platform-facing shells, thin by design ──
│   ├── monitor.py              Foreground-window polling on a daemon thread.
│   │                           Win32 backend, macOS (osascript), Linux (xdotool).
│   ├── notifier.py             Toasts and sounds: winotify/winsound (Windows),
│   │                           osascript/afplay (macOS), notify-send/paplay (Linux).
│   └── ui.py                   CustomTkinter front end. The only module that
│                               imports tkinter.
│
├── tests/
│   ├── test_session.py         State machine: transitions, pause, skip, formatting,
│   │                           and the serious-tokusatsu phase labels.
│   ├── test_classifier.py      Tokenizer, prediction, online learning, persistence.
│   ├── test_enforcer.py        Rule precedence, full escalation ladder, decay,
│   │                           notification copy, cross-platform process matching.
│   ├── test_observations.py    De-duplication, labelling, JSONL round-trip.
│   ├── test_claude_fallback.py Caching, async lookup, failure handling — no
│   │                           real network calls, a fake client stands in.
│   ├── test_rider_themes.py    Palette completeness, color validity, dark-mode
│   │                           shade generation.
│   ├── test_visuals.py         Font lookup, glow shape/fade, background contrast
│   │                           between light and dark mode.
│   └── smoke_ui.py             Headless end-to-end run under Xvfb (not pytest).
│
├── .github/workflows/
│   ├── tests.yml               Runs pytest on Windows, macOS, and Linux on every push.
│   └── release.yml             Builds and publishes installers on a version tag.
│
├── requirements.txt
├── pytest.ini
├── run.bat                     Launches with pythonw (no console window).
└── build.bat                   PyInstaller one-file build.
```

Runtime data lives outside the project, in `%APPDATA%\Lock In\`:

```
config.json          your settings
model.json           the trained classifier — readable, worth opening once
observations.jsonl   every window seen during focus, one JSON object per line
```

### Why it's split this way

The five "pure logic" modules import nothing outside the standard library. No
tkinter, no Win32, no network. That's what makes the unit test suite (run
`pytest` to see the current count) run in a fraction of a second with no
display server — and it means the escalation policy, the model,
and the state machine can all be reasoned about without booting a GUI.
`claude_fallback.py` sits just outside that boundary — it needs the `anthropic`
package and, when enabled, the network — but its own tests never make a real
call; a fake client swapped into `_client` exercises every branch offline.

Everything platform-specific is pushed into `monitor.py`, `notifier.py`, and
`ui.py`, which are deliberately thin: they perform actions and marshal data, but
make no decisions. `enforcer.py` decides that a window warrants `Action.MINIMIZE`;
`ui.py` just calls the minimise function.

**Threading.** `ActiveWindowMonitor` polls on a background daemon thread.
Tkinter is not thread-safe, so that thread does exactly one thing:
`queue.put(window_info)`. The UI thread drains the queue from an `after()` loop
and does all judging, enforcement, and widget updates. Nothing else crosses the
boundary.

```bat
pytest                                   :: runs the unit test suite
xvfb-run -a python tests/smoke_ui.py     :: end-to-end, needs a display
```

## Config

Settings, the trained model, and your training data all live in
`%APPDATA%\Lock In\` — outside the project directory, so a PyInstaller build
(where the app folder may be read-only) still writes correctly.

| File | What it is |
|---|---|
| `config.json` | Every setting, pretty-printed and hand-editable |
| `model.json` | The trained classifier — plain counts, worth opening once |
| `observations.jsonl` | Windows seen during focus, one JSON object per line |

Deleting any of them regenerates it. Deleting `model.json` costs you nothing if
your labels are still in `observations.jsonl` — just run `python train.py
rebuild`. Deleting `observations.jsonl` is the one that actually loses work, so
`train.py export` it first if you've put real time into labelling.

Recording can be switched off entirely (Blocking tab → "Record windows for
training"). Nothing ever leaves your machine either way — except, if you've
opted into it, the Claude fallback's ambiguous-window titles (see above).

`ANTHROPIC_API_KEY` lives in your OS environment, never in any of these files.
`config.json` only stores whether the fallback is *enabled* and which model to
use — never the key itself.

## Known limits

- **Windows, macOS, and Linux are all supported**, though Windows has the
  most mileage. macOS minimizing simulates Cmd+M via System Events, which
  needs Accessibility permission — macOS prompts for it the first time
  blocking tries to act. Linux detection and minimizing need `xdotool`
  installed and an X11 session — there's no Wayland equivalent, so
  blocking silently can't minimize windows under Wayland (detection still
  works). Toasts and sounds use `notify-send`/`paplay`/`aplay` on Linux
  and `osascript`/`afplay` on macOS, falling back to the in-app banner if
  those tools aren't present, exactly like the Windows toast falls back
  when `winotify` isn't installed.
- **Browser tabs are one window.** The title tells you the *active* tab, so a
  YouTube tab sitting in the background won't be flagged. Catching that needs a
  browser extension, which is a separate build.
- **Nothing survives task-killing the app.** By design.
- **The model needs data before it's much use.** Out of the box it knows the
  seed corpus and not your habits. The block and allow lists work perfectly from
  minute one; the classifier is the part that earns its keep over a few weeks.

## Releases

Tagged releases (`vX.Y.Z`) are built automatically for Windows, macOS,
and Linux via GitHub Actions and published to
[Releases](https://github.com/SVerma2696/lock-in/releases) — download the
one for your OS rather than building from source. Every push and pull
request also runs the test suite on all three OSes
(`.github/workflows/tests.yml`); a release only builds on a version tag
(`.github/workflows/release.yml`).

The macOS build isn't code-signed or notarized, so Gatekeeper will call it
from an "unidentified developer" the first time you open it — right-click
→ Open once to bypass that.

## License

MIT — see [LICENSE](LICENSE).