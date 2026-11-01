from collections.abc import Callable

from lurch.choices import Choices, choose_definition, choose_sentence, definition_options, key_of, sentence_options
from lurch.entries import POS_NAMES, Entry, Sense

ACCEPT_ALL = "a"
INSTRUCTIONS = (
    "Some meanings have several good options. Type a number to choose one, press Enter to keep the recommended one (*),\n"
    f"or type {ACCEPT_ALL} to accept the recommended choice for everything that is left."
)


def has_options(sense: Sense) -> bool:
    return len(definition_options(sense)) > 1 or len(sentence_options(sense)) > 1


def pending(entries: list[Entry], choices: Choices) -> list[tuple[Entry, Sense]]:
    return [
        (entry, sense)
        for entry in entries
        for sense in entry.senses
        if has_options(sense) and not choices.get(key_of(sense), {}).get("reviewed")
    ]


def ask(title: str, options: list[tuple[str, str]], read: Callable[[str], str]) -> int | str | None:
    print(f"\n{title}")
    for number, (text, source) in enumerate(options, 1):
        print(f"  {number}{'*' if number == 1 else ' '} {text}  [{source or 'dictionary'}]")
    while True:
        answer = read(f"Pick 1-{len(options)}, Enter keeps *, {ACCEPT_ALL} accepts all: ").strip().lower()
        if not answer:
            return None
        if answer == ACCEPT_ALL:
            return ACCEPT_ALL
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return int(answer) - 1


def review_sense(sense: Sense, choices: Choices, read: Callable[[str], str]) -> bool:
    picked: dict[str, str | bool] = {"reviewed": True}
    for kind, options, choose in (
        ("definition", definition_options(sense), choose_definition),
        ("sentence", sentence_options(sense), choose_sentence),
    ):
        if len(options) < 2:
            continue
        answer = ask(f"{kind.capitalize()}:", [(option.text, option.source) for option in options], read)
        if answer == ACCEPT_ALL:
            return False
        if answer is not None:
            choose(sense, options[answer].text)
            picked[kind] = options[answer].text
    choices[key_of(sense)] = picked
    return True


def review(entries: list[Entry], choices: Choices, read: Callable[[str], str] = input) -> None:
    todo = pending(entries, choices)
    if not todo:
        return
    print(f"\n{INSTRUCTIONS}")
    for number, (entry, sense) in enumerate(todo, 1):
        cue = f" · {sense.cue}" if len(entry.senses) > 1 and sense.cue else ""
        print(f"\n=== {sense.headword} ({POS_NAMES[sense.pos]}{cue})  [{number}/{len(todo)}]")
        if not review_sense(sense, choices, read):
            for _, rest in todo[number - 1 :]:
                choices.setdefault(key_of(rest), {"reviewed": True})
            return
