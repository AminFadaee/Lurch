from collections.abc import Callable

from lurch.choices import Choices, choose_definition, choose_sentence, definition_options, key_of, sentence_options
from lurch.entries import POS_NAMES, Entry, Sense

STOP = "q"


def ask(title: str, options: list[tuple[str, str]], read: Callable[[str], str]) -> int | str | None:
    print(f"\n{title}")
    for number, (text, source) in enumerate(options, 1):
        print(f"  {number}{'*' if number == 1 else ' '} {text}  [{source or 'dictionary'}]")
    while True:
        answer = read(f"Pick 1-{len(options)}, Enter keeps the current one, {STOP} stops: ").strip().lower()
        if not answer:
            return None
        if answer == STOP:
            return STOP
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return int(answer) - 1


def review_sense(sense: Sense, choices: Choices, read: Callable[[str], str]) -> bool:
    picked = choices.setdefault(key_of(sense), {})
    for kind, options, choose in (
        ("definition", definition_options(sense), choose_definition),
        ("sentence", sentence_options(sense), choose_sentence),
    ):
        if len(options) < 2:
            continue
        answer = ask(f"{kind.capitalize()}:", [(option.text, option.source) for option in options], read)
        if answer == STOP:
            return False
        if answer is not None:
            choose(sense, options[answer].text)
            picked[kind] = options[answer].text
    if not picked:
        del choices[key_of(sense)]
    return True


def review(entries: list[Entry], choices: Choices, read: Callable[[str], str] = input) -> None:
    senses = [(entry, sense) for entry in entries for sense in entry.senses if len(definition_options(sense)) > 1 or len(sentence_options(sense)) > 1]
    if not senses:
        print("Nothing to choose: every meaning has a single option. Run `uv run lurch sentences` first if you built before this feature existed.")
    for number, (entry, sense) in enumerate(senses, 1):
        cue = f" · {sense.cue}" if len(entry.senses) > 1 and sense.cue else ""
        print(f"\n=== {sense.headword} ({POS_NAMES[sense.pos]}{cue})  [{number}/{len(senses)}]")
        if not review_sense(sense, choices, read):
            break
