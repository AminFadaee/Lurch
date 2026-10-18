import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Sentence:
    id: str
    text: str
    score: float | None = None
    margin: float | None = None


@dataclass
class Sense:
    headword: str
    synset: str
    pos: str
    definition: str
    rank: int
    cue: str
    synonyms: list[str]
    related: list[str]
    antonyms: list[str]
    sentences: list[Sentence] = field(default_factory=list)
    word_audio: str = ""
    sentence_audio: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Sense":
        return cls(**{**data, "sentences": [Sentence(**sentence) for sentence in data["sentences"]]})


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
