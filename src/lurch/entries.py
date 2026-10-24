import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


POS_NAMES = {"n": "noun", "v": "verb", "a": "adjective", "r": "adverb"}


@dataclass
class Candidate:
    text: str
    source: str


@dataclass
class Sentence:
    id: str
    text: str
    source: str = ""


@dataclass
class Sense:
    headword: str
    key: str
    pos: str
    definition: str
    definition_source: str
    cue: str
    synonyms: list[str]
    related: list[str]
    antonyms: list[str]
    definitions: list[Candidate] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    examples: list[Sentence] = field(default_factory=list)
    sentences: list[Sentence] = field(default_factory=list)
    word_audio: str = ""
    sentence_audio: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Sense":
        sentences = {name: [Sentence(**sentence) for sentence in data[name]] for name in ("examples", "sentences")}
        return cls(**{**data, **sentences, "definitions": [Candidate(**candidate) for candidate in data["definitions"]]})


@dataclass
class Entry:
    word: str
    headwords: list[str]
    forms: list[str]
    senses: list[Sense]
    log: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> "Entry":
        return cls(**{**data, "senses": [Sense.from_dict(sense) for sense in data["senses"]]})


def save_entries(path: Path, entries: list[Entry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(entry) for entry in entries], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_entries(path: Path) -> list[Entry]:
    return [Entry.from_dict(entry) for entry in json.loads(path.read_text(encoding="utf-8"))]
