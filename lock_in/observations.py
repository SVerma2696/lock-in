"""
observations.py
===============
This file is a notebook that writes down what windows you had open, so we
can teach the guessing model to do better later.

The Activity tab in the app can only ever show you windows the model
**flagged**. That means you can only correct the times it wrongly accused
you — never the times a distracting app slipped right past it unnoticed.
That's the one mistake that actually costs you a study session, and you'd
never even find out about it.

This file fixes that. It writes down every different window it sees during a
focus block — flagged or not — along with what the model was thinking at the
time. Then `train.py label` walks you through them so you can correct any
mistakes.

How it's saved
------------------
Saved as a list, one line per window, at
`%APPDATA%\\Lock In\\observations.jsonl`:

    {"text": "...", "process": "chrome.exe", "title": "...", "count": 14,
     "first_seen": "2026-08-04T21:12:03", "last_seen": "...",
     "predicted": "study", "confidence": 0.61, "label": null}

`label` stays empty until you fill it in. We save it as one simple line per
entry on purpose: it's easy to add new lines, easy to search through, safe
if the file gets cut off mid-save (you'd lose one line, not everything), and
you could even open it in a plain text editor and label a bunch by hand
faster than clicking through the app.

Not counting the same window twice
-------------------------------------
Each window gets a matching "key" based on its cleaned-up text, so if you
visit the same window 200 times, that's one row with `count: 200` — not 200
separate rows. That count matters: the app you spent 40 minutes in is the
one most worth labelling carefully.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .classifier import tokenize


def normalise(text: str) -> str:
    """
    Turn a window's text into one standard "key" so we can tell if we've
    already seen this exact window before.

    We reuse the same word-splitting the guessing model uses, so two titles
    the model would treat as the same thing also get treated as the same
    thing here. We also sort the words, so word order doesn't matter —
    "Docs - Chrome" and "Chrome - Docs" become one entry instead of two you'd
    have to label separately.
    """
    return " ".join(sorted(set(tokenize(text))))


class Observation(dict):
    """
    One single window we recorded.

    This is built on top of a plain dictionary (instead of a fancier class)
    so it saves to and loads from JSON with zero extra work, and so that if
    you hand-edit the file and add an extra field yourself, it still loads
    fine without breaking.
    """

    @property
    def text(self) -> str:
        return self.get("text", "")

    @property
    def label(self) -> Optional[str]:
        return self.get("label")

    @property
    def count(self) -> int:
        return int(self.get("count", 1))

    @property
    def display(self) -> str:
        process = self.get("process", "")
        title = self.get("title", "")
        if process and title:
            return f"{process} — {title}"
        return process or title or self.text or "unknown window"


class ObservationStore:
    """
    Loads, records, labels, and saves the list of windows we've seen.

    Everything lives in memory while the app runs; the file on disk is just a
    backup copy. When we `save()`, we rewrite the whole file from scratch.
    That's totally fine here — even a heavy user only creates a few thousand
    entries a year, well under a megabyte — and it's much simpler than trying
    to carefully edit individual lines in a file people are meant to open and
    edit by hand anyway.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._records: Dict[str, Observation] = {}
        self._dirty = False
        self.load()

    # ------------------------------------------------------------------ #
    # Reading and writing the file
    # ------------------------------------------------------------------ #
    def load(self) -> None:
        """Read the saved file, skipping over any line that's broken."""
        self._records.clear()
        if not self.path.exists():
            return
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = Observation(json.loads(line))
                except json.JSONDecodeError:
                    # One broken line shouldn't cost you your whole training set.
                    continue
                key = record.get("key") or normalise(record.text)
                record["key"] = key
                self._records[key] = record
        except OSError:
            pass

    def save(self) -> None:
        """Save everything, oldest windows first."""
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(self._records.values(), key=lambda r: r.get("first_seen", ""))
        with self.path.open("w", encoding="utf-8") as handle:
            for record in ordered:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._dirty = False

    # ------------------------------------------------------------------ #
    # Writing down a window we saw
    # ------------------------------------------------------------------ #
    def record(
        self,
        text: str,
        process: str = "",
        title: str = "",
        predicted: Optional[str] = None,
        confidence: Optional[float] = None,
        blocked: bool = False,
    ) -> Optional[Observation]:
        """
        Add a new window, or update one we've already seen. Gives back the
        entry, or None if there was nothing worth recording.

        Even a window that's already been labelled still gets its count and
        last-seen time updated — that keeps an honest record of how much time
        you actually spend on it, without putting it back in the "needs a
        label" pile.
        """
        text = (text or "").strip()
        if not text:
            return None

        key = normalise(text)
        if not key:
            return None

        now = datetime.now().isoformat(timespec="seconds")
        existing = self._records.get(key)

        if existing is not None:
            existing["count"] = existing.count + 1
            existing["last_seen"] = now
            # Update the model's guess here too — handy for noticing exactly
            # when a correction changed its mind.
            if predicted is not None:
                existing["predicted"] = predicted
                existing["confidence"] = confidence
            self._dirty = True
            return existing

        record = Observation({
            "key": key,
            "text": text,
            "process": process,
            "title": title,
            "count": 1,
            "first_seen": now,
            "last_seen": now,
            "predicted": predicted,
            "confidence": confidence,
            "blocked": blocked,
            "label": None,
        })
        self._records[key] = record
        self._dirty = True
        return record

    # ------------------------------------------------------------------ #
    # Labelling
    # ------------------------------------------------------------------ #
    def set_label(self, key: str, label: Optional[str]) -> bool:
        """Set (or clear, with None) a window's label. True if that window existed."""
        record = self._records.get(key)
        if record is None:
            return False
        record["label"] = label
        record["labelled_at"] = datetime.now().isoformat(timespec="seconds")
        self._dirty = True
        return True

    def label_by_text(self, text: str, label: Optional[str]) -> bool:
        """The same as `set_label`, but you give it the raw title instead of the key."""
        return self.set_label(normalise(text), label)

    # ------------------------------------------------------------------ #
    # Looking things up
    # ------------------------------------------------------------------ #
    def all(self) -> List[Observation]:
        return list(self._records.values())

    def pending(self, min_count: int = 1) -> List[Observation]:
        """
        Windows still waiting to be labelled, most-seen ones first.

        Sorting this way puts the windows you spent the most time in at the
        top — so a few minutes of labelling gets you the most useful data.
        """
        items = [r for r in self._records.values()
                 if r.label is None and r.count >= min_count]
        return sorted(items, key=lambda r: r.count, reverse=True)

    def labelled(self) -> List[Observation]:
        return [r for r in self._records.values() if r.label is not None]

    def training_pairs(self) -> List[tuple]:
        """
        Gives back `(text, label)` pairs, ready to teach `NaiveBayesClassifier`.

        A window you saw 50 times is still just one example here, not 50.
        Counting it 50 times would let one app you happened to leave open all
        day take over the model's vocabulary — it would learn "what this
        person's laptop looks like" instead of "what studying looks like".
        """
        return [(r.text, r.label) for r in self.labelled() if r.label]

    def stats(self) -> dict:
        labelled = self.labelled()
        by_label: Dict[str, int] = {}
        for record in labelled:
            by_label[record.label] = by_label.get(record.label, 0) + 1
        return {
            "total": len(self._records),
            "labelled": len(labelled),
            "pending": len(self._records) - len(labelled),
            "by_label": by_label,
            "total_sightings": sum(r.count for r in self._records.values()),
        }

    def purge_unlabelled(self) -> int:
        """Throw away windows that were never labelled. Returns how many got removed."""
        pending = [r["key"] for r in self._records.values() if r.label is None]
        for key in pending:
            del self._records[key]
        self._dirty = bool(pending)
        return len(pending)

    def extend(self, pairs: Iterable[tuple]) -> int:
        """
        Bring in a big batch of `(text, label)` pairs at once, like from a CSV file.

        If a window is already recorded, this just updates it instead of
        making a duplicate — so importing the same file twice is harmless.
        """
        added = 0
        for text, label in pairs:
            record = self.record(text)
            if record is not None:
                record["label"] = label
                added += 1
        self._dirty = True
        return added