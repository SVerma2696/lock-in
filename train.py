"""
train.py
========
This is a command-line tool (type commands instead of clicking) for teaching
the Lock In guessing model.

The Activity tab in the app works fine for quick one-off corrections, but it
only ever shows you windows the model **flagged** — so you can only ever fix
the times it wrongly accused you. This tool instead reads `observations.jsonl`,
which records every window seen during focus, so you can also catch the
distracting apps that slipped right past it.

Commands
--------
    python train.py record            watch windows and write them down (Ctrl+C to stop)
    python train.py label             go through unlabelled windows, one keypress each
    python train.py rebuild           retrain the model from the starter examples + your labels
    python train.py stats             model size, label balance, most telling words
    python train.py eval              test the model on data it hasn't seen yet
    python train.py test "<title>"    guess one window title and show why
    python train.py import <file>     bring in a bunch of label,text pairs from a CSV/TSV file
    python train.py export <file>     save your labelled data as a CSV file
    python train.py purge             remove unlabelled windows

The usual way to use this
----------------------------
    1. Use the app normally for a few days (writing things down is on by default).
    2. `python train.py label`   — about 5 minutes, most-seen windows first.
    3. `python train.py rebuild` — folds your answers into the model.
    4. `python train.py eval`    — checks that it actually got better, not worse.
"""

from __future__ import annotations

import csv
import random
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from lock_in.classifier import (
    DISTRACTION,
    SEED_DATA,
    STUDY,
    NaiveBayesClassifier,
    tokenize,
)
from lock_in.config import Config, MODEL_PATH, OBSERVATIONS_PATH
from lock_in.observations import Observation, ObservationStore

# --------------------------------------------------------------------------- #
# Little helpers for printing nice, colorful text
# --------------------------------------------------------------------------- #
# These color codes work in newer terminals, but show up as garbled text in
# the old classic Windows console — so `--no-color` (or piping the output
# somewhere) turns them off.
USE_COLOR = sys.stdout.isatty() and "--no-color" not in sys.argv

BOLD = "\033[1m" if USE_COLOR else ""
DIM = "\033[2m" if USE_COLOR else ""
RED = "\033[31m" if USE_COLOR else ""
GREEN = "\033[32m" if USE_COLOR else ""
YELLOW = "\033[33m" if USE_COLOR else ""
CYAN = "\033[36m" if USE_COLOR else ""
RESET = "\033[0m" if USE_COLOR else ""


def heading(text: str) -> None:
    print(f"\n{BOLD}{text}{RESET}")
    print(DIM + "─" * min(len(text), 60) + RESET)


def colour_label(label: Optional[str]) -> str:
    if label == STUDY:
        return f"{GREEN}study{RESET}"
    if label == DISTRACTION:
        return f"{RED}distraction{RESET}"
    return f"{DIM}unlabelled{RESET}"


# --------------------------------------------------------------------------- #
# record
# --------------------------------------------------------------------------- #
def cmd_record(args: List[str]) -> int:
    """
    Watches your active window and writes it down, until you stop it.

    Handy when you want a bunch of training examples fast, without running a
    full Pomodoro session — leave this running through a normal afternoon and
    you'll have a few hundred different windows recorded by evening.
    """
    from lock_in.monitor import BACKEND_AVAILABLE, get_active_window

    if not BACKEND_AVAILABLE:
        print(f"{RED}No window-detection backend on this platform.{RESET}")
        print("On Windows: pip install pywin32 psutil")
        return 1

    interval = 1.0
    if "--interval" in args:
        interval = float(args[args.index("--interval") + 1])

    store = ObservationStore(OBSERVATIONS_PATH)
    model = NaiveBayesClassifier.load(MODEL_PATH)

    heading("Recording")
    print(f"Polling every {interval:g}s. Ctrl+C to stop and save.")
    print(f"Writing to {DIM}{OBSERVATIONS_PATH}{RESET}\n")

    seen_this_run: set[str] = set()
    last_key = None

    try:
        while True:
            window = get_active_window()
            if window.text.strip():
                predicted, confidence = model.predict(window.text)
                record = store.record(
                    text=window.text,
                    process=window.process_name,
                    title=window.title,
                    predicted=predicted,
                    confidence=confidence,
                )
                if record is not None and record["key"] != last_key:
                    last_key = record["key"]
                    is_new = record["key"] not in seen_this_run
                    seen_this_run.add(record["key"])
                    marker = f"{CYAN}new{RESET}" if is_new else f"{DIM}seen{RESET}"
                    print(f"  [{marker}] {window.display[:58]:<58} "
                          f"{colour_label(predicted)} {confidence:.0%}")

            # Save regularly, so force-closing the window doesn't lose everything.
            if len(seen_this_run) % 25 == 0:
                store.save()
            time.sleep(interval)

    except KeyboardInterrupt:
        pass

    store.save()
    stats = store.stats()
    print(f"\n{GREEN}Saved.{RESET} {len(seen_this_run)} distinct windows this run, "
          f"{stats['pending']} total waiting to be labelled.")
    print(f"Next: {BOLD}python train.py label{RESET}")
    return 0


# --------------------------------------------------------------------------- #
# label
# --------------------------------------------------------------------------- #
def cmd_label(args: List[str]) -> int:
    """
    Walks you through unlabelled windows one at a time, most-seen ones first.

    Just one keypress per window — the whole point is that this is way
    faster than clicking through the app. Every answer is saved to disk right
    away, so quitting partway through never loses anything.
    """
    min_count = 1
    if "--min-count" in args:
        min_count = int(args[args.index("--min-count") + 1])

    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    store = ObservationStore(OBSERVATIONS_PATH)
    model = NaiveBayesClassifier.load(MODEL_PATH)

    pending = store.pending(min_count=min_count)
    if limit:
        pending = pending[:limit]

    if not pending:
        print(f"{GREEN}Nothing to label.{RESET} "
              f"Run the app (or `train.py record`) to collect some windows first.")
        return 0

    heading(f"Labelling {len(pending)} windows")
    print(f"{BOLD}s{RESET} = study   {BOLD}d{RESET} = distraction   "
          f"{BOLD}enter{RESET} = accept the model's guess   "
          f"{BOLD}k{RESET} = skip   {BOLD}q{RESET} = save and quit\n")

    labelled = 0
    agreed = 0

    for index, record in enumerate(pending, start=1):
        # We ask the model fresh instead of trusting record["predicted"].
        # That saved value is from whenever the window was first seen —
        # maybe days ago — and since every answer here teaches the model
        # right away, its guesses can change several times in one run.
        # Showing an old guess could mean pressing enter accepts something
        # the model doesn't even believe anymore.
        guess, confidence = model.predict(record.text)

        print(f"{DIM}[{index}/{len(pending)}]{RESET} {BOLD}{record.display[:70]}{RESET}")
        print(f"     seen {record.count}×  ·  model says {colour_label(guess)} "
              f"({confidence:.0%})")

        # Show the words behind the guess, so it's never a mystery — you can
        # double check it makes sense before agreeing.
        top = model.explain(record.text, top_n=4)
        if top:
            rendered = ", ".join(
                f"{token}{'+' if weight > 0 else '-'}" for token, weight in top
            )
            print(f"     {DIM}signal: {rendered}{RESET}")

        try:
            answer = input("     > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if answer == "q":
            break
        if answer == "k":
            print()
            continue

        if answer == "":
            label = guess
            agreed += 1
        elif answer.startswith("s"):
            label = STUDY
        elif answer.startswith("d"):
            label = DISTRACTION
        else:
            print(f"     {YELLOW}didn't catch that — skipping{RESET}\n")
            continue

        store.set_label(record["key"], label)
        model.learn(record.text, label)
        labelled += 1

        # Save after every single answer. Labelling takes effort; losing it would be worse.
        store.save()
        model.save(MODEL_PATH)
        print(f"     {colour_label(label)}\n")

    stats = store.stats()
    heading("Done")
    print(f"Labelled {labelled} this run ({agreed} were the model's own guess).")
    print(f"Training set: {stats['labelled']} labelled, {stats['pending']} pending.")
    if stats["by_label"]:
        parts = ", ".join(f"{colour_label(k)} {v}" for k, v in stats["by_label"].items())
        print(f"Balance: {parts}")
    print(f"\nNext: {BOLD}python train.py rebuild{RESET} then {BOLD}python train.py eval{RESET}")
    return 0


# --------------------------------------------------------------------------- #
# rebuild
# --------------------------------------------------------------------------- #
def cmd_rebuild(args: List[str]) -> int:
    """
    Trains the model again from nothing: starter examples + every window
    you've labelled.

    Worth doing every so often, because `learn()` just adds on top of what's
    there — labelling the same window twice would count it twice. Rebuilding
    fixes that back to one example per window.

    `--no-seed` trains using only your own data, which is an honest test of
    whether you've collected enough examples to stand on your own yet.
    """
    store = ObservationStore(OBSERVATIONS_PATH)
    pairs = store.training_pairs()

    if not pairs and "--no-seed" in args:
        print(f"{RED}No labelled data, and --no-seed leaves nothing to train on.{RESET}")
        return 1

    model = NaiveBayesClassifier()
    if "--no-seed" not in args:
        model.train(SEED_DATA)
    model.train(pairs)
    model.save(MODEL_PATH)

    heading("Rebuilt")
    seed_count = 0 if "--no-seed" in args else len(SEED_DATA)
    print(f"Seed examples:  {seed_count}")
    print(f"Your labels:    {len(pairs)}")
    print(f"Vocabulary:     {len(model.vocabulary)} tokens")
    print(f"Saved to {DIM}{MODEL_PATH}{RESET}")
    return 0


# --------------------------------------------------------------------------- #
# stats
# --------------------------------------------------------------------------- #
def cmd_stats(args: List[str]) -> int:
    """Shows the model's size, its label balance, and its most telling words."""
    store = ObservationStore(OBSERVATIONS_PATH)
    model = NaiveBayesClassifier.load(MODEL_PATH)
    stats = store.stats()

    heading("Model")
    total = sum(model.label_counts.values())
    print(f"Examples:    {total}  "
          f"({model.label_counts[STUDY]} study / "
          f"{model.label_counts[DISTRACTION]} distraction)")
    print(f"Vocabulary:  {len(model.vocabulary)} tokens")

    # Balance matters: a model taught mostly with study examples gets used
    # to guessing "allowed" and quietly stops catching distractions.
    if total:
        skew = abs(model.label_counts[STUDY] - model.label_counts[DISTRACTION]) / total
        if skew > 0.4:
            print(f"{YELLOW}Warning: classes are {skew:.0%} skewed. "
                  f"Label more of the smaller class.{RESET}")

    heading("Observations")
    print(f"Distinct windows:  {stats['total']}")
    print(f"Labelled:          {stats['labelled']}")
    print(f"Pending:           {stats['pending']}")
    print(f"Total sightings:   {stats['total_sightings']}")

    heading("Most informative tokens")
    weights = _token_weights(model)
    print(f"\n{RED}Toward distraction{RESET}")
    for token, weight in weights[:10]:
        print(f"  {token:<24} {weight:+.2f}")
    print(f"\n{GREEN}Toward study{RESET}")
    for token, weight in list(reversed(weights))[:10]:
        print(f"  {token:<24} {weight:+.2f}")
    return 0


def _token_weights(model: NaiveBayesClassifier) -> List[Tuple[str, float]]:
    """
    Gives a weight to every word the model knows, most-distracting first.

    This reuses `explain()` by handing it every single known word at once,
    as if it were one giant window title — the exact same math, just
    applied to everything.

    `explain()` normally sorts by how strong a word's opinion is either way
    — good for explaining one title. Here we want the two extremes kept
    apart instead, so we re-sort by the actual signed number: most-
    distracting words at the top, most-studying words at the bottom.
    """
    if not model.vocabulary:
        return []
    weights = model.explain(" ".join(model.vocabulary), top_n=len(model.vocabulary))
    return sorted(weights, key=lambda pair: pair[1], reverse=True)


# --------------------------------------------------------------------------- #
# eval
# --------------------------------------------------------------------------- #
def cmd_eval(args: List[str]) -> int:
    """
    Tests the model fairly: teach it a random 70% of your examples, then
    quiz it on the other 30% it's never seen.

    We show results split by category, because one overall score can be
    misleading. A model that just says "study" for everything would score
    80% on a set that's 80% study — while being completely useless. The
    "distraction recall" number is what actually tells you whether the app
    will catch you slacking off.
    """
    repeats = 5
    if "--repeats" in args:
        repeats = int(args[args.index("--repeats") + 1])

    store = ObservationStore(OBSERVATIONS_PATH)
    data = list(SEED_DATA) + store.training_pairs()
    if "--mine-only" in args:
        data = store.training_pairs()

    if len(data) < 10:
        print(f"{RED}Only {len(data)} examples — too few to evaluate meaningfully.{RESET}")
        print("Label a few dozen windows first.")
        return 1

    heading(f"Hold-out evaluation ({len(data)} examples, {repeats} random splits)")

    accuracies = []
    recalls = {STUDY: [], DISTRACTION: []}
    precisions = {STUDY: [], DISTRACTION: []}
    overlaps = []

    for seed in range(repeats):
        # We use a fixed random seed each time, so the numbers come out the same every run.
        shuffled = list(data)
        random.Random(seed).shuffle(shuffled)
        split = int(len(shuffled) * 0.7)
        train, test = shuffled[:split], shuffled[split:]

        model = NaiveBayesClassifier().train(train)

        correct = 0
        # counts[actual][predicted]
        counts = {a: {p: 0 for p in (STUDY, DISTRACTION)} for a in (STUDY, DISTRACTION)}

        known = seen = 0
        for text, actual in test:
            predicted, _ = model.predict(text)
            counts[actual][predicted] += 1
            if predicted == actual:
                correct += 1

            # How many of this title's words had the model actually seen
            # before? This number is what tells apart "my model is bad" from
            # "I just haven't given it enough examples yet" — and those two
            # problems need opposite fixes.
            tokens = tokenize(text)
            seen += len(tokens)
            known += sum(1 for t in tokens if t in model.vocabulary)

        accuracies.append(correct / len(test) if test else 0.0)
        overlaps.append(known / seen if seen else 0.0)

        for label in (STUDY, DISTRACTION):
            true_positive = counts[label][label]
            actual_total = sum(counts[label].values())
            predicted_total = sum(counts[a][label] for a in (STUDY, DISTRACTION))
            recalls[label].append(true_positive / actual_total if actual_total else 0.0)
            precisions[label].append(true_positive / predicted_total if predicted_total else 0.0)

    def mean(values) -> float:
        return sum(values) / len(values) if values else 0.0

    print(f"Accuracy:              {mean(accuracies):.1%}")
    print()
    for label in (DISTRACTION, STUDY):
        print(f"{colour_label(label)}")
        print(f"  precision  {mean(precisions[label]):.1%}   "
              f"{DIM}(when it says this, how often it's right){RESET}")
        print(f"  recall     {mean(recalls[label]):.1%}   "
              f"{DIM}(of all real cases, how many it caught){RESET}")

    overlap = mean(overlaps)
    print()
    print(f"Vocabulary overlap:    {overlap:.0%}   "
          f"{DIM}(share of test-title words the model had seen before){RESET}")

    print()
    # We check these in order of importance. Low overlap matters most: no
    # amount of fiddling with settings fixes a model that's never seen the
    # words it's trying to judge — adjusting thresholds on a starved model
    # just moves the problem around instead of fixing it. So we mention that
    # first, or the rest of this advice would be misleading.
    distraction_recall = mean(recalls[DISTRACTION])
    study_precision = mean(precisions[STUDY])

    if overlap < 0.6:
        print(f"{YELLOW}Overlap is low — most test words were never seen in training.{RESET}")
        print("  The bottleneck is data volume, not tuning. Numbers above will stay")
        print("  near chance until you have a few hundred labelled windows.")
        print(f"  Keep using the app, then {BOLD}python train.py label{RESET} again.")
        print(f"  {DIM}Meanwhile the block/allow lists do the real work — they're")
        print(f"  exact matches and don't need training at all.{RESET}")
    elif distraction_recall < 0.7:
        print(f"{YELLOW}Low distraction recall — it's missing things. "
              f"Label more distraction examples, or lower classifier_threshold.{RESET}")
    elif study_precision < 0.8:
        print(f"{YELLOW}It's interrupting you while you work. "
              f"Label more study examples, or raise classifier_threshold.{RESET}")
    else:
        print(f"{GREEN}Healthy. Both classes are being handled well.{RESET}")

    if len(data) < 150:
        print(f"\n{DIM}Note: {len(data)} examples is a small corpus — expect these")
        print(f"numbers to swing several points between runs.{RESET}")
    return 0


# --------------------------------------------------------------------------- #
# test
# --------------------------------------------------------------------------- #
def cmd_test(args: List[str]) -> int:
    """Guesses on one window title, and shows the words behind the guess."""
    text = " ".join(a for a in args if not a.startswith("--")).strip()
    if not text:
        print('Usage: python train.py test "Some Window Title - App"')
        return 1

    config = Config.load()
    model = NaiveBayesClassifier.load(MODEL_PATH)
    label, confidence = model.predict(text)

    heading("Prediction")
    print(f"Input:       {text}")
    print(f"Verdict:     {colour_label(label)} at {confidence:.1%} confidence")

    would_block = label == DISTRACTION and confidence >= config.classifier_threshold
    print(f"Threshold:   {config.classifier_threshold:.0%}")
    print(f"Would block: {RED + 'yes' + RESET if would_block else GREEN + 'no' + RESET}")

    heading("Why")
    for token, weight in model.explain(text, top_n=8):
        direction = f"{RED}distraction{RESET}" if weight > 0 else f"{GREEN}study{RESET}"
        print(f"  {token:<22} {weight:+.2f}  → {direction}")
    return 0


# --------------------------------------------------------------------------- #
# import / export
# --------------------------------------------------------------------------- #
def cmd_import(args: List[str]) -> int:
    """
    Brings in a whole batch of `label,text` rows from a CSV or TSV file.

    The fastest way to teach the model your own habits: type out forty lines
    in a text editor in five minutes, instead of waiting to happen to open
    each app one at a time.
    """
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print("Usage: python train.py import <file.csv>")
        print('Each row: label,text   e.g.  distraction,"Reddit - Google Chrome chrome.exe"')
        return 1

    path = Path(paths[0])
    if not path.exists():
        print(f"{RED}No such file: {path}{RESET}")
        return 1

    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    pairs: List[Tuple[str, str]] = []
    skipped = 0

    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle, delimiter=delimiter):
            if len(row) < 2:
                skipped += 1
                continue
            label = row[0].strip().lower()
            text = row[1].strip()
            # Allow the short "s"/"d" versions, and skip a header row if there is one.
            if label.startswith("s"):
                label = STUDY
            elif label.startswith("d"):
                label = DISTRACTION
            else:
                skipped += 1
                continue
            if text:
                pairs.append((text, label))

    store = ObservationStore(OBSERVATIONS_PATH)
    added = store.extend(pairs)
    store.save()

    heading("Imported")
    print(f"Added or updated: {added}")
    if skipped:
        print(f"{DIM}Skipped {skipped} unparseable rows (headers, blanks).{RESET}")
    print(f"\nNext: {BOLD}python train.py rebuild{RESET}")
    return 0


def cmd_export(args: List[str]) -> int:
    """Saves your labelled data to a CSV file — for backups, or editing in a spreadsheet."""
    paths = [a for a in args if not a.startswith("--")]
    target = Path(paths[0]) if paths else Path("lockin_training_data.csv")

    store = ObservationStore(OBSERVATIONS_PATH)
    rows = store.labelled()

    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["label", "text", "process", "count", "first_seen"])
        for record in sorted(rows, key=lambda r: r.count, reverse=True):
            writer.writerow([record.label, record.text, record.get("process", ""),
                             record.count, record.get("first_seen", "")])

    print(f"{GREEN}Exported {len(rows)} labelled examples to {target}{RESET}")
    return 0


# --------------------------------------------------------------------------- #
# purge
# --------------------------------------------------------------------------- #
def cmd_purge(args: List[str]) -> int:
    """Removes unlabelled windows — a clean start, without losing anything you already labelled."""
    store = ObservationStore(OBSERVATIONS_PATH)
    pending = len(store.pending())

    if not pending:
        print("Nothing pending to purge.")
        return 0

    if "--yes" not in args:
        answer = input(f"Delete {pending} unlabelled observations? "
                       f"(labels are kept) [y/N] ").strip().lower()
        if not answer.startswith("y"):
            print("Cancelled.")
            return 0

    removed = store.purge_unlabelled()
    store.save()
    print(f"{GREEN}Removed {removed} unlabelled observations.{RESET}")
    return 0


# --------------------------------------------------------------------------- #
# Sending each command to the right function
# --------------------------------------------------------------------------- #
COMMANDS = {
    "record": cmd_record,
    "label": cmd_label,
    "rebuild": cmd_rebuild,
    "stats": cmd_stats,
    "eval": cmd_eval,
    "test": cmd_test,
    "import": cmd_import,
    "export": cmd_export,
    "purge": cmd_purge,
}


def usage() -> None:
    print(__doc__)
    print(f"{BOLD}Data files{RESET}")
    print(f"  model:        {MODEL_PATH}")
    print(f"  observations: {OBSERVATIONS_PATH}")


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help", "help"):
        usage()
        return 0

    command = argv[0].lower()
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"{RED}Unknown command: {command}{RESET}\n")
        usage()
        return 1

    return handler(argv[1:])


if __name__ == "__main__":
    sys.exit(main())