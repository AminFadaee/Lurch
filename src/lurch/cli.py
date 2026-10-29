import argparse
import sys
from dataclasses import replace
from pathlib import Path

from lurch.config import Settings
from lurch.hub import prepare


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
    from lurch.entries import load_entries, save_entries
    from lurch.llm import connect
    from lurch.sentences import attach_sentences, download

    arbiter, writer = connect(settings)
    entries = load_entries(settings.entries_file)
    attach_sentences(entries, download(settings.cache_dir), arbiter, writer)
    save_entries(settings.entries_file, entries)
    for entry in entries:
        for line in entry.log:
            print(f"{entry.word}: {line}", file=sys.stderr)
        for sense in entry.senses:
            if not sense.sentences:
                print(f"{sense.headword} ({sense.cue or sense.pos}): no example sentence", file=sys.stderr)


def run_audio(settings: Settings) -> None:
    from lurch.audio import Speaker, add_audio
    from lurch.entries import load_entries, save_entries

    entries = load_entries(settings.entries_file)
    add_audio(entries, Speaker(settings.voices, settings.audio_dir))
    save_entries(settings.entries_file, entries)


def run_deck(settings: Settings) -> None:
    from lurch.deck import build_deck
    from lurch.entries import load_entries

    print(build_deck(load_entries(settings.entries_file), settings))


STEPS = {"senses": run_senses, "sentences": run_sentences, "audio": run_audio, "deck": run_deck}


def main() -> None:
    parser = argparse.ArgumentParser(prog="lurch", description="Build an Anki vocabulary deck from a list of words.")
    parser.add_argument("command", choices=[*STEPS, "build"], help="a single step, or build to run them all")
    parser.add_argument("--words", type=Path, help="word list, one word per line (default: LURCH_WORDS or words.txt)")
    args = parser.parse_args()
    settings = Settings.load()
    if args.words:
        settings = replace(settings, words_file=args.words)
    names = list(STEPS) if args.command == "build" else [args.command]
    prepare(names)
    for name in names:
        STEPS[name](settings)
