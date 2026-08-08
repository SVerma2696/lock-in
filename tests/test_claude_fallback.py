"""
Tests for claude_fallback.py.

Nothing in this file ever really talks to the internet. `ClaudeFallback._client`
gets swapped out for a small pretend version that copies the two kinds of
replies Claude's toolkit can give back (a normal answer, or a broken/missing
one) — that's enough to test every path through `_call` without needing a
real API key or an internet connection.
"""

import json
import time

import pytest

from lock_in.classifier import DISTRACTION, STUDY
from lock_in.claude_fallback import ClaudeFallback, ClaudeVerdict
from lock_in.config import Config


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeTextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, content) -> None:
        self.content = content


class FakeMessages:
    """A pretend version of `client.messages`. `script` gets called with (kwargs)."""

    def __init__(self, script) -> None:
        self._script = script
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._script(kwargs)


class FakeClient:
    def __init__(self, script) -> None:
        self.messages = FakeMessages(script)


def install_fake_client(fallback: ClaudeFallback, script) -> FakeClient:
    """Skip the real Claude toolkit entirely — just plug in our pretend client."""
    client = FakeClient(script)
    fallback._client = client
    return client


def reply(label: str, confidence: float = 0.9) -> FakeResponse:
    return FakeResponse([FakeTextBlock(json.dumps({"label": label, "confidence": confidence}))])


@pytest.fixture
def config() -> Config:
    return Config(claude_fallback_enabled=True, claude_cache_minutes=30)


@pytest.fixture
def fallback(config, monkeypatch) -> ClaudeFallback:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    return ClaudeFallback(config)


# --------------------------------------------------------------------------- #
# Availability
# --------------------------------------------------------------------------- #
def test_unavailable_when_disabled(config, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    config.claude_fallback_enabled = False
    assert not ClaudeFallback(config).available


def test_unavailable_without_api_key(config, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert not ClaudeFallback(config).available


def test_status_reports_missing_key(config, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert "ANTHROPIC_API_KEY" in ClaudeFallback(config).status


def test_status_off_when_disabled(config, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    config.claude_fallback_enabled = False
    assert ClaudeFallback(config).status == "off"


# --------------------------------------------------------------------------- #
# judge() — the blocking call, exercised with a fake client
# --------------------------------------------------------------------------- #
def test_judge_parses_a_clean_response(fallback):
    install_fake_client(fallback, lambda kwargs: reply(DISTRACTION, 0.93))
    verdict = fallback.judge("TikTok For You page - Google Chrome chrome.exe")
    assert verdict.label == DISTRACTION
    assert verdict.confidence == pytest.approx(0.93)
    assert verdict.source == "claude"


def test_judge_sends_the_configured_model(fallback):
    fallback.config.claude_model = "claude-haiku-4-5-20251001"
    client = install_fake_client(fallback, lambda kwargs: reply(STUDY))
    fallback.judge("some window")
    assert client.messages.calls[0]["model"] == "claude-haiku-4-5-20251001"


def test_judge_sends_only_the_window_text(fallback):
    """The privacy promise in the README only holds true if we're not sending anything extra."""
    client = install_fake_client(fallback, lambda kwargs: reply(STUDY))
    fallback.judge("Overleaf thesis draft - Google Chrome chrome.exe")
    sent = client.messages.calls[0]["messages"][0]["content"]
    assert sent == "Window: Overleaf thesis draft - Google Chrome chrome.exe"


def test_judge_clamps_confidence_into_range(fallback):
    install_fake_client(fallback, lambda kwargs: reply(DISTRACTION, 1.7))
    assert fallback.judge("x").confidence == 1.0

    install_fake_client(fallback, lambda kwargs: reply(DISTRACTION, 0.1))
    assert fallback.judge("y").confidence == 0.5


def test_judge_rejects_unparseable_json(fallback):
    install_fake_client(fallback, lambda kwargs: FakeResponse([FakeTextBlock("not json")]))
    verdict = fallback.judge("z")
    assert verdict.source == "error"
    assert verdict.label == STUDY          # assume it's fine by default, unless we know otherwise


def test_judge_rejects_unexpected_label(fallback):
    install_fake_client(fallback, lambda kwargs: reply("maybe", 0.9))
    verdict = fallback.judge("z")
    assert verdict.source == "error"


def test_judge_survives_client_exceptions(fallback):
    def blow_up(kwargs):
        raise RuntimeError("connection reset")
    install_fake_client(fallback, blow_up)
    verdict = fallback.judge("z")
    assert verdict.source == "error"
    assert verdict.label == STUDY
    assert "connection reset" in verdict.detail


def test_judge_never_raises_on_empty_text(fallback):
    verdict = fallback.judge("")
    assert verdict.source == "unavailable"


def test_judge_returns_unavailable_without_client(config, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    verdict = ClaudeFallback(config).judge("something")
    assert verdict.source == "unavailable"
    assert verdict.label == STUDY
    assert verdict.confidence == 0.5


# --------------------------------------------------------------------------- #
# Caching
# --------------------------------------------------------------------------- #
def test_second_call_hits_the_cache(fallback):
    client = install_fake_client(fallback, lambda kwargs: reply(DISTRACTION, 0.9))
    fallback.judge("same window")
    fallback.judge("same window")
    assert len(client.messages.calls) == 1


def test_cache_is_keyed_per_text(fallback):
    client = install_fake_client(fallback, lambda kwargs: reply(STUDY, 0.9))
    fallback.judge("window a")
    fallback.judge("window b")
    assert len(client.messages.calls) == 2


def test_second_call_reports_cache_source(fallback):
    install_fake_client(fallback, lambda kwargs: reply(STUDY, 0.9))
    fallback.judge("same window")
    second = fallback.judge("same window")
    assert second.source == "cache"
    assert second.label == STUDY


def test_expired_cache_entry_triggers_a_new_call(fallback):
    fallback.config.claude_cache_minutes = 0     # expires immediately
    client = install_fake_client(fallback, lambda kwargs: reply(STUDY, 0.9))
    fallback.judge("same window")
    time.sleep(0.01)
    fallback.judge("same window")
    assert len(client.messages.calls) == 2


def test_errors_are_not_cached(fallback):
    """One temporary failure shouldn't ruin every future check for the same title."""
    calls = {"n": 0}

    def flaky(kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("rate limited")
        return reply(DISTRACTION, 0.9)

    install_fake_client(fallback, flaky)
    first = fallback.judge("same window")
    second = fallback.judge("same window")
    assert first.source == "error"
    assert second.source == "claude"
    assert calls["n"] == 2


def test_peek_never_calls_the_client(fallback):
    client = install_fake_client(fallback, lambda kwargs: reply(STUDY, 0.9))
    assert fallback.peek("never asked") is None
    assert client.messages.calls == []


def test_peek_returns_a_warm_cache_entry(fallback):
    install_fake_client(fallback, lambda kwargs: reply(DISTRACTION, 0.88))
    fallback.judge("window")
    peeked = fallback.peek("window")
    assert peeked is not None
    assert peeked.label == DISTRACTION


def test_clear_cache_forgets_everything(fallback):
    client = install_fake_client(fallback, lambda kwargs: reply(STUDY, 0.9))
    fallback.judge("window")
    fallback.clear_cache()
    fallback.judge("window")
    assert len(client.messages.calls) == 2


# --------------------------------------------------------------------------- #
# judge_async — the "don't wait around" version the enforcer actually uses
# --------------------------------------------------------------------------- #
def test_judge_async_delivers_a_result(fallback):
    install_fake_client(fallback, lambda kwargs: reply(DISTRACTION, 0.9))
    results = []
    fallback.judge_async("bg window", lambda text, verdict: results.append((text, verdict)))

    for _ in range(50):
        if results:
            break
        time.sleep(0.02)

    assert results
    text, verdict = results[0]
    assert text == "bg window"
    assert verdict.label == DISTRACTION


def test_judge_async_does_not_block_the_caller(fallback):
    def slow(kwargs):
        time.sleep(0.3)
        return reply(STUDY, 0.9)
    install_fake_client(fallback, slow)

    start = time.monotonic()
    fallback.judge_async("window", lambda text, verdict: None)
    elapsed = time.monotonic() - start
    assert elapsed < 0.1        # comes back almost instantly, the real work happens on a background thread


def test_judge_async_skips_when_unavailable(config, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fb = ClaudeFallback(config)
    calls = []
    fb.judge_async("window", lambda text, verdict: calls.append(verdict))
    time.sleep(0.05)
    assert calls == []           # a background thread should never have even started


def test_double_fire_is_guarded(fallback):
    """Two background asks for the same text before the first finishes -> only one real call."""
    started = []

    def slow(kwargs):
        started.append(1)
        time.sleep(0.2)
        return reply(STUDY, 0.9)

    client = install_fake_client(fallback, slow)
    fallback.judge_async("window", lambda text, verdict: None)
    time.sleep(0.02)                    # let the first thread start and register
    fallback.judge_async("window", lambda text, verdict: None)   # should be a no-op
    time.sleep(0.3)
    assert len(client.messages.calls) == 1