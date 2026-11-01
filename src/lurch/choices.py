import json
from pathlib import Path

from lurch.entries import PER_SENSE, Candidate, Entry, Sense, Sentence

Choices = dict[str, dict[str, str]]


def key_of(sense: Sense) -> str:
    return f"{sense.headword}|{sense.key}"


def load_choices(path: Path) -> Choices:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_choices(path: Path, choices: Choices) -> None:
    path.write_text(json.dumps(choices, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def definition_options(sense: Sense) -> list[Candidate]:
    options = {sense.definition: Candidate(sense.definition, sense.definition_source)}
    for candidate in sense.definitions:
        options.setdefault(candidate.text, candidate)
    return list(options.values())


def sentence_options(sense: Sense) -> list[Sentence]:
    options: dict[str, Sentence] = {}
    for sentence in sense.sentences + sense.candidates:
        options.setdefault(sentence.text, sentence)
    return list(options.values())


def choose_definition(sense: Sense, text: str) -> None:
    chosen = next((candidate for candidate in definition_options(sense) if candidate.text == text), None)
    if chosen:
        sense.definition, sense.definition_source = chosen.text, chosen.source


def choose_sentence(sense: Sense, text: str) -> None:
    chosen = next((sentence for sentence in sentence_options(sense) if sentence.text == text), None)
    if chosen:
        sense.sentences = [chosen] + [sentence for sentence in sense.sentences if sentence.text != text][: PER_SENSE - 1]


def apply_choices(entries: list[Entry], choices: Choices) -> None:
    for entry in entries:
        for sense in entry.senses:
            picked = choices.get(key_of(sense), {})
            if "definition" in picked:
                choose_definition(sense, picked["definition"])
            if "sentence" in picked:
                choose_sentence(sense, picked["sentence"])
