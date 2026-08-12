"""Tests for the judgement rules and the escalation ladder."""

import pytest

from lock_in.classifier import DISTRACTION, SEED_DATA, STUDY, NaiveBayesClassifier
from lock_in.config import Config
from lock_in.enforcer import (
    Action,
    Enforcer,
    Reason,
    WindowInfo,
    judge,
    message_for,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 500.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def config() -> Config:
    return Config(
        grace_seconds=8,
        strike_interval_seconds=10,
        strike_decay_seconds=30,
        hard_mode=False,
        use_classifier=True,
        classifier_threshold=0.8,
        blocklist=["discord.exe", "steam.exe"],
        allowlist=["code.exe", "chrome.exe"],
    )


@pytest.fixture
def model() -> NaiveBayesClassifier:
    return NaiveBayesClassifier().train(SEED_DATA)


@pytest.fixture
def enforcer(config, clock) -> Enforcer:
    return Enforcer(config, clock=clock)


def win(process="", title="", handle=1) -> WindowInfo:
    return WindowInfo(process_name=process, title=title, pid=42, handle=handle)


# --------------------------------------------------------------------------- #
# judge()
# --------------------------------------------------------------------------- #
def test_blocklist_blocks(config, model):
    v = judge(win("discord.exe", "general #chat"), config, model)
    assert v.blocked
    assert v.reason is Reason.BLOCKLIST


def test_allowlist_allows(config, model):
    v = judge(win("code.exe", "main.py"), config, model)
    assert not v.blocked
    assert v.reason is Reason.ALLOWLIST


def test_allowlist_beats_the_classifier(config, model):
    """chrome.exe is on the allow list, so even a YouTube title must be let through."""
    v = judge(win("chrome.exe", "Stray Kids MV - YouTube"), config, model)
    assert not v.blocked
    assert v.reason is Reason.ALLOWLIST


def test_classifier_catches_unlisted_distractions(config, model):
    config.allowlist = []      # take chrome off the list, so the model has to decide
    v = judge(win("chrome.exe", "TikTok For You page - Google Chrome"), config, model)
    assert v.blocked
    assert v.reason is Reason.CLASSIFIER
    assert v.confidence >= config.classifier_threshold


def test_classifier_can_be_switched_off(config, model):
    config.allowlist = []
    config.use_classifier = False
    v = judge(win("chrome.exe", "TikTok For You page"), config, model)
    assert not v.blocked
    assert v.reason is Reason.UNKNOWN


def test_high_threshold_suppresses_weak_flags(config, model):
    config.allowlist = []
    config.classifier_threshold = 0.999
    v = judge(win("chrome.exe", "some ambiguous page"), config, model)
    assert not v.blocked


def test_unknown_window_is_allowed(config):
    v = judge(win("", ""), config, None)
    assert not v.blocked
    assert v.reason is Reason.UNKNOWN


def test_process_matching_is_case_insensitive(config, model):
    assert judge(win("DISCORD.EXE", "chat"), config, model).blocked


def test_title_fallback_blocks_when_process_name_is_unreadable(config, model):
    """
    Some programs (like Steam running "as administrator") hide their process
    name from a program that isn't also elevated. When that happens, we
    should still catch it by matching the blocked program's name in the
    window's title text instead.
    """
    v = judge(win("", "Steam"), config, model)
    assert v.blocked
    assert v.reason is Reason.BLOCKLIST


def test_title_fallback_allows_when_process_name_is_unreadable(config, model):
    v = judge(win("", "Visual Studio Code"), config, model)
    assert not v.blocked
    assert v.reason is Reason.ALLOWLIST


def test_title_fallback_is_not_used_when_process_name_is_known(config, model):
    """If we DO know the process name, we trust that — not a fuzzy title guess."""
    config.allowlist = []
    v = judge(win("chrome.exe", "just a plain page"), config, model)
    assert v.reason is not Reason.BLOCKLIST
    assert v.reason is not Reason.ALLOWLIST


def test_blocklist_matches_process_without_exe_suffix(config, model):
    """macOS/Linux report process names with no .exe — the same list still has
    to catch it, since nobody should need a separate list per computer."""
    v = judge(win("discord", "general #chat"), config, model)
    assert v.blocked
    assert v.reason is Reason.BLOCKLIST


def test_allowlist_matches_process_without_exe_suffix(config, model):
    v = judge(win("code", "main.py - lock_in"), config, model)
    assert not v.blocked
    assert v.reason is Reason.ALLOWLIST


# --------------------------------------------------------------------------- #
# Escalation ladder
# --------------------------------------------------------------------------- #
def blocked_verdict():
    from lock_in.enforcer import Verdict
    return Verdict(True, Reason.BLOCKLIST, 1.0)


def clean_verdict():
    from lock_in.enforcer import Verdict
    return Verdict(False, Reason.ALLOWLIST, 1.0)


def test_grace_period_stays_silent(enforcer, clock):
    w = win("discord.exe", "chat")
    assert enforcer.update(blocked_verdict(), w) is Action.NONE
    clock.advance(7)
    assert enforcer.update(blocked_verdict(), w) is Action.NONE
    assert enforcer.strikes == 0


def test_first_strike_after_grace_is_a_warning(enforcer, clock):
    w = win("discord.exe", "chat")
    enforcer.update(blocked_verdict(), w)
    clock.advance(9)
    assert enforcer.update(blocked_verdict(), w) is Action.WARN


def test_zero_grace_mode_skips_the_grace_period_entirely(config, clock):
    config.zero_grace_mode = True
    e = Enforcer(config, clock=clock)
    w = win("discord.exe", "chat")
    # Normally the very first check would return Action.NONE (still
    # inside the grace period, see test_grace_period_stays_silent) --
    # zero_grace_mode should skip straight to a real strike instead.
    assert e.update(blocked_verdict(), w) is not Action.NONE


def test_full_ladder_in_hard_mode(config, clock):
    """Hard mode skips the warnings entirely and acts right away."""
    config.hard_mode = True
    e = Enforcer(config, clock=clock)
    w = win("discord.exe", "chat")
    e.update(blocked_verdict(), w)

    clock.advance(9)
    assert e.update(blocked_verdict(), w) is Action.MINIMIZE
    clock.advance(11)
    assert e.update(blocked_verdict(), w) is Action.LOCKDOWN


def test_soft_mode_never_touches_windows(config, clock):
    config.hard_mode = False
    e = Enforcer(config, clock=clock)
    w = win("discord.exe", "chat")
    e.update(blocked_verdict(), w)

    actions = []
    for _ in range(5):
        clock.advance(11)
        actions.append(e.update(blocked_verdict(), w))

    assert Action.MINIMIZE not in actions
    assert Action.LOCKDOWN not in actions
    assert Action.NAG in actions


def test_escalation_is_rate_limited(enforcer, clock):
    """Checking every second must not mean a new alert every second."""
    w = win("discord.exe", "chat")
    enforcer.update(blocked_verdict(), w)
    clock.advance(9)
    assert enforcer.update(blocked_verdict(), w) is Action.WARN

    fired = 0
    for _ in range(8):                      # 8 more checks, 1 second apart
        clock.advance(1)
        if enforcer.update(blocked_verdict(), w) is not Action.NONE:
            fired += 1
    assert fired == 0


def test_returning_to_work_stops_escalation(enforcer, clock):
    w = win("discord.exe", "chat")
    enforcer.update(blocked_verdict(), w)
    clock.advance(9)
    enforcer.update(blocked_verdict(), w)

    clock.advance(2)
    assert enforcer.update(clean_verdict(), win("code.exe", "main.py")) is Action.NONE
    assert enforcer.seconds_on_blocked_app == 0.0


def test_strikes_decay_after_sustained_clean_time(enforcer, clock):
    w = win("discord.exe", "chat")
    enforcer.update(blocked_verdict(), w)
    clock.advance(9)
    enforcer.update(blocked_verdict(), w)
    clock.advance(11)
    enforcer.update(blocked_verdict(), w)
    assert enforcer.strikes == 2

    good = win("code.exe", "main.py")
    enforcer.update(clean_verdict(), good)      # this is when the good behavior clock starts
    clock.advance(31)
    enforcer.update(clean_verdict(), good)
    assert enforcer.strikes == 1


def test_app_hopping_does_not_reset_strikes(enforcer, clock):
    """Switching from Discord to Steam gives a fresh grace period but keeps your strikes."""
    enforcer.update(blocked_verdict(), win("discord.exe", "chat"))
    clock.advance(9)
    enforcer.update(blocked_verdict(), win("discord.exe", "chat"))
    assert enforcer.strikes == 1

    clock.advance(1)
    enforcer.update(blocked_verdict(), win("steam.exe", "Library"))
    clock.advance(20)
    assert enforcer.update(blocked_verdict(), win("steam.exe", "Library")) is Action.NAG
    assert enforcer.strikes == 2


def test_reset_clears_state(enforcer, clock):
    w = win("discord.exe", "chat")
    enforcer.update(blocked_verdict(), w)
    clock.advance(9)
    enforcer.update(blocked_verdict(), w)
    enforcer.reset()
    assert enforcer.strikes == 0
    assert enforcer.seconds_on_blocked_app == 0.0


def test_seconds_on_blocked_app_tracks_the_visit(enforcer, clock):
    w = win("discord.exe", "chat")
    enforcer.update(blocked_verdict(), w)
    clock.advance(5)
    assert enforcer.seconds_on_blocked_app == pytest.approx(5.0)


# --------------------------------------------------------------------------- #
# Copy
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("action", [Action.WARN, Action.NAG, Action.MINIMIZE, Action.LOCKDOWN])
def test_every_rung_has_message_copy(action):
    title, body = message_for(action, app="discord.exe", remaining="12:30",
                              seconds=20, lockdown=15)
    assert title and body
    assert "{" not in body          # make sure every blank in the message got filled in


def test_message_copy_matches_serious_tokusatsu_tone():
    title, body = message_for(Action.WARN, terminology="tokusatsu", app="discord.exe",
                              remaining="12:30", seconds=20, lockdown=15)
    assert title == "Off Mission"
    assert body == "discord.exe is not part of the mission. 12:30 remains in this Henshin block."

    title, body = message_for(Action.NAG, terminology="tokusatsu", app="discord.exe",
                              remaining="12:30", seconds=20, lockdown=15)
    assert title == "Repeated Violation"
    assert body == "20s on discord.exe. 12:30 until the mission ends — hold the line."

    title, body = message_for(Action.MINIMIZE, terminology="tokusatsu", app="discord.exe",
                              remaining="12:30", seconds=20, lockdown=15)
    assert title == "Window Neutralized"
    assert body == "discord.exe minimized. 12:30 remaining. This was your directive."

    title, body = message_for(Action.LOCKDOWN, terminology="tokusatsu", app="discord.exe",
                              remaining="12:30", seconds=20, lockdown=15)
    assert title == "Full Lockdown"
    assert body == "Screen sealed for 15s. Recover, then resume the mission."


def test_message_copy_defaults_to_professional_tone():
    """No terminology given should read exactly like asking for "professional"."""
    default = message_for(Action.WARN, app="discord.exe", remaining="12:30", seconds=20, lockdown=15)
    professional = message_for(Action.WARN, terminology="professional", app="discord.exe",
                               remaining="12:30", seconds=20, lockdown=15)
    assert default == professional


def test_professional_tone_is_the_same_regardless_of_era():
    """Professional mode has one voice -- era only matters in tokusatsu mode."""
    showa = message_for(Action.WARN, era="Showa", terminology="professional", app="discord.exe",
                        remaining="12:30", seconds=20, lockdown=15)
    reiwa = message_for(Action.WARN, era="Reiwa", terminology="professional", app="discord.exe",
                        remaining="12:30", seconds=20, lockdown=15)
    assert showa == reiwa


def test_professional_tone_does_not_use_tokusatsu_words():
    _, body = message_for(Action.WARN, terminology="professional", app="discord.exe",
                          remaining="12:30", seconds=20, lockdown=15)
    assert "Henshin" not in body
    assert "mission" not in body.lower()


def test_default_era_is_heisei():
    """No era given (in tokusatsu mode) should read exactly like asking for Heisei."""
    default = message_for(Action.WARN, terminology="tokusatsu", app="discord.exe",
                          remaining="12:30", seconds=20, lockdown=15)
    heisei = message_for(Action.WARN, era="Heisei", terminology="tokusatsu", app="discord.exe",
                         remaining="12:30", seconds=20, lockdown=15)
    assert default == heisei


@pytest.mark.parametrize("era", ["Showa", "Heisei", "Reiwa"])
@pytest.mark.parametrize("action", [Action.WARN, Action.NAG, Action.MINIMIZE, Action.LOCKDOWN])
def test_every_era_has_message_copy_for_every_rung(era, action):
    title, body = message_for(action, era=era, terminology="tokusatsu", app="discord.exe",
                              remaining="12:30", seconds=20, lockdown=15)
    assert title and body
    assert "{" not in body


def test_showa_and_reiwa_have_a_different_voice_than_heisei():
    """The whole point of era copy is that it doesn't all read the same."""
    heisei_title, _ = message_for(Action.WARN, era="Heisei", terminology="tokusatsu",
                                  app="discord.exe", remaining="12:30", seconds=20, lockdown=15)
    showa_title, _ = message_for(Action.WARN, era="Showa", terminology="tokusatsu",
                                 app="discord.exe", remaining="12:30", seconds=20, lockdown=15)
    reiwa_title, _ = message_for(Action.WARN, era="Reiwa", terminology="tokusatsu",
                                 app="discord.exe", remaining="12:30", seconds=20, lockdown=15)
    assert len({heisei_title, showa_title, reiwa_title}) == 3


def test_unknown_era_falls_back_to_heisei_instead_of_crashing():
    title, _ = message_for(Action.WARN, era="Not A Real Era", terminology="tokusatsu",
                           app="discord.exe", remaining="12:30", seconds=20, lockdown=15)
    assert title == "Off Mission"


def test_unknown_terminology_falls_back_to_professional_instead_of_crashing():
    title, _ = message_for(Action.WARN, terminology="Not A Real Mode", app="discord.exe",
                           remaining="12:30", seconds=20, lockdown=15)
    professional_title, _ = message_for(Action.WARN, terminology="professional", app="discord.exe",
                                        remaining="12:30", seconds=20, lockdown=15)
    assert title == professional_title


@pytest.mark.parametrize("era", ["Showa", "Heisei", "Reiwa"])
def test_every_era_has_a_lockdown_screen_label(era):
    from lock_in.enforcer import lockdown_label_for
    label = lockdown_label_for(era, terminology="tokusatsu")
    assert label and label == label.upper()   # the lockdown screen shouts, on purpose


def test_lockdown_label_falls_back_for_unknown_era():
    from lock_in.enforcer import lockdown_label_for
    assert lockdown_label_for("Not A Real Era", terminology="tokusatsu") == \
        lockdown_label_for("Heisei", terminology="tokusatsu")


def test_lockdown_label_defaults_to_professional():
    from lock_in.enforcer import lockdown_label_for
    assert lockdown_label_for("Heisei") == lockdown_label_for("Heisei", terminology="professional")
    assert lockdown_label_for("Heisei") != lockdown_label_for("Heisei", terminology="tokusatsu")


def test_window_display_truncates_long_titles():
    w = win("chrome.exe", "x" * 200)
    assert len(w.display) < 90


# --------------------------------------------------------------------------- #
# Testing how judge() works together with Claude (the background-thread parts
# are tested separately, over in test_claude_fallback.py)
# --------------------------------------------------------------------------- #
class StubClaude:
    """A tiny pretend Claude that only offers what judge() actually calls: peek()."""

    def __init__(self, cached=None):
        self._cached = cached or {}

    def peek(self, text):
        return self._cached.get(text)


def test_claude_not_consulted_when_feature_disabled(config, model):
    """Even with a remembered answer ready to go, turned off means turned off."""
    from lock_in.claude_fallback import ClaudeVerdict
    config.allowlist = []
    config.claude_fallback_enabled = False
    stub = StubClaude({"ambiguous window": ClaudeVerdict(DISTRACTION, 0.9, "claude")})
    v = judge(win("unknown.exe", "ambiguous window"), config, model, stub)
    assert v.reason is not Reason.CLAUDE


def test_claude_breaks_ties_when_local_model_is_unsure(config, model):
    """A confident local answer never needs Claude's help; an unsure one does."""
    from lock_in.claude_fallback import ClaudeVerdict
    config.allowlist = []
    config.claude_fallback_enabled = True
    config.classifier_threshold = 0.999      # force everything into "unsure"

    window = win("unknown.exe", "some ambiguous productivity tool window")
    stub = StubClaude({window.text: ClaudeVerdict(DISTRACTION, 0.85, "claude")})
    v = judge(window, config, model, stub)
    assert v.blocked
    assert v.reason is Reason.CLAUDE
    assert v.confidence == pytest.approx(0.85)


def test_claude_cache_miss_falls_back_to_local_verdict(config, model):
    """No remembered answer yet -> just use the local model's answer for THIS check."""
    config.allowlist = []
    config.claude_fallback_enabled = True
    config.classifier_threshold = 0.999
    stub = StubClaude({})     # nothing remembered yet
    v = judge(win("unknown.exe", "some ambiguous window"), config, model, stub)
    assert v.reason is Reason.CLASSIFIER
    assert not v.blocked      # being unsure defaults to letting it through, never blocking


def test_allowlist_beats_claude(config, model):
    """The lists you set yourself always outrank any model, local or remote."""
    from lock_in.claude_fallback import ClaudeVerdict
    config.claude_fallback_enabled = True
    window = win("chrome.exe", "Stray Kids MV - YouTube")   # chrome.exe is on the allow list
    stub = StubClaude({window.text: ClaudeVerdict(DISTRACTION, 0.99, "claude")})
    v = judge(window, config, model, stub)
    assert not v.blocked
    assert v.reason is Reason.ALLOWLIST


def test_blocklist_beats_claude(config, model):
    from lock_in.claude_fallback import ClaudeVerdict
    config.claude_fallback_enabled = True
    window = win("discord.exe", "some window")   # discord.exe is on the block list
    stub = StubClaude({window.text: ClaudeVerdict(STUDY, 0.99, "claude")})
    v = judge(window, config, model, stub)
    assert v.blocked
    assert v.reason is Reason.BLOCKLIST


def test_confident_local_verdict_beats_claude(config, model):
    """Claude only breaks ties — it can't overrule a confident local answer."""
    from lock_in.claude_fallback import ClaudeVerdict
    config.allowlist = []
    config.claude_fallback_enabled = True
    # We leave the threshold at its default (0.8) — the starter-trained model
    # is confident about "general #chat" style text, so Claude should never
    # even get asked.
    window = win("unknown.exe", "general #chat - Discord")
    stub = StubClaude({window.text: ClaudeVerdict(STUDY, 0.99, "claude")})
    v = judge(window, config, model, stub)
    assert v.reason is Reason.CLASSIFIER      # not CLAUDE — it was never even asked
    assert v.blocked                          # the local model's own answer wins


def test_claude_none_behaves_exactly_like_before(config, model):
    """Not passing a claude argument at all shouldn't change any old behavior."""
    config.allowlist = []
    v = judge(win("unknown.exe", "TikTok For You page"), config, model)
    assert v.blocked
    assert v.reason is Reason.CLASSIFIER