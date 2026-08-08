"""Tests for the window-title classifier."""

import json

import pytest

from lock_in.classifier import (
    DISTRACTION,
    SEED_DATA,
    STUDY,
    NaiveBayesClassifier,
    tokenize,
)


@pytest.fixture
def model() -> NaiveBayesClassifier:
    return NaiveBayesClassifier().train(SEED_DATA)


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #
def test_tokenize_lowercases_and_splits():
    assert tokenize("Main.PY - Visual Studio Code") == ["main", "py", "visual", "studio", "code"]


def test_tokenize_drops_stopwords_and_single_chars():
    tokens = tokenize("The Art of X - a Guide")
    assert "the" not in tokens
    assert "of" not in tokens
    assert "x" not in tokens
    assert "art" in tokens


def test_tokenize_handles_empty_and_punctuation_only():
    assert tokenize("") == []
    assert tokenize("--- ... !!!") == []


def test_tokenize_drops_non_chrome_browser_names_too():
    """
    Every browser's name and process word must be filtered, not just
    Chrome's — otherwise a word like "msedge" or "microsoft" quietly
    becomes "the thing every Edge window has in common" instead of being
    ignored, the same problem the Chrome/Google stopwords already guard
    against.
    """
    tokens = tokenize("Reddit r all - Microsoft Edge msedge.exe")
    assert "microsoft" not in tokens
    assert "edge" not in tokens
    assert "msedge" not in tokens
    assert "reddit" in tokens

    firefox_tokens = tokenize("Wikipedia Fourier transform - Mozilla Firefox firefox.exe")
    assert "mozilla" not in firefox_tokens
    assert "firefox" not in firefox_tokens
    assert "wikipedia" in firefox_tokens


# --------------------------------------------------------------------------- #
# Prediction
# --------------------------------------------------------------------------- #
def test_untrained_model_has_no_opinion():
    label, confidence = NaiveBayesClassifier().predict("YouTube")
    assert label == STUDY               # assume it's fine unless we know otherwise
    assert confidence == 0.5


def test_recognises_obvious_distractions(model):
    for title in [
        "Stray Kids comeback stage - YouTube - Google Chrome chrome.exe",
        "general #chat - Discord discord.exe",
        "TikTok For You page - Google Chrome chrome.exe",
        "Steam Library steam.exe",
    ]:
        label, confidence = model.predict(title)
        assert label == DISTRACTION, f"{title!r} was classified {label}"
        assert confidence > 0.6


def test_recognises_obvious_study(model):
    for title in [
        "enforcer.py - lock_in - Visual Studio Code code.exe",
        "Problem Set 5.pdf - Adobe Acrobat Reader acrord32.exe",
        "Canvas ECE 232 Modules - Google Chrome chrome.exe",
        "Stack Overflow python threading deadlock - Google Chrome chrome.exe",
    ]:
        label, confidence = model.predict(title)
        assert label == STUDY, f"{title!r} was classified {label}"


def test_recognises_distractions_and_study_in_edge_too(model):
    """The model shouldn't need Chrome specifically — same words, same answer."""
    distraction, _ = model.predict("Netflix watch episode - Microsoft Edge msedge.exe")
    assert distraction == DISTRACTION

    study, _ = model.predict("Overleaf compile thesis chapter - Microsoft Edge msedge.exe")
    assert study == STUDY


def test_confidence_is_a_valid_probability(model):
    for title in ["YouTube", "lecture notes", "", "asdkjhasd"]:
        _, confidence = model.predict(title)
        assert 0.5 <= confidence <= 1.0


def test_unknown_text_stays_near_the_middle(model):
    _, confidence = model.predict("zzzz qqqq wwww")
    assert confidence < 0.75    # none of these words are familiar, so no strong opinion


# --------------------------------------------------------------------------- #
# Online learning
# --------------------------------------------------------------------------- #
def test_correction_moves_the_decision(model):
    title = "Kamen Rider Gavv episode 30 - Google Chrome chrome.exe"
    assert model.predict(title)[0] == DISTRACTION

    # Let's say it's actually research for a project. Teach it, more than
    # once — one example shouldn't be enough to change a strong belief, but
    # several in a row should.
    for _ in range(12):
        model.learn(title, STUDY)

    assert model.predict(title)[0] == STUDY


def test_learn_rejects_unknown_labels(model):
    with pytest.raises(ValueError):
        model.learn("something", "maybe")


def test_learning_grows_vocabulary(model):
    before = len(model.vocabulary)
    model.learn("Verilog testbench simulation modelsim.exe", STUDY)
    assert len(model.vocabulary) > before


# --------------------------------------------------------------------------- #
# Explainability
# --------------------------------------------------------------------------- #
def test_explain_surfaces_the_deciding_tokens(model):
    weights = dict(model.explain("Discord general chat discord.exe", top_n=8))
    # the word 'discord' should point strongly toward "distraction".
    assert weights.get("discord", 0) > 0


def test_explain_respects_top_n(model):
    assert len(model.explain("a b c d e f g h i j youtube discord steam", top_n=3)) <= 3


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def test_round_trip_preserves_predictions(model, tmp_path):
    path = tmp_path / "model.json"
    model.save(path)
    restored = NaiveBayesClassifier.load(path)

    for title in ["YouTube video", "lecture slides.pdf", "Discord"]:
        assert model.predict(title) == restored.predict(title)


def test_saved_model_is_readable_json(model, tmp_path):
    path = tmp_path / "model.json"
    model.save(path)
    data = json.loads(path.read_text())
    assert "token_counts" in data and "vocabulary" in data


def test_load_missing_file_returns_seeded_model(tmp_path):
    m = NaiveBayesClassifier.load(tmp_path / "nope.json")
    assert m.is_trained
    assert m.predict("Netflix watch now")[0] == DISTRACTION


def test_load_corrupt_file_falls_back_to_seed(tmp_path):
    path = tmp_path / "model.json"
    path.write_text("{ this is not json")
    m = NaiveBayesClassifier.load(path)
    assert m.is_trained