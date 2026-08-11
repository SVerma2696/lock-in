"""
ui.py
=====
This file draws the actual window you see and click on. It's the only file
in the whole app that touches the screen-drawing toolkit directly.

How the background thread and the screen work together (important!)
-------------------------------------------------------------------------
`ActiveWindowMonitor` checks your active window on its own background
thread. The screen-drawing toolkit isn't safe to touch from another thread,
so that background thread does exactly one simple thing:
`queue.put(window_info)` — it drops the info into a safe waiting line. The
main screen thread picks things up from that line on a timer loop, and it's
the only place that makes decisions or updates anything you see.

What the window looks like
------------------------------
    ┌───────────────────────────────┐
    │ banner (short pop-up message) │
    ├───────────────────────────────┤
    │  FOCUS                        │
    │        24:31                  │
    │  ▓▓▓▓▓░░░░░░░░░░░░            │
    │  [Start] [Skip] [Reset]       │
    ├───────────────────────────────┤
    │ Timer │ Blocking │ Activity │ Settings │
    └───────────────────────────────┘
"""

from __future__ import annotations

import queue
import sys
import time
from datetime import datetime
from typing import List, Optional

import customtkinter as ctk
from PIL import ImageTk

from .classifier import DISTRACTION, STUDY, NaiveBayesClassifier
from .claude_fallback import ClaudeFallback
from .config import Config, MODEL_PATH, OBSERVATIONS_PATH, app_data_dir
from .observations import ObservationStore
from .enforcer import Action, Enforcer, Reason, WindowInfo, judge, lockdown_label_for, message_for
from .monitor import BACKEND_AVAILABLE, ActiveWindowMonitor, minimize_window
from .notifier import Notifier
from .session import Event, Phase, PomodoroSession, label_for
from .rider_themes import DEFAULT_RIDER_THEME, RIDER_THEMES
from .visuals import (
    SHAPE_EFFECTS,
    apply_tier1_background_effect,
    display_font_family,
    ease_drive_progress,
    interpolate_agito_color,
    load_app_icon,
    make_background_texture,
    make_glow,
    make_panel_divider,
    render_progress,
)

# Our color choices, kept in one spot — so changing the theme means
# changing a few lines here, not hunting through the whole file.
# (The focus color isn't here anymore — it now comes from whichever
# Kamen Rider is picked in Settings. See _apply_rider_theme.)
COLOR_BREAK = "#2f9e5f"      # green — means it's okay to relax
COLOR_IDLE = "#5a6472"
COLOR_WARN = "#e0a800"
COLOR_DANGER = "#c0392b"

# A few extra accent colors, so each tab/section has its own bit of
# personality instead of everything being the same grey. Each one is a
# (light-mode color, dark-mode color) pair — CustomTkinter automatically
# picks the right half depending on which theme is active, so these stay
# easy to read no matter which mode you're in.
COLOR_BLOCKING_ACCENT = ("#c2255c", "#ff6b9d")   # rose pink — Blocking tab
COLOR_ACTIVITY_ACCENT = ("#e8590c", "#ffa94d")   # orange — Activity tab
COLOR_TIMER_ACCENT = ("#1c7ed6", "#4dabf7")      # blue — timer-length settings
COLOR_ENFORCE_ACCENT = ("#e03131", "#ff8787")    # red — enforcement settings
COLOR_LOOK_ACCENT = ("#0ca678", "#63e6be")       # teal — sound/notification/look settings
COLOR_CLAUDE_ACCENT = ("#9c36b5", "#e599f7")     # purple — the Claude fallback feature

# The nicer-looking font for the timer digits and headings. Picked once
# per computer in visuals.py — see that file for why.
DISPLAY_FONT = display_font_family()

# The background wallpaper picture is made bigger than the window's
# starting size, so shrinking the window down never looks blurry — only
# growing it a lot past this would.
BG_TEXTURE_WIDTH = 900
BG_TEXTURE_HEIGHT = 1200

# The thin strip between the timer panel and the tab panel. Made wider
# than the window starts at, same reasoning as the background above.
DIVIDER_WIDTH = 900
DIVIDER_HEIGHT = 14

# The size of the picture used for the 4 Tier 1 Riders with their own
# custom progress SHAPE (windmill, rising bar, constellation, vials).
# Fixed on purpose -- unlike the background/divider above, this picture
# doesn't stretch when you resize the window, it just stays centered.
PROGRESS_SHAPE_WIDTH = 340
PROGRESS_SHAPE_HEIGHT = 48


class LockInApp(ctk.CTk):
    """The main app window — everything you see lives inside this."""

    UI_TICK_MS = 200      # how often we redraw the countdown, in milliseconds
    BANNER_MS = 6000      # how long a pop-up banner stays on screen, in milliseconds

    def __init__(self) -> None:
        super().__init__()

        # ---------------- The main pieces of the app -------------------- #
        self.config_obj = Config.load()
        # The session has to exist BEFORE _apply_rider_theme(), because
        # that method now also has to check what phase we're in (for
        # Stronger/Kiva's Tier 1 background effect).
        self.session = PomodoroSession(self.config_obj)
        self._apply_rider_theme()
        self.model = NaiveBayesClassifier.load(MODEL_PATH)
        self.observations = ObservationStore(OBSERVATIONS_PATH)
        self.claude = ClaudeFallback(self.config_obj)
        self.enforcer = Enforcer(self.config_obj)
        self.notifier = Notifier(self.config_obj)
        self.notifier.banner_callback = self._queue_banner

        # Safe mailboxes for passing messages between threads.
        self._window_queue: "queue.Queue[WindowInfo]" = queue.Queue()
        self._banner_queue: "queue.Queue[tuple]" = queue.Queue()
        self._claude_queue: "queue.Queue[tuple]" = queue.Queue()

        self.monitor = ActiveWindowMonitor(
            callback=self._window_queue.put,   # safe to call from any thread — does nothing fancy
            interval=1.0,
        )

        # The activity list: dicts of {time, text, blocked, reason, label}
        self.activity: List[dict] = []
        self._lockdown_window: Optional[ctk.CTkToplevel] = None
        self._banner_after_id: Optional[str] = None

        # ---------------- The window frame ------------------------------ #
        ctk.set_appearance_mode(self.config_obj.appearance)
        ctk.set_default_color_theme(self.config_obj.accent)

        self.title("Lock In")
        self.geometry("560x720")
        self.minsize(500, 640)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_app_icon()

        # This picture sits behind absolutely everything else. It has to
        # be made FIRST, before any other button or label — in this
        # screen-drawing toolkit, whatever gets made first sits at the
        # very back, like the bottom of a stack of papers.
        self._bg_label = ctk.CTkLabel(self, text="", image=self._bg_image)
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        # Whenever you resize the window, stretch the picture to match —
        # otherwise it would stay one fixed size and leave a bare edge.
        self.bind("<Configure>", self._on_window_resized)

        self._build_header()
        self._build_divider()
        self._build_tabs()

        self.monitor.start()
        self._sync_progress_widget_visibility()
        self._pump()          # start the UI heartbeat
        self._refresh_timer_widgets()
        # Wait a moment before showing this, so the window is fully drawn
        # and visible first — a banner on a window that isn't on screen yet
        # would just be missed.
        self.after(400, self._warn_if_app_detection_unavailable)

    def _set_app_icon(self) -> None:
        """
        Puts the app's own picture in the title bar and the taskbar.

        If the picture is missing or broken, `load_app_icon()` just
        gives back `None` instead of raising an error — so we quietly
        skip this and the window keeps the toolkit's plain default
        icon instead of crashing.
        """
        icon = load_app_icon()
        if icon is None:
            return
        # Tkinter only understands its own kind of picture object, so we
        # convert to that here. We also keep a copy on `self` — if we
        # didn't, the toolkit could throw the picture away too early and
        # the icon would quietly vanish a moment after it appeared.
        self._icon_image = ImageTk.PhotoImage(icon)
        self.iconphoto(True, self._icon_image)

        # Windows' own title bar and taskbar don't reliably pick up the
        # picture from the line above -- on Windows specifically, they
        # need a real ".ico" file handed to them a different way. We
        # save one, once, in the app's own settings folder (the same
        # place config.json lives), so we're not trying to write into
        # the program's own install folder, which might not be allowed.
        if sys.platform == "win32":
            try:
                ico_path = app_data_dir() / "app_icon.ico"
                if not ico_path.exists():
                    icon.save(
                        ico_path, format="ICO",
                        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
                    )
                self.iconbitmap(default=str(ico_path))
            except Exception:
                pass

    # ================================================================== #
    # Picking words: "professional" (the normal voice) or "tokusatsu"
    # (the Kamen Rider-flavored voice you turn on in Settings)
    # ================================================================== #
    def _is_tokusatsu(self) -> bool:
        return self.config_obj.terminology == "tokusatsu"

    def _henshin_word(self) -> str:
        """What the main Start/Henshin button says when it's not running."""
        return "Henshin" if self._is_tokusatsu() else "Start"

    def _rider_row_label_text(self) -> str:
        """What the color-theme picker's row is called in Settings."""
        return "Kamen Rider theme" if self._is_tokusatsu() else "Color theme"

    def _apply_rider_theme(self) -> None:
        """
        Look up which Kamen Rider is picked in settings, and remember
        that Rider's two colors so the rest of the app can use them.

        Also redraws the three Rider-colored pictures (the background
        wallpaper, and the two soft glows) to match. The very first time
        this runs, the pictures don't exist yet, so we make brand-new
        ones; every time after that (when you pick a different Rider),
        we just update the ones already on screen instead.

        If we don't understand the saved name for some reason, we just
        use the first Rider instead of crashing.
        """
        theme = RIDER_THEMES.get(
            self.config_obj.rider_theme, RIDER_THEMES[DEFAULT_RIDER_THEME]
        )
        self.color_focus = theme.primary_pair
        self.color_rider_accent = theme.secondary_pair
        # A panel-background color tinted by the Rider's primary color —
        # pale in light mode, near-black in dark mode, same hue either
        # way. This is what makes the header and tabs themselves change
        # color, not just a button and a label.
        self.color_surface = theme.surface_pair
        # These are for WORDS specifically, not fills or bars — they're
        # always readable on top of whatever they're meant to sit on,
        # even for a Rider whose own color is almost white or almost
        # black. Without these, a Rider like Fourze (pure white) would
        # have text that's the exact same color as its own background —
        # invisible.
        self.color_focus_text = theme.primary_text_pair
        self.color_driver_text = theme.secondary_text_pair
        self.color_button_text = theme.button_text_pair
        # The lockdown screen's cover is always dark, no matter which
        # appearance mode you're in, so its words just need to always be
        # bright — one plain color, not a light/dark pair. The dark-mode
        # half of primary is already hand-picked to pop against a dark
        # background, so it's used as-is here, no extra lightening.
        self.color_lockdown_text = theme.primary[1]
        # Which era this Rider is from (Showa/Heisei/Reiwa) — this also
        # picks the notification wording, the lockdown screen's big
        # words, the background pattern shape, and the sound cues.
        self.current_era = theme.era

        # Which Tier 1 gimmick (if any) this Rider has, and the two
        # (light, dark) color pairs some of those gimmicks need directly
        # (not the text/surface pairs above -- Agito's color shift and
        # Stronger's glow both work from the Rider's real colors).
        self.current_tier1_effect = theme.tier1_effect
        self.rider_primary_pair = theme.primary
        self.rider_secondary_pair = theme.secondary
        # Stronger's glow uses the Rider's own primary (already a red);
        # Kiva's night wash uses the secondary (the amber gold). Every
        # other Rider never reads this, so the value doesn't matter for them.
        self.color_tier1_effect_pair = (
            theme.primary if theme.tier1_effect == "border_glow" else theme.secondary
        )

        primary_light, primary_dark = theme.primary
        secondary_light, secondary_dark = theme.secondary
        timer_glow_light = make_glow(300, 120, primary_light)
        timer_glow_dark = make_glow(300, 120, primary_dark)
        button_glow_light = make_glow(170, 70, secondary_light)
        button_glow_dark = make_glow(170, 70, secondary_dark)
        bg_dark = make_background_texture(
            BG_TEXTURE_WIDTH, BG_TEXTURE_HEIGHT, primary_dark, secondary_dark,
            dark=True, era=theme.era,
        )
        bg_light = make_background_texture(
            BG_TEXTURE_WIDTH, BG_TEXTURE_HEIGHT, primary_light, secondary_light,
            dark=False, era=theme.era,
        )
        divider_light = make_panel_divider(
            DIVIDER_WIDTH, DIVIDER_HEIGHT, primary_light, secondary_light, era=theme.era,
        )
        divider_dark = make_panel_divider(
            DIVIDER_WIDTH, DIVIDER_HEIGHT, primary_dark, secondary_dark, era=theme.era,
        )
        # Keep the PLAIN pattern around separately from whatever ends up
        # on screen -- Stronger/Kiva's effect gets painted fresh on top
        # of this every tick, so we always need the untouched original
        # to start from, not last tick's already-tinted result.
        self._base_bg_dark = bg_dark
        self._base_bg_light = bg_light

        if hasattr(self, "_timer_glow_image"):
            self._timer_glow_image.configure(light_image=timer_glow_light, dark_image=timer_glow_dark)
            self._button_glow_image.configure(light_image=button_glow_light, dark_image=button_glow_dark)
            self._bg_image.configure(light_image=bg_light, dark_image=bg_dark)
            self._divider_image.configure(light_image=divider_light, dark_image=divider_dark)
        else:
            self._timer_glow_image = ctk.CTkImage(
                light_image=timer_glow_light, dark_image=timer_glow_dark, size=(300, 120)
            )
            self._button_glow_image = ctk.CTkImage(
                light_image=button_glow_light, dark_image=button_glow_dark, size=(170, 70)
            )
            self._bg_image = ctk.CTkImage(
                light_image=bg_light, dark_image=bg_dark,
                size=(BG_TEXTURE_WIDTH, BG_TEXTURE_HEIGHT),
            )
            self._divider_image = ctk.CTkImage(
                light_image=divider_light, dark_image=divider_dark,
                size=(DIVIDER_WIDTH, DIVIDER_HEIGHT),
            )

        # Re-apply Stronger/Kiva's effect (if this Rider has one) right
        # away -- otherwise switching themes mid-focus-block would show
        # the plain, untinted background for a moment.
        self._refresh_background_effect(self.session.progress)

    def _refresh_background_effect(self, progress_fraction: float) -> None:
        """
        Redraw the background picture's Stronger-glow or Kiva-wash (if
        this Rider has one) and push it onto the picture already on
        screen. Both effects only show up DURING a focus block and
        disappear the moment it ends -- that's what `in_focus` is for.
        Riders without either effect just get the plain picture back,
        unchanged.
        """
        in_focus = self.session.phase is Phase.FOCUS
        active_effect = self.current_tier1_effect if in_focus else "none"
        effect_color_light, effect_color_dark = self.color_tier1_effect_pair
        bg_light = apply_tier1_background_effect(
            self._base_bg_light, active_effect, effect_color_light, progress_fraction,
        )
        bg_dark = apply_tier1_background_effect(
            self._base_bg_dark, active_effect, effect_color_dark, progress_fraction,
        )
        self._bg_image.configure(light_image=bg_light, dark_image=bg_dark)

    def _on_window_resized(self, event) -> None:
        """
        Stretch the background picture to match whenever the window
        changes size.

        This fires a LOT while you're actively dragging the window's
        edge, so we skip the work unless the size actually changed —
        otherwise we'd be resizing the same picture to the same size
        over and over for no reason.
        """
        if event.widget is not self:
            return
        new_size = (max(event.width, 1), max(event.height, 1))
        if self._bg_image.cget("size") != new_size:
            self._bg_image.configure(size=new_size)

        # The divider strip spans the same width as the header/tabs
        # panels above and below it (the window's width, minus the
        # padx=20 gap on each side) — keep it in sync as the window
        # changes size, same idea as the background picture above.
        divider_width = max(event.width - 40, 1)
        if self._divider_image.cget("size") != (divider_width, DIVIDER_HEIGHT):
            self._divider_image.configure(size=(divider_width, DIVIDER_HEIGHT))

    def _warn_if_app_detection_unavailable(self) -> None:
        """
        Puts up an obvious on-screen warning if blocking can't work at all.

        `main.py` already prints this same warning to the console — but
        `run.bat` launches with `pythonw.exe` specifically so no console
        window shows up, which also means that printed warning is thrown
        away and nobody ever sees it. Someone could easily use the app for
        weeks thinking blocking is on, when it's silently doing nothing.
        This banner (and the note already on the Blocking tab) make sure
        that's visible right on the main screen instead.
        """
        if not BACKEND_AVAILABLE:
            self._show_banner(
                "Blocking isn't working: pywin32 and psutil aren't "
                "installed, so the app can't see which window you're in. "
                "Run: pip install pywin32 psutil",
                "high", duration_ms=20000,
            )

    # ================================================================== #
    # Building the pieces you see on screen
    # ================================================================== #
    def _build_header(self) -> None:
        """Builds the top area: banner, phase name, countdown, progress bar, and buttons."""
        header = ctk.CTkFrame(self, corner_radius=16, fg_color=self.color_surface)
        header.pack(fill="x", padx=20, pady=(16, 4))
        # Kept so `_on_rider_theme_change` can re-tint this panel later
        # without having to rebuild the whole header from scratch.
        self.header_frame = header

        # A short pop-up message banner. Starts hidden; _show_banner reveals it.
        self.banner = ctk.CTkLabel(
            header, text="", corner_radius=8, height=44,
            font=ctk.CTkFont(size=13), wraplength=480, justify="left",
        )

        # A soft glow sits right behind the timer digits. It has to be
        # made before EVERY other label in this header, including the
        # phase name above it — whatever gets made first is stacked at
        # the back, so this makes sure the glow never paints over words.
        self._timer_glow_label = ctk.CTkLabel(header, text="", image=self._timer_glow_image)
        self._timer_glow_label.place(relx=0.5, rely=0.33, anchor="center")

        self.phase_label = ctk.CTkLabel(
            header, text="Standing By",
            font=ctk.CTkFont(family=DISPLAY_FONT, size=16, weight="bold"),
            text_color=COLOR_IDLE,
        )
        self.phase_label.pack(pady=(4, 0))

        self.time_label = ctk.CTkLabel(
            header, text="25:00", font=ctk.CTkFont(family=DISPLAY_FONT, size=76, weight="bold"),
        )
        self.time_label.pack(pady=(0, 4))

        self.streak_label = ctk.CTkLabel(
            header, text="0 blocks done", font=ctk.CTkFont(size=12),
            text_color=COLOR_IDLE,
        )
        self.streak_label.pack()

        self.driver_label = ctk.CTkLabel(
            header, text=self.config_obj.rider_theme.upper(),
            font=ctk.CTkFont(family=DISPLAY_FONT, size=10, weight="bold"),
            text_color=self.color_driver_text,
        )
        self.driver_label.pack(pady=(2, 0))

        self.progress = ctk.CTkProgressBar(header, height=8, corner_radius=4)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(12, 14))

        # A second, picture-based widget -- only shown INSTEAD of the
        # plain bar above, and only for the 4 Riders with their own
        # custom shape (see _sync_progress_widget_visibility). Every
        # other Rider never sees this at all; the plain bar above just
        # keeps working exactly like it always has.
        self.progress_shape = ctk.CTkLabel(header, text="", image=None)

        self.controls = ctk.CTkFrame(header, fg_color="transparent")
        self.controls.pack()
        controls = self.controls

        # Same trick as the timer glow: made first, so it sits behind the
        # Henshin button that gets made right after it.
        self._button_glow_label = ctk.CTkLabel(controls, text="", image=self._button_glow_image)
        self._button_glow_label.place(relx=0.18, rely=0.5, anchor="center")

        self.start_button = ctk.CTkButton(
            controls, text=self._henshin_word(), width=140, height=40,
            font=ctk.CTkFont(family=DISPLAY_FONT, size=15, weight="bold"), command=self._on_toggle,
            fg_color=self.color_rider_accent, text_color=self.color_button_text,
        )
        self.start_button.grid(row=0, column=0, padx=6)

        ctk.CTkButton(controls, text="Skip", width=80, height=40,
                      fg_color="transparent", border_width=2,
                      border_color=COLOR_TIMER_ACCENT, text_color=COLOR_TIMER_ACCENT,
                      hover_color=("#d0ebff", "#173a5e"),
                      command=self._on_skip).grid(row=0, column=1, padx=6)

        ctk.CTkButton(controls, text="Reset", width=80, height=40,
                      fg_color="transparent", border_width=2,
                      border_color=COLOR_ENFORCE_ACCENT, text_color=COLOR_ENFORCE_ACCENT,
                      hover_color=("#ffe3e3", "#4a1414"),
                      command=self._on_reset).grid(row=0, column=2, padx=6)

        # Shows, live, what window we currently think you're looking at.
        self.watch_label = ctk.CTkLabel(
            header, text="", font=ctk.CTkFont(size=11), text_color=COLOR_IDLE,
            wraplength=480,
        )
        self.watch_label.pack(pady=(12, 0))

    def _build_divider(self) -> None:
        """
        Builds the thin, decorated strip that sits in the gap between
        the timer panel above and the tab panel below — so even that
        little gap looks like it belongs to whichever Kamen Rider era
        is picked, instead of just being empty space.
        """
        self._divider_label = ctk.CTkLabel(self, text="", image=self._divider_image)
        self._divider_label.pack(fill="x", padx=20, pady=(0, 4))

    def _build_tabs(self) -> None:
        self.tabs = ctk.CTkTabview(
            self, height=340,
            fg_color=self.color_surface,
            segmented_button_selected_color=self.color_rider_accent,
            text_color=self.color_button_text,
        )
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        for name in ("Blocking", "Activity", "Settings"):
            self.tabs.add(name)

        self._build_blocking_tab(self.tabs.tab("Blocking"))
        self._build_activity_tab(self.tabs.tab("Activity"))
        self._build_settings_tab(self.tabs.tab("Settings"))

    # ------------------------------------------------------------------ #
    def _build_blocking_tab(self, parent) -> None:
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True)

        if not BACKEND_AVAILABLE:
            ctk.CTkLabel(
                frame,
                text=("App detection unavailable on this system.\n"
                      "Install pywin32 + psutil on Windows to enable it.\n"
                      "The timer works fine either way."),
                text_color=COLOR_WARN, justify="left",
            ).pack(anchor="w", pady=(0, 10))

        self.enforce_var = ctk.BooleanVar(value=self.config_obj.enforcement_enabled)
        ctk.CTkSwitch(frame, text="Block distracting apps during focus",
                      variable=self.enforce_var, progress_color=COLOR_ENFORCE_ACCENT,
                      command=self._save_from_widgets).pack(anchor="w", pady=6)

        self.hard_var = ctk.BooleanVar(value=self.config_obj.hard_mode)
        ctk.CTkSwitch(frame, text="Hard mode (minimise windows, lockdown screen)",
                      variable=self.hard_var, progress_color=COLOR_DANGER,
                      command=self._save_from_widgets).pack(anchor="w", pady=6)

        self.classifier_var = ctk.BooleanVar(value=self.config_obj.use_classifier)
        ctk.CTkSwitch(frame, text="Use the learned model on unlisted apps",
                      variable=self.classifier_var, progress_color=COLOR_TIMER_ACCENT,
                      command=self._save_from_widgets).pack(anchor="w", pady=6)

        self.record_var = ctk.BooleanVar(value=self.config_obj.record_observations)
        ctk.CTkSwitch(frame, text="Record windows for training (stays on this PC)",
                      variable=self.record_var, progress_color=COLOR_LOOK_ACCENT,
                      command=self._save_from_widgets).pack(anchor="w", pady=6)

        # --- The Claude helper -------------------------------------------- #
        ctk.CTkLabel(frame, text="").pack(pady=2)
        ctk.CTkLabel(frame, text="Claude fallback", text_color=COLOR_CLAUDE_ACCENT,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            frame,
            text=("Off by default. When the local model is unsure, sends "
                  "just that one window's title to the Claude API instead "
                  "of guessing. Confident local judgements never leave "
                  "your machine."),
            text_color=COLOR_IDLE, justify="left", wraplength=440,
        ).pack(anchor="w", pady=(0, 6))

        self.claude_var = ctk.BooleanVar(value=self.config_obj.claude_fallback_enabled)
        ctk.CTkSwitch(frame, text="Enable Claude fallback for ambiguous windows",
                      variable=self.claude_var, progress_color=COLOR_CLAUDE_ACCENT,
                      command=self._on_claude_toggle).pack(anchor="w", pady=4)

        self.claude_status = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=11),
                                          text_color=COLOR_IDLE)
        self.claude_status.pack(anchor="w", pady=(0, 4))
        self._refresh_claude_status()

        ctk.CTkLabel(frame, text="Blocked apps (one process name per line)",
                     text_color=COLOR_ENFORCE_ACCENT,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(16, 4))
        self.blocklist_box = ctk.CTkTextbox(frame, height=120, border_width=2,
                                            border_color=COLOR_ENFORCE_ACCENT)
        self.blocklist_box.insert("1.0", "\n".join(self.config_obj.blocklist))
        self.blocklist_box.pack(fill="x")

        ctk.CTkLabel(frame, text="Always-allowed apps", text_color=COLOR_BREAK,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(16, 4))
        self.allowlist_box = ctk.CTkTextbox(frame, height=120, border_width=2,
                                            border_color=COLOR_BREAK)
        self.allowlist_box.insert("1.0", "\n".join(self.config_obj.allowlist))
        self.allowlist_box.pack(fill="x")

        ctk.CTkButton(frame, text="Save lists",
                      command=self._save_lists).pack(anchor="w", pady=14)

    # ------------------------------------------------------------------ #
    def _build_activity_tab(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(header, text="What you were on during focus blocks.",
                     text_color=COLOR_ACTIVITY_ACCENT,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

        self.model_stats = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=11),
                                        text_color=COLOR_IDLE)
        self.model_stats.pack(side="right")

        self.activity_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.activity_frame.pack(fill="both", expand=True)

        self.activity_empty = ctk.CTkLabel(
            self.activity_frame,
            text="Nothing logged yet.\nStart a focus block and this fills in.",
            text_color=COLOR_IDLE, justify="left",
        )
        self.activity_empty.pack(anchor="w", pady=20)
        self._update_model_stats()

    # ------------------------------------------------------------------ #
    def _build_settings_tab(self, parent) -> None:
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True)

        self.spinners: dict[str, ctk.CTkEntry] = {}

        def add_number(key: str, label: str, value: int) -> None:
            """Makes one number field with a label next to it. We check the value when it's saved."""
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=260, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=70)
            entry.insert(0, str(value))
            entry.pack(side="left")
            self.spinners[key] = entry

        ctk.CTkLabel(frame, text="Timer lengths", text_color=COLOR_TIMER_ACCENT,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(0, 4))
        add_number("focus_minutes", "Focus length (min)", self.config_obj.focus_minutes)
        add_number("short_break_minutes", "Short break (min)", self.config_obj.short_break_minutes)
        add_number("long_break_minutes", "Long break (min)", self.config_obj.long_break_minutes)
        add_number("blocks_until_long_break", "Blocks before long break",
                   self.config_obj.blocks_until_long_break)

        ctk.CTkLabel(frame, text="Enforcement", text_color=COLOR_ENFORCE_ACCENT,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(14, 4))
        add_number("grace_seconds", "Grace period on a blocked app (s)",
                   self.config_obj.grace_seconds)
        add_number("strike_interval_seconds", "Seconds between escalations",
                   self.config_obj.strike_interval_seconds)
        add_number("lockdown_seconds", "Lockdown length (s)", self.config_obj.lockdown_seconds)

        ctk.CTkLabel(frame, text="Behavior & notifications", text_color=COLOR_LOOK_ACCENT,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(14, 4))

        self.autobreak_var = ctk.BooleanVar(value=self.config_obj.auto_start_breaks)
        ctk.CTkSwitch(frame, text="Auto-start breaks", variable=self.autobreak_var,
                      progress_color=COLOR_LOOK_ACCENT,
                      command=self._save_from_widgets).pack(anchor="w", pady=4)

        self.autofocus_var = ctk.BooleanVar(value=self.config_obj.auto_start_focus)
        ctk.CTkSwitch(frame, text="Auto-start next focus block", variable=self.autofocus_var,
                      progress_color=COLOR_LOOK_ACCENT,
                      command=self._save_from_widgets).pack(anchor="w", pady=4)

        self.sound_var = ctk.BooleanVar(value=self.config_obj.sound_enabled)
        ctk.CTkSwitch(frame, text="Sounds", variable=self.sound_var,
                      progress_color=COLOR_LOOK_ACCENT,
                      command=self._save_from_widgets).pack(anchor="w", pady=4)

        self.toast_var = ctk.BooleanVar(value=self.config_obj.toast_enabled)
        ctk.CTkSwitch(frame, text="Desktop notifications", variable=self.toast_var,
                      progress_color=COLOR_LOOK_ACCENT,
                      command=self._save_from_widgets).pack(anchor="w", pady=4)

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(row, text="Appearance", width=260, anchor="w").pack(side="left")
        self.appearance_menu = ctk.CTkOptionMenu(
            row, values=["dark", "light", "system"], width=110,
            fg_color=COLOR_LOOK_ACCENT, button_color=COLOR_LOOK_ACCENT,
            command=self._on_appearance_change,
        )
        self.appearance_menu.set(self.config_obj.appearance)
        self.appearance_menu.pack(side="left")

        rider_row = ctk.CTkFrame(frame, fg_color="transparent")
        rider_row.pack(fill="x", pady=(10, 4))
        self.rider_row_label = ctk.CTkLabel(
            rider_row, text=self._rider_row_label_text(), width=260, anchor="w",
        )
        self.rider_row_label.pack(side="left")
        self.rider_menu = ctk.CTkOptionMenu(
            rider_row, values=list(RIDER_THEMES.keys()), width=220,
            command=self._on_rider_theme_change,
        )
        self.rider_menu.set(self.config_obj.rider_theme)
        self.rider_menu.pack(side="left")

        terminology_row = ctk.CTkFrame(frame, fg_color="transparent")
        terminology_row.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(terminology_row, text="Wording", width=140, anchor="w").pack(side="left")

        # A switch you can see the state of at a glance: "Professional"
        # printed in the same color the switch turns when it's off,
        # "Tokusatsu" printed in the color it turns when it's on.
        ctk.CTkLabel(terminology_row, text="Professional", font=ctk.CTkFont(size=12),
                     text_color=COLOR_LOOK_ACCENT).pack(side="left", padx=(0, 8))
        self.terminology_switch = ctk.CTkSwitch(
            terminology_row, text="",
            fg_color=COLOR_LOOK_ACCENT,          # the switch's color when it's OFF (Professional)
            progress_color=COLOR_ENFORCE_ACCENT,  # the switch's color when it's ON (Tokusatsu)
            command=self._on_terminology_switch_toggled,
        )
        if self._is_tokusatsu():
            self.terminology_switch.select()
        else:
            self.terminology_switch.deselect()
        self.terminology_switch.pack(side="left", padx=8)
        ctk.CTkLabel(terminology_row, text="Tokusatsu", font=ctk.CTkFont(size=12),
                     text_color=COLOR_ENFORCE_ACCENT).pack(side="left")

        ctk.CTkButton(frame, text="Save settings",
                      command=self._save_settings).pack(anchor="w", pady=14)

        ctk.CTkButton(frame, text="Rebuild model from labels", fg_color="transparent",
                      border_width=1, text_color=COLOR_DANGER,
                      command=self._reset_model).pack(anchor="w")

    # ================================================================== #
    # The heartbeat — keeps everything moving
    # ================================================================== #
    def _pump(self) -> None:
        """
        The one loop that runs the whole app: move the timer forward, check
        the waiting lines for new info, then redraw the screen.

        This schedules itself again each time using `after`, so it never
        gets stuck waiting on anything.
        """
        try:
            for event in self.session.tick():
                if event is Event.PHASE_ENDED:
                    self._on_phase_ended()
                elif event is Event.PHASE_STARTED:
                    self._on_phase_started()

            self._drain_window_queue()
            self._drain_claude_queue()
            self._drain_banner_queue()
            self._refresh_timer_widgets()
        finally:
            # This "finally" makes sure we always schedule the next loop,
            # even if something above broke — otherwise one bad moment
            # would freeze the whole app forever.
            self.after(self.UI_TICK_MS, self._pump)

    def _drain_window_queue(self) -> None:
        """Look at every window the background checker noticed, and judge each one."""
        latest: Optional[WindowInfo] = None
        while True:
            try:
                latest = self._window_queue.get_nowait()
            except queue.Empty:
                break

            if self.session.phase is not Phase.FOCUS or not self.session.is_running:
                continue
            if not self.config_obj.enforcement_enabled:
                continue

            # Never block someone just for looking at Lock In itself.
            if "lock in" in (latest.title or "").lower():
                continue

            verdict = judge(latest, self.config_obj, self.model, self.claude)
            action = self.enforcer.update(verdict, latest)

            # If our own model isn't sure, and we don't already have a
            # remembered Claude answer, quietly ask Claude in the background.
            # For right now, we just use the local model's "not sure" answer;
            # the real answer will be ready in time for the next check —
            # usually just a second later, since you're probably still on
            # the same window.
            if (self.config_obj.claude_fallback_enabled
                    and verdict.reason is Reason.CLASSIFIER
                    and verdict.confidence < self.config_obj.classifier_threshold):
                self.claude.judge_async(latest.text, self._claude_queue.put)

            # Write down EVERY window, not just the ones we blocked. The
            # Activity tab can only ever show you the times we wrongly
            # flagged something — this is what lets train.py also show you
            # the distracting apps that slipped past unnoticed.
            if self.config_obj.record_observations:
                predicted, confidence = self.model.predict(latest.text)
                self.observations.record(
                    text=latest.text,
                    process=latest.process_name,
                    title=latest.title,
                    predicted=predicted,
                    confidence=confidence,
                    blocked=verdict.blocked,
                )

            # Log every window here, not just blocked ones — otherwise the
            # Activity tab only ever shows the rare flagged window, which
            # looks like it's "missing" most of what you actually did.
            self._log_activity(latest, verdict)
            if action is not Action.NONE:
                self._perform(action, latest)

        if latest is not None:
            self._update_watch_label(latest)

    def _drain_claude_queue(self) -> None:
        """
        Claude's answers show up here, sent over from a background thread.

        Every real, fresh answer (not a repeated one, and not an error) also
        gets added to the training data — that's the whole point of asking
        Claude: over time, the local model learns what Claude knows and
        needs to ask less and less.
        """
        while True:
            try:
                text, verdict = self._claude_queue.get_nowait()
            except queue.Empty:
                return
            if verdict.source != "claude":
                continue        # errors and "couldn't ask" results teach us nothing
            self.observations.record(text=text, predicted=verdict.label,
                                     confidence=verdict.confidence)
            self.observations.label_by_text(text, verdict.label)
            self.observations.save()

    def _drain_banner_queue(self) -> None:
        """Notifier can be called from any thread; its banner messages land here."""
        while True:
            try:
                title, body, urgency = self._banner_queue.get_nowait()
            except queue.Empty:
                return
            self._show_banner(f"{title} — {body}", urgency)

    # ================================================================== #
    # Actually doing something about a blocked window
    # ================================================================== #
    def _perform(self, action: Action, window: WindowInfo) -> None:
        """Turn a step on the ladder into something you actually see or hear."""
        title, body = message_for(
            action,
            era=self.current_era,
            terminology=self.config_obj.terminology,
            app=window.display,
            remaining=self.session.format_remaining(),
            seconds=self.enforcer.seconds_on_blocked_app,
            lockdown=self.config_obj.lockdown_seconds,
        )

        if action is Action.WARN:
            self.notifier.notify(title, body, urgency="normal")

        elif action is Action.NAG:
            self.notifier.notify(title, body, urgency="high")

        elif action is Action.MINIMIZE:
            self.notifier.notify(title, body, urgency="high")
            minimize_window(window.handle)
            # Bring our own window forward, so the timer is what you see now.
            self.after(120, self._raise_self)

        elif action is Action.LOCKDOWN:
            self.notifier.notify(title, body, urgency="high")
            minimize_window(window.handle)
            self._show_lockdown()

    def _raise_self(self) -> None:
        """
        Bring the timer window to the front, without keeping it pinned there
        forever.

        Quickly turning "always on top" on and then back off is the reliable
        trick to actually raise a window — just asking nicely often doesn't
        work, because Windows has its own rules about that.
        """
        try:
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.after(400, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    def _show_lockdown(self) -> None:
        """
        Covers the whole screen for `lockdown_seconds`.

        There's always a visible way out ("End session"), on purpose. An app
        that can trap you is an app you'd delete the first time it messes up
        at a moment that actually mattered.
        """
        if self._lockdown_window is not None:
            return

        overlay = ctk.CTkToplevel(self)
        overlay.attributes("-topmost", True)
        try:
            overlay.attributes("-fullscreen", True)
        except Exception:
            overlay.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        overlay.configure(fg_color="#121417")
        overlay.protocol("WM_DELETE_WINDOW", lambda: None)   # the X button on this window does nothing
        self._lockdown_window = overlay

        ctk.CTkLabel(overlay, text=lockdown_label_for(self.current_era, self.config_obj.terminology),
                     font=ctk.CTkFont(size=54, weight="bold"),
                     text_color=self.color_lockdown_text).pack(pady=(220, 10))

        remaining_word = "mission" if self._is_tokusatsu() else "session"
        ctk.CTkLabel(overlay, text=f"{self.session.format_remaining()} left in this {remaining_word}",
                     font=ctk.CTkFont(size=20), text_color="#9aa4b2").pack()

        countdown = ctk.CTkLabel(overlay, text="", font=ctk.CTkFont(size=16),
                                 text_color="#6b7480")
        countdown.pack(pady=26)

        end_button_text = "Abort Mission" if self._is_tokusatsu() else "End Session"
        ctk.CTkButton(overlay, text=end_button_text, width=200,
                      fg_color="transparent", border_width=1,
                      text_color="#6b7480", hover_color="#1d2026",
                      command=self._end_session_from_lockdown).pack()

        remaining = {"value": self.config_obj.lockdown_seconds}

        def step() -> None:
            """Count down the lockdown screen's own timer, then close itself."""
            if self._lockdown_window is None:
                return
            if remaining["value"] <= 0:
                self._close_lockdown()
                return
            countdown.configure(text=f"unlocks in {remaining['value']}s")
            remaining["value"] -= 1
            overlay.after(1000, step)

        step()
        try:
            overlay.focus_force()
        except Exception:
            pass

    def _close_lockdown(self) -> None:
        if self._lockdown_window is not None:
            try:
                self._lockdown_window.destroy()
            except Exception:
                pass
            self._lockdown_window = None

    def _end_session_from_lockdown(self) -> None:
        """The way out: stops the whole session, not just closes the lockdown screen."""
        self._close_lockdown()
        self._on_reset()

    # ================================================================== #
    # Reacting to the timer changing phases
    # ================================================================== #
    def _on_phase_started(self) -> None:
        """Turn on watching for FOCUS, turn it off for everything else."""
        self.enforcer.reset()
        phase = self.session.phase

        if phase is Phase.FOCUS and self.session.is_running:
            self.monitor.resume()
        else:
            self.monitor.pause()
            self._close_lockdown()

        if phase is not Phase.IDLE:
            label = label_for(phase, self.config_obj.terminology)
            self.notifier.phase_chime(label)
            if phase.is_break:
                self._show_banner(
                    f"{label} — {self.session.format_remaining()} remaining.",
                    "low",
                )
            elif self._is_tokusatsu():
                self._show_banner("Henshin initiated. Blocking is active.", "low")
            else:
                self._show_banner("Focus session started. Blocking is active.", "low")

    def _on_phase_ended(self) -> None:
        self.monitor.pause()
        self._close_lockdown()
        # Saving right when a phase ends is a natural, safe checkpoint — if
        # the app were to crash, you'd only lose at most one block's worth
        # of training data, never more.
        self.observations.save()

    # ================================================================== #
    # What happens when you click a button
    # ================================================================== #
    def _on_toggle(self) -> None:
        was_running = self.session.is_running
        for event in self.session.toggle():
            if event is Event.PHASE_STARTED:
                self._on_phase_started()

        # Resuming a phase that was already started doesn't send an event,
        # so we check and update things ourselves here.
        if not was_running and self.session.is_running:
            if self.session.phase is Phase.FOCUS:
                self.monitor.resume()
        else:
            self.monitor.pause()

        self._refresh_timer_widgets()

    def _on_skip(self) -> None:
        for event in self.session.skip():
            if event is Event.PHASE_STARTED:
                self._on_phase_started()
        self._refresh_timer_widgets()

    def _on_reset(self) -> None:
        self.session.reset()
        self.enforcer.reset()
        self.monitor.pause()
        self._close_lockdown()
        self._refresh_timer_widgets()

    def _on_appearance_change(self, value: str) -> None:
        ctk.set_appearance_mode(value)
        self.config_obj.appearance = value
        self.config_obj.save()
        # Some widgets (the scrolling tab areas and text boxes) don't repaint
        # themselves right away when you switch between dark and light — they
        # can be left showing old, wrong-colored backgrounds with new text
        # colors on top, which is very hard to read. Rebuilding the tabs from
        # scratch forces everything to redraw with the right colors.
        self._rebuild_tabs()

    def _on_rider_theme_change(self, value: str) -> None:
        """Called when you pick a new Kamen Rider in Settings."""
        self.config_obj.rider_theme = value
        self.config_obj.save()
        self._apply_rider_theme()
        self.driver_label.configure(text=value.upper(), text_color=self.color_driver_text)
        self.start_button.configure(fg_color=self.color_rider_accent, text_color=self.color_button_text)
        self.header_frame.configure(fg_color=self.color_surface)
        self._sync_progress_widget_visibility()
        self._refresh_timer_widgets()
        # Rebuilding the tabs is how the tab panels themselves (and the
        # selected-tab highlight) pick up the new surface color and
        # accent — same trick already used when you switch appearance
        # mode, just triggered by a Rider change instead.
        self._rebuild_tabs()

    def _on_terminology_switch_toggled(self) -> None:
        """Called when you click the Wording switch itself."""
        value = "Tokusatsu" if self.terminology_switch.get() else "Professional"
        self._on_terminology_change(value)

    def _on_terminology_change(self, value: str) -> None:
        """
        Called when you flip the Wording switch between Professional and
        Tokusatsu in Settings.

        This changes words, not colors — but the words show up in a lot
        of places at once (the button, the settings labels, the timer's
        own phase name), so the easiest way to make sure every single
        one updates together is the same trick used for a Rider change:
        rebuild everything from scratch. The Rider name label itself
        doesn't have any wording-dependent text anymore, so it's not
        touched here.
        """
        self.config_obj.terminology = value.lower()
        self.config_obj.save()
        self.start_button.configure(text=self._henshin_word())
        self._refresh_timer_widgets()
        self._rebuild_tabs()

    def _rebuild_tabs(self) -> None:
        """Throws away and redraws the tabs, keeping whichever one was open."""
        try:
            current = self.tabs.get()
        except Exception:
            current = "Blocking"
        self.tabs.destroy()
        self._build_tabs()
        self._render_activity()
        try:
            self.tabs.set(current)
        except Exception:
            pass
        # Force every freshly-built widget to actually paint right now,
        # instead of waiting for its own natural turn. Skipping this can
        # leave brand-new widgets showing a stale or blank background for
        # a moment — especially when this whole rebuild was triggered
        # from inside another widget's own click, like the theme dropdown.
        self.update_idletasks()

    # ================================================================== #
    # Saving your settings
    # ================================================================== #
    def _on_claude_toggle(self) -> None:
        """
        Turning this switch on is a real decision — confusing window titles
        will start being sent to Claude — so it gets its own special handler
        instead of quietly sharing one with all the other switches.
        """
        self.config_obj.claude_fallback_enabled = self.claude_var.get()
        self.config_obj.save()
        self.claude.clear_cache()          # an old "unavailable" answer shouldn't stick around
        self._refresh_claude_status()

    def _refresh_claude_status(self) -> None:
        status = self.claude.status
        colour = COLOR_BREAK if status.startswith("ready") else COLOR_IDLE
        self.claude_status.configure(text=f"status: {status}", text_color=colour)

    def _save_from_widgets(self) -> None:
        """These switches save themselves right away — no separate save step needed."""
        c = self.config_obj
        c.enforcement_enabled = self.enforce_var.get()
        c.hard_mode = self.hard_var.get()
        c.use_classifier = self.classifier_var.get()
        c.record_observations = self.record_var.get()
        if hasattr(self, "autobreak_var"):
            c.auto_start_breaks = self.autobreak_var.get()
            c.auto_start_focus = self.autofocus_var.get()
            c.sound_enabled = self.sound_var.get()
            c.toast_enabled = self.toast_var.get()
        c.save()

    def _save_lists(self) -> None:
        """Reads the two text boxes into clean lists, and saves them."""
        def parse(box: ctk.CTkTextbox) -> list:
            raw = box.get("1.0", "end").splitlines()
            # This trick removes duplicate lines while keeping your original order.
            return list(dict.fromkeys(line.strip().lower() for line in raw if line.strip()))

        self.config_obj.blocklist = parse(self.blocklist_box)
        self.config_obj.allowlist = parse(self.allowlist_box)
        self.config_obj.save()
        self._show_banner("Lists saved.", "low")

    def _save_settings(self) -> None:
        """Checks and saves the number fields; tells you clearly if something's wrong."""
        problems = []
        for key, entry in self.spinners.items():
            try:
                value = int(entry.get())
                if value < 1:
                    raise ValueError
                setattr(self.config_obj, key, value)
            except ValueError:
                problems.append(key.replace("_", " "))

        self._save_from_widgets()

        if problems:
            self._show_banner(f"Ignored invalid values: {', '.join(problems)}", "high")
        else:
            self._show_banner("Settings saved. Applies from the next phase.", "low")

    def _reset_model(self) -> None:
        """
        Rebuilds the model from the starter examples plus everything you've
        labelled.

        This RE-builds it, it doesn't wipe it clean. Since every correction
        you've made is also saved to observations.jsonl, nothing you taught
        it is actually lost — what gets cleaned up is just extra double
        counting from clicking the same correction more than once. This does
        the exact same thing as `train.py rebuild`.
        """
        pairs = self.observations.training_pairs()
        self.model = NaiveBayesClassifier.load_seed()
        for text, label in pairs:
            self.model.learn(text, label)
        self.model.save(MODEL_PATH)
        self._update_model_stats()
        self._show_banner(f"Rebuilt from seed + {len(pairs)} of your labels.", "low")

    # ================================================================== #
    # The activity list, and teaching the model as you go
    # ================================================================== #
    def _log_activity(self, window: WindowInfo, verdict) -> None:
        """
        Adds a window to the list — every window, not just blocked ones —
        combining it with the row above if it's the very same app repeated.

        Without combining them, you'd get a brand-new row every single
        second, which would make the list far too messy to actually use for
        correcting the model.
        """
        key = window.display
        if self.activity and self.activity[-1]["key"] == key:
            self.activity[-1]["count"] += 1
            self.activity[-1]["blocked"] = verdict.blocked
            self.activity[-1]["reason"] = verdict.reason
            self.activity[-1]["confidence"] = verdict.confidence
            return

        entry = {
            "key": key,
            "text": window.text,
            "time": datetime.now().strftime("%H:%M"),
            "reason": verdict.reason,
            "confidence": verdict.confidence,
            "blocked": verdict.blocked,
            "count": 1,
            "corrected": None,
        }
        self.activity.append(entry)
        self.activity = self.activity[-40:]     # only keep the most recent entries
        self._render_activity()

    def _render_activity(self) -> None:
        """Redraws the whole activity list from scratch. There aren't many entries, so this is fine."""
        for child in self.activity_frame.winfo_children():
            child.destroy()

        if not self.activity:
            ctk.CTkLabel(self.activity_frame, text="Nothing logged yet.",
                         text_color=COLOR_IDLE).pack(anchor="w", pady=20)
            return

        for entry in reversed(self.activity):
            # Red means we blocked it, green means we let it through. This
            # is what makes it easy to see, at a glance, why something
            # wasn't stopped (like Steam not getting blocked because it was
            # judged "allowed").
            dot_color = COLOR_DANGER if entry.get("blocked") else COLOR_BREAK

            row = ctk.CTkFrame(self.activity_frame, border_width=1, border_color=dot_color)
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(row, text="●", text_color=dot_color, width=20,
                         font=ctk.CTkFont(size=14)).pack(side="left", padx=(10, 0))

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=10, pady=8)

            ctk.CTkLabel(left, text=entry["key"], anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         wraplength=280, justify="left").pack(anchor="w")

            status = "blocked" if entry.get("blocked") else "allowed"
            detail = f"{entry['time']} · {status} · {entry['reason'].value}"
            if entry["reason"] in (Reason.CLASSIFIER, Reason.CLAUDE):
                detail += f" {entry['confidence']:.0%}"
            if entry["count"] > 1:
                detail += f" · seen {entry['count']}×"
            if entry["corrected"]:
                detail += f" · you said: {entry['corrected']}"

            ctk.CTkLabel(left, text=detail, anchor="w",
                         font=ctk.CTkFont(size=10),
                         text_color=COLOR_IDLE).pack(anchor="w")

            # These two buttons are how you actually correct and teach the model.
            ctk.CTkButton(row, text="was studying", width=90, height=26,
                          font=ctk.CTkFont(size=10), fg_color="transparent",
                          border_width=1,
                          command=lambda e=entry: self._correct(e, STUDY)
                          ).pack(side="right", padx=(0, 10))

            ctk.CTkButton(row, text="distraction", width=80, height=26,
                          font=ctk.CTkFont(size=10), fg_color=COLOR_DANGER,
                          hover_color="#96281b",
                          command=lambda e=entry: self._correct(e, DISTRACTION)
                          ).pack(side="right", padx=6)

    def _correct(self, entry: dict, label: str) -> None:
        """
        Teaches the model from one click, and saves it right away.

        The model only needs to update a few simple counts, so this happens
        instantly — the very next check already uses what it just learned.
        """
        self.model.learn(entry["text"], label)
        self.model.save(MODEL_PATH)
        entry["corrected"] = label

        # Also save this decision into the training data, so `train.py`
        # doesn't ask you about a window you already corrected here.
        self.observations.label_by_text(entry["text"], label)
        self.observations.save()

        # Saying "this was studying" is also a strong hint that this app
        # should just always be allowed — so we offer to do that for you
        # right away, instead of making you go find it in the Blocking tab.
        process = entry["key"].split(" — ")[0].strip().lower()
        if label == STUDY and process and process not in self.config_obj.normalised_allowlist():
            self.config_obj.allowlist.append(process)
            self.config_obj.save()
            self._sync_list_boxes()
            self._show_banner(f"Learned. Also allow-listed {process}.", "low")
        else:
            self._show_banner("Learned.", "low")

        self._update_model_stats()
        self._render_activity()

    def _sync_list_boxes(self) -> None:
        """Puts the saved lists back into the text boxes after we've changed them in code."""
        self.blocklist_box.delete("1.0", "end")
        self.blocklist_box.insert("1.0", "\n".join(self.config_obj.blocklist))
        self.allowlist_box.delete("1.0", "end")
        self.allowlist_box.insert("1.0", "\n".join(self.config_obj.allowlist))

    def _update_model_stats(self) -> None:
        """Shows how big the model is, and nudges you toward `train.py label` if there's a backlog."""
        total = sum(self.model.label_counts.values())
        text = f"{total} examples · {len(self.model.vocabulary)} tokens"

        pending = len(self.observations.pending())
        if pending:
            text += f" · {pending} to label"

        self.model_stats.configure(text=text)

    # ================================================================== #
    # Helpers that redraw parts of the screen
    # ================================================================== #
    def _refresh_timer_widgets(self) -> None:
        phase = self.session.phase
        label = label_for(phase, self.config_obj.terminology)
        progress_fraction = self.session.progress

        self.time_label.configure(text=self.session.format_remaining())

        # The progress bar's fill uses the plain, vivid Rider color — but
        # the WORDS use the separate, always-readable version instead,
        # since a word-colored-exactly-like-its-own-background is a word
        # nobody can read (this is exactly the bug some Riders, like
        # Fourze's pure white, used to have).
        fill_color = {
            Phase.FOCUS: self.color_focus,
            Phase.SHORT_BREAK: COLOR_BREAK,
            Phase.LONG_BREAK: COLOR_BREAK,
            Phase.IDLE: COLOR_IDLE,
        }[phase]
        text_color = {
            Phase.FOCUS: self.color_focus_text,
            Phase.SHORT_BREAK: COLOR_BREAK,
            Phase.LONG_BREAK: COLOR_BREAK,
            Phase.IDLE: COLOR_IDLE,
        }[phase]

        if phase is Phase.FOCUS:
            # Agito's whole gimmick is that its color wakes up over the
            # block instead of staying still -- swap in that shifting
            # color ONLY during a focus block, so break/idle still look normal.
            if self.current_tier1_effect == "color_interpolation":
                primary_light, primary_dark = self.rider_primary_pair
                fill_color = (
                    interpolate_agito_color(progress_fraction, primary_light),
                    interpolate_agito_color(progress_fraction, primary_dark),
                )
            # Drive's gimmick lives in how fast the bar itself appears
            # to move, not its color or shape -- so we bend the NUMBER
            # fed to the bar, not what draws it.
            if self.current_tier1_effect == "accelerating_fill":
                progress_fraction = ease_drive_progress(progress_fraction)

        suffix = " (paused)" if self.session.is_paused and phase is not Phase.IDLE else ""
        self.phase_label.configure(text=label + suffix, text_color=text_color)
        self.time_label.configure(text_color=text_color)

        if self.current_tier1_effect in SHAPE_EFFECTS:
            self._refresh_progress_shape(progress_fraction)
        else:
            self.progress.set(progress_fraction)
            self.progress.configure(progress_color=fill_color)

        if self.current_tier1_effect in ("border_glow", "night_overlay"):
            self._refresh_background_effect(progress_fraction)

        self.start_button.configure(text="Pause" if self.session.is_running else self._henshin_word())

        done = self.session.completed_focus_blocks
        until_long = self.session.blocks_until_long_break
        if self._is_tokusatsu():
            streak_text = f"{done} mission{'s' if done != 1 else ''} complete · Full Recovery in {until_long}"
        else:
            streak_text = f"{done} session{'s' if done != 1 else ''} complete · Long break in {until_long}"
        self.streak_label.configure(text=streak_text, text_color=COLOR_LOOK_ACCENT)

        # The title bar also shows a tiny timer, so it's visible even when
        # this window is hidden behind others.
        self.title(f"{self.session.format_remaining()} · {label} — Lock In")

    def _refresh_progress_shape(self, progress_fraction: float) -> None:
        """
        Redraw the picture for one of the 4 Riders with their own
        custom progress shape, and push it onto the picture widget
        already on screen. Renders BOTH a light-mode and a dark-mode
        version, same trick already used for the background wallpaper.
        """
        primary_light, primary_dark = self.rider_primary_pair
        secondary_light, secondary_dark = self.rider_secondary_pair
        light_image = render_progress(
            self.current_tier1_effect, PROGRESS_SHAPE_WIDTH, PROGRESS_SHAPE_HEIGHT,
            progress_fraction, primary_light, secondary_light, False,
        )
        dark_image = render_progress(
            self.current_tier1_effect, PROGRESS_SHAPE_WIDTH, PROGRESS_SHAPE_HEIGHT,
            progress_fraction, primary_dark, secondary_dark, True,
        )
        if hasattr(self, "_progress_shape_image"):
            self._progress_shape_image.configure(light_image=light_image, dark_image=dark_image)
        else:
            self._progress_shape_image = ctk.CTkImage(
                light_image=light_image, dark_image=dark_image,
                size=(PROGRESS_SHAPE_WIDTH, PROGRESS_SHAPE_HEIGHT),
            )
            self.progress_shape.configure(image=self._progress_shape_image)

    def _sync_progress_widget_visibility(self) -> None:
        """
        Show whichever ONE of the two progress widgets this Rider
        actually needs, and hide the other. Always re-inserts the
        visible one right before the button row (`before=self.controls`)
        instead of just calling plain `.pack()` again -- packing a
        forgotten widget with no `before=` appends it at the END of the
        layout order instead of putting it back where it was, which
        would silently push it below the button row.
        """
        if self.current_tier1_effect in SHAPE_EFFECTS:
            self.progress.pack_forget()
            self.progress_shape.pack(fill="x", pady=(12, 14), before=self.controls)
        else:
            self.progress_shape.pack_forget()
            self.progress.pack(fill="x", pady=(12, 14), before=self.controls)

    def _update_watch_label(self, window: WindowInfo) -> None:
        if self.session.phase is Phase.FOCUS and self.monitor.is_active:
            self.watch_label.configure(text=f"watching: {window.display}")
        else:
            self.watch_label.configure(text="")

    def _queue_banner(self, title: str, body: str, urgency: str) -> None:
        """Notifier calls this from any thread — it's safe to use that way."""
        self._banner_queue.put((title, body, urgency))

    def _show_banner(self, text: str, urgency: str = "low", duration_ms: Optional[int] = None) -> None:
        """Shows a short message banner above the timer for a little while."""
        colors = {
            "low": ("#1f6aa5", "#dbe9f4"),
            "normal": (COLOR_WARN, "#241d00"),
            "high": (COLOR_DANGER, "#ffe8e5"),
        }
        bg, fg = colors.get(urgency, colors["low"])

        self.banner.configure(text=text, fg_color=bg, text_color=fg)
        self.banner.pack(fill="x", pady=(0, 10), before=self.phase_label)

        # Cancel any earlier "hide the banner" timer, so a new banner always
        # gets its own full amount of time on screen.
        if self._banner_after_id is not None:
            try:
                self.after_cancel(self._banner_after_id)
            except Exception:
                pass
        self._banner_after_id = self.after(duration_ms or self.BANNER_MS, self.banner.pack_forget)

    # ================================================================== #
    def _on_close(self) -> None:
        """Saves everything and shuts down the background checker cleanly."""
        try:
            self.config_obj.save()
            self.model.save(MODEL_PATH)
            self.observations.save()
        finally:
            self.monitor.stop()
            self.destroy()


def run() -> None:
    """This is what main.py calls to actually open the app."""
    LockInApp().mainloop()