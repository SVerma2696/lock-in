"""Tests for the observation store that backs train.py."""

import json

import pytest

from lock_in.classifier import DISTRACTION, STUDY
from lock_in.observations import ObservationStore, normalise


@pytest.fixture
def store(tmp_path) -> ObservationStore:
    return ObservationStore(tmp_path / "observations.jsonl")


# --------------------------------------------------------------------------- #
# Normalisation / de-duplication
# --------------------------------------------------------------------------- #
def test_normalise_is_order_insensitive():
    assert normalise("Docs - Chrome") == normalise("Chrome - Docs")


def test_normalise_ignores_case_and_punctuation():
    assert normalise("Main.PY -- VS Code") == normalise("main py vs code")


def test_normalise_of_empty_text_is_empty():
    assert normalise("") == ""
    assert normalise("!!! ...") == ""


# --------------------------------------------------------------------------- #
# Recording
# --------------------------------------------------------------------------- #
def test_record_creates_a_row(store):
    record = store.record("general #chat Discord", process="discord.exe")
    assert record is not None
    assert record.count == 1
    assert len(store.all()) == 1


def test_repeat_sightings_increment_rather_than_duplicate(store):
    for _ in range(50):
        store.record("general #chat Discord", process="discord.exe")
    assert len(store.all()) == 1
    assert store.all()[0].count == 50


def test_empty_text_is_ignored(store):
    assert store.record("") is None
    assert store.record("   ") is None
    assert store.record("!!!") is None      # cleans up to nothing at all
    assert store.all() == []


def test_record_stores_the_models_opinion(store):
    record = store.record("YouTube", predicted=DISTRACTION, confidence=0.93)
    assert record["predicted"] == DISTRACTION
    assert record["confidence"] == pytest.approx(0.93)


def test_repeat_sighting_refreshes_the_prediction(store):
    store.record("YouTube", predicted=STUDY, confidence=0.51)
    record = store.record("YouTube", predicted=DISTRACTION, confidence=0.97)
    assert record["predicted"] == DISTRACTION
    assert record.count == 2


# --------------------------------------------------------------------------- #
# Labelling
# --------------------------------------------------------------------------- #
def test_set_label_marks_the_record(store):
    record = store.record("Steam Library", process="steam.exe")
    assert store.set_label(record["key"], DISTRACTION)
    assert store.all()[0].label == DISTRACTION


def test_set_label_on_missing_key_returns_false(store):
    assert not store.set_label("nope", STUDY)


def test_label_by_text_matches_on_normalised_form(store):
    store.record("Lecture Notes - Chrome")
    assert store.label_by_text("Chrome - lecture notes", STUDY)
    assert store.all()[0].label == STUDY


def test_labelled_records_leave_the_pending_queue(store):
    store.record("a study window")
    store.record("a distracting window")
    assert len(store.pending()) == 2

    store.label_by_text("a study window", STUDY)
    pending = store.pending()
    assert len(pending) == 1
    assert "distracting" in pending[0].text


def test_pending_is_sorted_by_sightings(store):
    store.record("rare window")
    for _ in range(10):
        store.record("frequent window")
    assert store.pending()[0].text == "frequent window"


def test_pending_respects_min_count(store):
    store.record("rare window")
    for _ in range(5):
        store.record("frequent window")
    assert len(store.pending(min_count=3)) == 1


def test_labelled_record_still_accumulates_sightings(store):
    store.record("Discord chat")
    store.label_by_text("Discord chat", DISTRACTION)
    store.record("Discord chat")
    record = store.all()[0]
    assert record.count == 2
    assert record.label == DISTRACTION      # doesn't go back into the "needs a label" pile


# --------------------------------------------------------------------------- #
# Training data
# --------------------------------------------------------------------------- #
def test_training_pairs_only_include_labelled(store):
    store.record("labelled one")
    store.record("unlabelled one")
    store.label_by_text("labelled one", STUDY)

    pairs = store.training_pairs()
    assert len(pairs) == 1
    assert pairs[0] == ("labelled one", STUDY)


def test_training_pairs_emit_once_regardless_of_visit_count(store):
    """A window seen 200 times must not take over the model's vocabulary."""
    for _ in range(200):
        store.record("Spotify playlist")
    store.label_by_text("Spotify playlist", DISTRACTION)
    assert len(store.training_pairs()) == 1


def test_extend_bulk_imports(store):
    added = store.extend([
        ("Overleaf thesis", STUDY),
        ("Reddit frontpage", DISTRACTION),
    ])
    assert added == 2
    assert len(store.training_pairs()) == 2


def test_extend_is_idempotent(store):
    pairs = [("Overleaf thesis", STUDY)]
    store.extend(pairs)
    store.extend(pairs)
    assert len(store.all()) == 1


# --------------------------------------------------------------------------- #
# Stats and purge
# --------------------------------------------------------------------------- #
def test_stats_counts_correctly(store):
    store.record("one")
    store.record("one")
    store.record("two")
    store.label_by_text("one", STUDY)

    stats = store.stats()
    assert stats["total"] == 2
    assert stats["labelled"] == 1
    assert stats["pending"] == 1
    assert stats["total_sightings"] == 3
    assert stats["by_label"] == {STUDY: 1}


def test_purge_keeps_labelled_data(store):
    store.record("keep me")
    store.record("drop me")
    store.label_by_text("keep me", STUDY)

    removed = store.purge_unlabelled()
    assert removed == 1
    assert len(store.all()) == 1
    assert store.all()[0].text == "keep me"


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def test_round_trip_through_disk(tmp_path):
    path = tmp_path / "obs.jsonl"
    first = ObservationStore(path)
    first.record("Discord chat", process="discord.exe")
    first.label_by_text("Discord chat", DISTRACTION)
    first.save()

    second = ObservationStore(path)
    assert len(second.all()) == 1
    assert second.all()[0].label == DISTRACTION
    assert second.training_pairs() == [("Discord chat", DISTRACTION)]


def test_saved_file_is_one_json_object_per_line(tmp_path):
    path = tmp_path / "obs.jsonl"
    store = ObservationStore(path)
    store.record("first window")
    store.record("second window")
    store.save()

    # each saved line should be its own valid, complete JSON entry
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    assert len(lines) == 2
    for line in lines:
        assert "text" in json.loads(line)


def test_corrupt_lines_are_skipped_not_fatal(tmp_path):
    path = tmp_path / "obs.jsonl"
    path.write_text(
        json.dumps({"text": "good record", "count": 1, "label": None}) + "\n"
        "{ this line is broken\n"
        + json.dumps({"text": "another good one", "count": 1, "label": None}) + "\n"
    )
    store = ObservationStore(path)
    assert len(store.all()) == 2


def test_missing_file_loads_empty(tmp_path):
    assert ObservationStore(tmp_path / "nothing.jsonl").all() == []


def test_save_is_a_noop_when_nothing_changed(tmp_path):
    path = tmp_path / "obs.jsonl"
    ObservationStore(path).save()
    assert not path.exists()        # don't leave a useless empty file behind