import argparse
import sys
from dataclasses import replace
from pathlib import Path

from lurch.config import Settings
from lurch.hub import prepare


def built_entries(settings: Settings) -> tuple[list, list]:
    from lurch.entries import load_entries
    from lurch.words import read_words

    listed = read_words(settings.words_file)
    entries = load_entries(settings.entries_file) if settings.entries_file.exists() else []
    built = {entry.word for entry in entries}
    for word in listed:
        if word not in built:
            print(f"'{word}' has not been built yet; run `uv run lurch build`.", file=sys.stderr)
    return entries, [entry for entry in entries if entry.word in listed]


def run_senses(settings: Settings) -> None:
    from lurch.entries import save_entries
    from lurch.llm import connect
    from lurch.senses import build_entries
    from lurch.words import read_words

    _, writer = connect(settings)
    entries = build_entries(read_words(settings.words_file), settings, writer)
    save_entries(settings.entries_file, entries)
    for entry in entries:
        for line in entry.log:
            print(f"{entry.word}: {line}", file=sys.stderr)


def run_sentences(settings: Settings) -> None:
    from lurch.choices import apply_choices, load_choices
    from lurch.entries import save_entries
    from lurch.llm import connect
    from lurch.sentences import attach_sentences, download

    arbiter, writer = connect(settings)
    entries, listed = built_entries(settings)
    attach_sentences(listed, download(settings.cache_dir), arbiter, writer)
    apply_choices(listed, load_choices(settings.choices_file))
    save_entries(settings.entries_file, entries)
    for entry in listed:
        for line in entry.log:
            print(f"{entry.word}: {line}", file=sys.stderr)
        for sense in entry.senses:
            if not sense.sentences:
                print(f"{sense.headword} ({sense.cue or sense.pos}): no example sentence", file=sys.stderr)


def run_audio(settings: Settings) -> None:
    from lurch.audio import Speaker, add_audio
    from lurch.entries import save_entries

    entries, listed = built_entries(settings)
    add_audio(listed, Speaker(settings.voices, settings.audio_dir))
    save_entries(settings.entries_file, entries)


def run_deck(settings: Settings) -> None:
    from lurch.deck import build_deck

    _, listed = built_entries(settings)
    if not any(entry.senses for entry in listed):
        raise SystemExit("There are no cards to build for the words in your word list; run `uv run lurch build` first.")
    print(build_deck(listed, settings))


def run_review(settings: Settings) -> None:
    from lurch.choices import load_choices, save_choices
    from lurch.entries import save_entries
    from lurch.review import pending, review

    entries, listed = built_entries(settings)
    choices = load_choices(settings.choices_file)
    todo = pending(listed, choices)
    if not todo:
        return
    if not settings.ask or not sys.stdin.isatty():
        print(f"{len(todo)} meaning(s) have several options; using the recommended ones.", file=sys.stderr)
        return
    review(listed, choices)
    save_choices(settings.choices_file, choices)
    save_entries(settings.entries_file, entries)


STEPS = {"senses": run_senses, "sentences": run_sentences, "audio": run_audio, "deck": run_deck}
BUILD = ("senses", "sentences", "review", "audio", "deck")
ACTIONS = {**STEPS, "review": run_review}


def main() -> None:
    parser = argparse.ArgumentParser(prog="lurch", description="Build an Anki vocabulary deck from a list of words.")
    parser.add_argument("command", choices=[*STEPS, "build"], help="a single step, or build to run them all (build asks you to choose between good options)")
    parser.add_argument("--words", type=Path, help="word list, one word per line (default: LURCH_WORDS or words.txt)")
    parser.add_argument("--recommended", action="store_true", help="do not ask which definition or sentence you prefer; use the recommended ones")
    args = parser.parse_args()
    settings = Settings.load()
    if args.words:
        settings = replace(settings, words_file=args.words)
    if args.recommended:
        settings = replace(settings, ask=False)
    names = list(BUILD) if args.command == "build" else [args.command]
    prepare(names)
    for name in names:
        ACTIONS[name](settings)
