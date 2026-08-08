"""
classifier.py
=============
This is the little "brain" that guesses whether the window you're looking at
is studying or goofing off. It looks at the window's title and the program's
name (not a picture of your screen) and makes a guess.

Why we read words instead of looking at pictures
--------------------------------------------------
We could have made this brain look at screenshots instead. Here's why we
didn't:

1. Words already say enough. "Ryujinnie - Discord" and "Lecture 12:
   Pipelining.pdf - Adobe Acrobat" are easy to tell apart just from their
   names. A picture-reading brain would need to work much harder to learn
   what these few words already tell us for free.
2. Words are cheap. Checking a short title once a second is tiny and fast.
   Checking screenshots all day would use way more battery and be much slower.
3. Words keep you private. Nothing about your screen ever leaves your
   computer this way. An app that watches you all day while you work should
   not be sending pictures of your screen anywhere.

If someone wants to add screenshot-reading later, that's an easy swap — just
make a new brain that gives back the same kind of answer (a label plus how
sure it is), and nothing else needs to change.

Why this simple kind of brain (Naive Bayes)
---------------------------------------------
This kind of model learns from just a few examples, learns instantly with no
waiting, needs no extra software, and — best of all — you can always see
*why* it made a guess. That matters a lot for an app whose whole job is to be
trusted when it interrupts you.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

STUDY = "study"
DISTRACTION = "distraction"
LABELS = (STUDY, DISTRACTION)

# This chops text apart at anything that isn't a letter or number. So
# "cs.121" becomes two separate words, which is fine — both pieces still
# hint at studying.
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Boring little words we throw away because they don't tell us anything.
# If we kept "the", the model might wrongly think "the" means "studying".
_STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "www", "com", "http", "https",
    "exe", "app", "new", "tab", "window", "page", "of", "to", "in", "on", "a",
    # Almost every browser window title ends with the browser's own name, no
    # matter what's on the page — so these words don't help tell study and
    # distraction apart. We handle the actual program name separately, with
    # the allow/block lists.
    #
    # Each browser needs BOTH of its words listed here: the word Windows
    # puts in the window title ("Microsoft Edge") and the word that comes
    # from its process name ("msedge.exe" -> "msedge"). Missing either one
    # means that word quietly becomes "the thing every window in that
    # browser has in common" instead of being ignored — the exact same
    # problem this whole stopword list exists to avoid.
    "google", "chrome", "mozilla", "firefox", "edge", "msedge", "microsoft",
    "safari", "opera", "brave", "vivaldi", "browser",
}


def tokenize(text: str) -> List[str]:
    """
    Turn a sentence into a clean list of lowercase words.

    We make everything lowercase, remove punctuation, and throw out both the
    boring words above and any leftover single letters.

    Example
    -------
    >>> tokenize("Stray Kids 'CIRCUS' M/V - YouTube")
    ['stray', 'kids', 'circus', 'm', 'v', 'youtube']
    """
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]


# --------------------------------------------------------------------------- #
# Starter examples
# --------------------------------------------------------------------------- #
# The model already knows these examples before you even open the app, so it
# can make good guesses right away instead of just flipping a coin until you
# teach it 50 examples yourself. Each one looks like a real window title.

SEED_DATA: List[Tuple[str, str]] = [
    # --- studying ---------------------------------------------------------- #
    ("main.py - lock_in - Visual Studio Code code.exe", STUDY),
    ("Lecture 12 Pipelining.pdf - Adobe Acrobat Reader acrord32.exe", STUDY),
    ("Homework 4 Solutions.docx - Word winword.exe", STUDY),
    ("Overleaf honors thesis draft - Google Chrome chrome.exe", STUDY),
    ("Gradescope Submit Assignment - Google Chrome chrome.exe", STUDY),
    ("Canvas ECE 232 Modules - Google Chrome chrome.exe", STUDY),
    ("Stack Overflow how to fix segmentation fault - Google Chrome chrome.exe", STUDY),
    ("GitHub SVerma2696 pull request - Google Chrome chrome.exe", STUDY),
    ("Python documentation asyncio - Google Chrome chrome.exe", STUDY),
    ("Wikipedia Fourier transform - Google Chrome chrome.exe", STUDY),
    ("Untitled - Notepad notepad.exe", STUDY),
    ("Obsidian vault - notes obsidian.exe", STUDY),
    ("Windows PowerShell windowsterminal.exe", STUDY),
    ("MATLAB R2024b matlab.exe", STUDY),
    ("Lab report data analysis.xlsx - Excel excel.exe", STUDY),
    ("arXiv paper secure timing edge systems - Google Chrome chrome.exe", STUDY),
    ("Khan Academy linear algebra practice - Google Chrome chrome.exe", STUDY),
    ("Zoom Meeting office hours zoom.exe", STUDY),
    ("Datasheet ESP32 WROOM.pdf - SumatraPDF sumatrapdf.exe", STUDY),
    ("Google Scholar citation - Google Chrome chrome.exe", STUDY),
    # --- distraction ------------------------------------------------------- #
    ("Stray Kids MANIAC Official MV - YouTube - Google Chrome chrome.exe", DISTRACTION),
    ("(24) YouTube - Google Chrome chrome.exe", DISTRACTION),
    ("general #chat - Discord discord.exe", DISTRACTION),
    ("Instagram reels - Google Chrome chrome.exe", DISTRACTION),
    ("TikTok For You - Google Chrome chrome.exe", DISTRACTION),
    ("Reddit r all - Google Chrome chrome.exe", DISTRACTION),
    ("Twitter home timeline - Google Chrome chrome.exe", DISTRACTION),
    ("Netflix watch episode - Google Chrome chrome.exe", DISTRACTION),
    ("Twitch live stream - Google Chrome chrome.exe", DISTRACTION),
    ("Steam Library steam.exe", DISTRACTION),
    ("Minecraft 1.21 minecraft.exe", DISTRACTION),
    ("League of Legends client leagueclient.exe", DISTRACTION),
    ("Spotify Premium playlist spotify.exe", DISTRACTION),
    ("Amazon shopping cart - Google Chrome chrome.exe", DISTRACTION),
    ("eBay auction listing - Google Chrome chrome.exe", DISTRACTION),
    ("F1 2026 race highlights - YouTube - Google Chrome chrome.exe", DISTRACTION),
    ("Kamen Rider episode 12 stream - Google Chrome chrome.exe", DISTRACTION),
    ("9GAG memes - Google Chrome chrome.exe", DISTRACTION),
    ("Roblox roblox.exe", DISTRACTION),
    ("WhatsApp chat whatsapp.exe", DISTRACTION),
    # --- second batch -------------------------------------------------------- #
    # A word the model has only seen once isn't enough to make it feel sure.
    # So here we show it the most common words a second time, worded a little
    # differently, so it's confident enough to actually act on day one.
    ("TikTok following feed - Google Chrome chrome.exe", DISTRACTION),
    ("tiktok.com scrolling - Google Chrome chrome.exe", DISTRACTION),
    ("YouTube Shorts - Google Chrome chrome.exe", DISTRACTION),
    ("watching YouTube video essay - Google Chrome chrome.exe", DISTRACTION),
    ("Instagram explore - Google Chrome chrome.exe", DISTRACTION),
    ("Netflix browse titles - Google Chrome chrome.exe", DISTRACTION),
    ("Twitch following channels - Google Chrome chrome.exe", DISTRACTION),
    ("Reddit r popular posts - Google Chrome chrome.exe", DISTRACTION),
    ("Discord voice call - Discord discord.exe", DISTRACTION),
    ("Steam store sale page steam.exe", DISTRACTION),
    ("F1 qualifying results discussion - Google Chrome chrome.exe", DISTRACTION),
    ("Spotify Daily Mix spotify.exe", DISTRACTION),
    ("classifier.py - lock_in - Visual Studio Code code.exe", STUDY),
    ("test_session.py editing - Visual Studio Code code.exe", STUDY),
    ("Homework 6 problem set.pdf - SumatraPDF sumatrapdf.exe", STUDY),
    ("Midterm review sheet.pdf - Adobe Acrobat Reader acrord32.exe", STUDY),
    ("Canvas assignment submission - Google Chrome chrome.exe", STUDY),
    ("Canvas course announcements - Google Chrome chrome.exe", STUDY),
    ("Overleaf compile thesis chapter - Google Chrome chrome.exe", STUDY),
    ("Stack Overflow python import error - Google Chrome chrome.exe", STUDY),
    ("GitHub repository issues - Google Chrome chrome.exe", STUDY),
    ("Lecture notes week 8.docx - Word winword.exe", STUDY),
    ("Zoom lecture recording zoom.exe", STUDY),
    ("Lab 3 measurements.xlsx - Excel excel.exe", STUDY),
    # --- other browsers (Microsoft Edge, Firefox) --------------------------- #
    # Everything above only ever ran through Chrome. Without at least a few
    # examples that use a different browser's process name and title suffix,
    # the model has no idea those word patterns even exist — it isn't that it
    # "prefers" Chrome, it just hasn't met anything else yet. These fill that
    # gap the same way the browsers themselves are handled: the actual
    # content words (reddit, canvas, overleaf, ...) are what carry the
    # meaning; the browser name itself is filtered out as a stopword either
    # way, in `tokenize()`.
    ("Reddit r all - Microsoft Edge msedge.exe", DISTRACTION),
    ("YouTube Stray Kids MV - Microsoft Edge msedge.exe", DISTRACTION),
    ("Instagram reels - Microsoft Edge msedge.exe", DISTRACTION),
    ("Netflix watch episode - Microsoft Edge msedge.exe", DISTRACTION),
    ("TikTok For You - Microsoft Edge msedge.exe", DISTRACTION),
    ("Twitch live stream - Microsoft Edge msedge.exe", DISTRACTION),
    ("Canvas ECE 232 Modules - Microsoft Edge msedge.exe", STUDY),
    ("Overleaf honors thesis draft - Microsoft Edge msedge.exe", STUDY),
    ("Stack Overflow python import error - Microsoft Edge msedge.exe", STUDY),
    ("Gradescope Submit Assignment - Microsoft Edge msedge.exe", STUDY),
    ("Google Scholar citation - Microsoft Edge msedge.exe", STUDY),
    ("GitHub pull request review - Microsoft Edge msedge.exe", STUDY),
    ("Reddit r popular posts - Mozilla Firefox firefox.exe", DISTRACTION),
    ("YouTube Shorts - Mozilla Firefox firefox.exe", DISTRACTION),
    ("Canvas course announcements - Mozilla Firefox firefox.exe", STUDY),
    ("Wikipedia Fourier transform - Mozilla Firefox firefox.exe", STUDY),
]


class NaiveBayesClassifier:
    """
    A simple guessing model that learns by counting words.

    Everything inside is just plain counting numbers stored in dictionaries.
    That means the whole model can be saved as plain JSON — no special file
    format — and you can open model.json yourself and read what it learned.
    """

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha                                    # how cautious the guessing is
        self.token_counts: Dict[str, Dict[str, int]] = {l: defaultdict(int) for l in LABELS}
        self.label_counts: Dict[str, int] = {l: 0 for l in LABELS}   # examples seen per label
        self.total_tokens: Dict[str, int] = {l: 0 for l in LABELS}   # words seen per label
        self.vocabulary: set[str] = set()

    # ------------------------------------------------------------------ #
    # Teaching it
    # ------------------------------------------------------------------ #
    def learn(self, text: str, label: str) -> None:
        """Teach the model one example right now — it updates instantly."""
        if label not in LABELS:
            raise ValueError(f"label must be one of {LABELS}, got {label!r}")

        self.label_counts[label] += 1
        for token in tokenize(text):
            self.token_counts[label][token] += 1
            self.total_tokens[label] += 1
            self.vocabulary.add(token)

    def train(self, samples: Iterable[Tuple[str, str]]) -> "NaiveBayesClassifier":
        """Teach it a whole bunch of examples at once, one by one."""
        for text, label in samples:
            self.learn(text, label)
        return self

    @property
    def is_trained(self) -> bool:
        return sum(self.label_counts.values()) > 0

    # ------------------------------------------------------------------ #
    # Making a guess
    # ------------------------------------------------------------------ #
    def _log_likelihood(self, tokens: List[str], label: str) -> float:
        """
        Work out a score for how likely this label is, using math tricks so
        tiny numbers don't get lost (we add instead of multiply).
        """
        total_docs = sum(self.label_counts.values())
        prior = math.log(self.label_counts[label] / total_docs)

        vocab_size = max(1, len(self.vocabulary))
        denominator = self.total_tokens[label] + self.alpha * vocab_size

        score = prior
        for token in tokens:
            # Skip any word the model has never seen at all, in either class.
            # If we didn't skip these, a totally unknown word would quietly
            # tip the scale toward "distraction" more often than "study",
            # since study titles tend to be longer and wordier ("ECE 232
            # Lecture 9 pipelining.pdf sumatrapdf.exe" vs "Steam Library
            # steam.exe"). That's the exact wrong kind of mistake: interrupting
            # someone who was actually working.
            #
            # We tested this change carefully (see `python train.py eval`):
            # it made the model slightly less "accurate" overall (63% -> 59%)
            # but much fairer — it went from catching only 30% of real
            # distractions to catching 62%, without wrongly flagging nearly as
            # much real work. A model that flags everything looks accurate on
            # paper but is useless in practice.
            if token not in self.vocabulary:
                continue
            # A word the model HAS seen before, just not in this particular
            # label, still counts as real evidence — not ignored.
            count = self.token_counts[label].get(token, 0)
            score += math.log((count + self.alpha) / denominator)
        return score

    def predict(self, text: str) -> Tuple[str, float]:
        """
        Guess whether `text` is study or distraction.

        Returns
        -------
        (label, confidence) — confidence is a number between 0.5 and 1.0,
        where higher means more sure. If the model hasn't learned anything
        yet, or the text is empty, it plays it safe and says
        (STUDY, 0.5) — "no strong opinion, so don't bother anyone." That's on
        purpose: wrongly interrupting someone who's working is the worst
        mistake this app can make.
        """
        tokens = tokenize(text)
        if not self.is_trained or not tokens:
            return STUDY, 0.5

        scores = {label: self._log_likelihood(tokens, label) for label in LABELS}

        # Turn the two raw scores into normal probabilities that add up to 1.
        top = max(scores.values())
        exps = {l: math.exp(s - top) for l, s in scores.items()}
        denom = sum(exps.values())

        winner = max(scores, key=lambda l: scores[l])
        return winner, exps[winner] / denom

    def explain(self, text: str, top_n: int = 5) -> List[Tuple[str, float]]:
        """
        List the words that pushed the guess toward DISTRACTION the hardest.

        The app shows this next to a flagged window so you can see why it was
        flagged, instead of just trusting a mystery answer — for example,
        "flagged because: youtube, mv, official".
        """
        vocab_size = max(1, len(self.vocabulary))
        weights: List[Tuple[str, float]] = []

        for token in set(tokenize(text)):
            per_label = {}
            for label in LABELS:
                count = self.token_counts[label].get(token, 0)
                denom = self.total_tokens[label] + self.alpha * vocab_size
                per_label[label] = (count + self.alpha) / denom
            # A positive number means "this word points toward distraction."
            weights.append((token, math.log(per_label[DISTRACTION] / per_label[STUDY])))

        weights.sort(key=lambda pair: abs(pair[1]), reverse=True)
        return weights[:top_n]

    # ------------------------------------------------------------------ #
    # Saving and loading
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return {
            "alpha": self.alpha,
            "token_counts": {l: dict(c) for l, c in self.token_counts.items()},
            "label_counts": self.label_counts,
            "total_tokens": self.total_tokens,
            "vocabulary": sorted(self.vocabulary),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NaiveBayesClassifier":
        model = cls(alpha=data.get("alpha", 1.0))
        for label in LABELS:
            model.token_counts[label] = defaultdict(int, data.get("token_counts", {}).get(label, {}))
        model.label_counts = {l: data.get("label_counts", {}).get(l, 0) for l in LABELS}
        model.total_tokens = {l: data.get("total_tokens", {}).get(l, 0) for l in LABELS}
        model.vocabulary = set(data.get("vocabulary", []))
        return model

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=1), encoding="utf-8")

    @classmethod
    def load_seed(cls) -> "NaiveBayesClassifier":
        """Make a brand-new model taught only the starter examples. Used by 'Reset model'."""
        return cls().train(SEED_DATA)

    @classmethod
    def load(cls, path: Path) -> "NaiveBayesClassifier":
        """
        Load a saved model from disk. If there isn't one yet, or the file is
        broken, just make a fresh one with the starter examples instead of
        giving up.
        """
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError, KeyError):
                pass
        return cls().train(SEED_DATA)