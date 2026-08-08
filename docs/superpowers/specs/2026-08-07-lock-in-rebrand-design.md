# Lock In: rebrand, Kamen Rider theming, cross-platform parity, and release CI

Date: 2026-08-07
Status: Approved by user, ready for implementation plan

## Goal

Rename "FocusLock" to "Lock In", reskin its copy with a serious tokusatsu
(Kamen Rider) tone, add a toggleable Kamen Rider color theme (38 series),
bring macOS/Linux up to real feature parity with Windows, and add a
tag-triggered GitHub Actions release pipeline that builds installers for
all three OSes.

Repo the CI will target: `https://github.com/SVerma2696/lock-in` (user will
create the local git repo, remote, and all pushes/tags themselves — this
implementation does not run any git commands).

## 1. Identity / rename

- App name everywhere: **Lock In** (was FocusLock).
- Python package: `pomodoro_lock/` → `lock_in/`. Update every import in
  `main.py`, `train.py`, all of `tests/*.py`.
- `FocusLockApp` class → `LockInApp`.
- `Config.APP_NAME` → `"Lock In"`, so `%APPDATA%\Lock In\` (Windows),
  `~/Library/Application Support/Lock In/` (macOS),
  `~/.config/Lock In/` (Linux, or `$XDG_CONFIG_HOME`).
- `notifier.Notifier`'s default `app_name` param → `"Lock In"`.
- Built binaries: `Lock In.exe` (Windows), `Lock In.app` (macOS),
  `Lock In` (Linux ELF binary).
- Self-window exclusion check in `ui.py` (`_drain_window_queue`) matches on
  `"lock in"` (lowercase) instead of `"focuslock"`.
- `classifier.py` SEED_DATA and `tests/test_classifier.py` fixture strings
  that reference the dev's own editor title (`"... - focuslock - Visual
  Studio Code code.exe"`) get updated to `"... - lock_in - ..."` to match
  the renamed folder.
- `build.bat`, `run.bat`, `.gitignore`, `README.md`: every "FocusLock"
  string and the project-structure tree updated.

## 2. Tone: serious, not playful

Phase labels (`session.py` `Phase.label`):

| Phase | Old | New |
|---|---|---|
| IDLE | Ready | Standing By |
| FOCUS | Focus | Henshin |
| SHORT_BREAK | Short Break | Recovery |
| LONG_BREAK | Long Break | Stand Down |

Main toggle button: `"Start"` → `"Henshin"`. Pause stays `"Pause"`.

Phase-transition banners (`ui.py` `_on_phase_started`):
- Focus start: `"Henshin initiated. Blocking is active."`
- Short break: `"Recovery underway — {remaining} remaining."`
- Long break: `"Stand down — {remaining} remaining. Full recovery earned."`

Escalation notification copy (`enforcer.py` `MESSAGES`):

| Action | Title | Body |
|---|---|---|
| WARN | Off Mission | `{app} is not part of the mission. {time} remains in this Henshin block.` |
| NAG | Repeated Violation | `{seconds}s on {app}. {time} until the mission ends — hold the line.` |
| MINIMIZE | Window Neutralized | `{app} minimized. {time} remaining. This was your directive.` |
| LOCKDOWN | Full Lockdown | `Screen sealed for {lockdown}s. Recover, then resume the mission.` |

Lockdown fullscreen (`ui.py` `_show_lockdown`): big label
`"LOCKDOWN ENGAGED."`, subtext `"{remaining} left in this mission."`,
countdown text unchanged (`"unlocks in {n}s"`), exit button
`"Abort Mission"`.

Streak label: `"{n} missions complete · Full Recovery in {m}"`.

Functional/error copy (dependency warnings, "App detection unavailable")
stays plain English — clarity over theme when something's actually broken.

Enum *values* (`Action.WARN = "warn"`, `Reason.CLASSIFIER = "classifier"`,
`STUDY = "study"`, `DISTRACTION = "distraction"`, `Phase.FOCUS = "focus"`)
are internal identifiers persisted in `config.json`/`model.json` and are
**not** renamed — only the human-facing `.label` strings and UI copy change.

## 3. Kamen Rider theme toggle

- Color-palette-only: each Rider defines one **primary** hex (drives the
  Henshin/focus color — timer digits, progress bar, phase label, and the
  Henshin button) and one **secondary** hex (button border/hover accent,
  and a small `"DRIVER: <name>"` label under the header). All other colors
  (break green, danger red, tab accents) stay constant across themes.
- New module `lock_in/rider_themes.py`: an ordered dict
  `RIDER_THEMES: dict[str, RiderTheme]` keyed by display name (e.g.
  `"Kamen Rider (1971)"`), each holding `era`, `year`, `primary` (single
  hex), `secondary` (single hex). A `lighten(hex, factor)` helper derives
  the dark-mode-friendly variant at load time instead of hand-picking 76
  shades — each theme stores exactly one hex per role.
- `Config` gains `rider_theme: str = "Kamen Rider (1971)"`.
- Settings tab gains a new dropdown ("Kamen Rider theme") next to
  Appearance, listing all 38 names in era order. Changing it saves config,
  recomputes the two dynamic colors, and rebuilds the tabs/header (same
  pattern as the existing appearance-change handler).
- Default on first launch: **Kamen Rider (1971)**.

### Final palette (source of truth — user-corrected)

| Rider (year) | Primary | Secondary |
|---|---|---|
| Kamen Rider (1971) | `#1b5e3a` | `#c0392b` |
| V3 (1973) | `#2e7d32` | `#c0392b` |
| X (1974) | `#cfd8dc` | `#1565c0` |
| Amazon (1974) | `#33691e` | `#e65100` |
| Stronger (1975) | `#c62828` | `#212121` |
| Skyrider (1979) | `#2e7d32` | `#8d6e63` |
| Super-1 (1980) | `#e0e0e0` | `#212121` |
| ZX (1982) | `#c62828` | `#b0bec5` |
| Black (1987) | `#1a1a1a` | `#00c853` |
| Black RX (1988) | `#2e7d32` | `#1a1a1a` |
| Kuuga (2000) | `#c1272d` | `#212121` |
| Agito (2001) | `#ffca28` | `#212121` |
| Ryuki (2002) | `#c62828` | `#9e9e9e` |
| 555 / Faiz (2003) | `#111111` | `#d50000` |
| Blade (2004) | `#1565c0` | `#b0bec5` |
| Hibiki (2005) | `#4a148c` | `#c62828` |
| Kabuto (2006) | `#c62828` | `#90a4ae` |
| Den-O (2007) | `#c62828` | `#eceff1` |
| Kiva (2008) | `#8e0000` | `#ffca28` |
| Decade (2009) | `#d81b60` | `#212121` |
| W / Double (2009) | `#2e7d32` | `#1a1a1a` |
| OOO (2010) | `#1a1a1a` | `#c62828` |
| Fourze (2011) | `#ffffff` | `#ef6c00` |
| Wizard (2012) | `#c62828` | `#212121` |
| Gaim (2013) | `#ef6c00` | `#c9a227` |
| Drive (2014) | `#c62828` | `#212121` |
| Ghost (2015) | `#1a1a1a` | `#ff9800` |
| Ex-Aid (2016) | `#e91e63` | `#00e676` |
| Build (2017) | `#c62828` | `#1565c0` |
| Zi-O (2018) | `#212121` | `#d81b60` |
| Zero-One (2019) | `#aeea00` | `#1a1a1a` |
| Saber (2020) | `#c62828` | `#212121` |
| Revice (2021) | `#e91e63` | `#00e5ff` |
| Geats (2022) | `#ffffff` | `#c62828` |
| Gotchard (2023) | `#00bcd4` | `#ff9800` |
| Gavv (2024) | `#7b1fa2` | `#fbc02d` |
| Zeztz (2025) | `#2e7d32` | `#1a1a1a` |
| MY-TH (2026) | `#1565c0` | `#b0bec5` |

Tie-breaks resolved where the user's source data listed more than two
colors for a single role (presented back to the user; no objection
raised, proceeding as proposed):
- **OOO**: secondary Red `#c62828` (dropped yellow/green — red reads
  clearly against the black primary).
- **Fourze**: secondary Orange `#ef6c00` (dropped black — black is
  already the de facto neutral elsewhere; orange gives real contrast
  against the white primary).
- **Zi-O**: secondary Magenta `#d81b60` (dropped silver, per the
  table's stated secondary).
- **Den-O**: secondary White `#eceff1` (first-named of "White/Black").
- **Saber**: secondary Black `#212121` (first-named of "Black/White").
- **Geats**: secondary Red `#c62828` (first-named of "Red/Black").

## 4. Cross-platform parity

**`monitor.py`:**
- Linux: add PID lookup (`xdotool getactivewindow getpid`) → `psutil.Process(pid).name()`
  so block/allow-list matching by process name works there (today Linux
  only returns a title, no process name).
- Minimize: Windows unchanged (`win32gui.ShowWindow`). macOS: simulate
  Cmd+M via `osascript` System Events keystroke on the frontmost app
  (requires Accessibility permission — first use triggers the OS prompt).
  Linux: `xdotool getactivewindow windowminimize` (X11 only; no Wayland
  equivalent — documented as a known limitation, not solved).

**Bug fix (uncovered while doing this):** block/allow lists are stored
with a `.exe` suffix (`"discord.exe"`). On macOS/Linux the detected
process name has no `.exe`, so exact-match blocking silently never fires
there today (only the title-substring fallback catches it, and only when
process name is empty). Fix: strip a trailing `.exe` from both sides
before comparing in `enforcer.judge()`, so one block/allow list works
unmodified across all three OSes.

**`notifier.py`:** add a macOS branch (`osascript -e 'display
notification'` for toasts, `afplay` against a bundled system sound for
the alert cue) and a Linux branch (`notify-send` for toasts, `paplay`/
`aplay` for sound), each gated behind `shutil.which(...)` and wrapped in
try/except — same "never crash, fall back to the in-app banner" contract
as the existing Windows path.

**Known caveat:** this is written on a Windows machine per each OS's
documented mechanism, but not run on macOS/Linux — needs real
verification on those OSes before being trusted in production.

## 5. CI/CD

Two workflow files under `.github/workflows/`:

1. **`tests.yml`** — triggers on push and pull_request. Matrix:
   `windows-latest`, `macos-latest`, `ubuntu-latest`. Installs
   `requirements.txt`, runs `pytest`. Catches cross-platform breakage on
   every push at effectively no cost (the suite runs in a fraction of a
   second).
2. **`release.yml`** — triggers only on tags matching `v*.*.*`. Matrix
   builds a PyInstaller binary per OS (`--onefile --windowed --name "Lock
   In"`, with `--hidden-import` for the three win32 modules added only on
   the Windows leg), zips/tars each into `LockIn-Windows.zip`,
   `LockIn-macOS.zip`, `LockIn-Linux.tar.gz`, uploads as build artifacts.
   A final `publish` job (depends on the matrix, runs once on
   `ubuntu-latest`) downloads all three artifacts and runs
   `gh release create "$TAG" ... --generate-notes` using the **preinstalled
   `gh` CLI** and the default `GITHUB_TOKEN` — no third-party marketplace
   action, no secrets to configure, `permissions: contents: write` set on
   the job.

macOS builds are not code-signed or notarized (needs a paid Apple
Developer account, out of scope) — users will see an "unidentified
developer" Gatekeeper warning on first run. Documented in the README, not
solved.

## 6. Explicitly out of scope for this pass

- Any git/GitHub action taken by the assistant (init, commit, push, tag,
  remote, repo creation). The user does all of that themselves; the final
  deliverable includes the exact commands to run.
- Code-signing/notarizing the macOS build.
- Wayland support for Linux minimize.
- Per-Rider unique copy/catchphrases (theme is colors only, per the
  approved design).

## 7. File-by-file change list

- Rename `pomodoro_lock/` → `lock_in/` (all files inside get import-path
  and copy updates as described above).
- New: `lock_in/rider_themes.py`.
- New: `.github/workflows/tests.yml`, `.github/workflows/release.yml`.
- Edit: `main.py`, `train.py`, `build.bat`, `run.bat`, `.gitignore`,
  `README.md`, all of `tests/*.py`.
- Edit inside the renamed package: `__init__.py`, `config.py`,
  `session.py`, `enforcer.py`, `monitor.py`, `notifier.py`, `ui.py`,
  `classifier.py` (SEED_DATA self-reference strings only).
