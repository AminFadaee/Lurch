import html
import re
from importlib.resources import files
from pathlib import Path

import genanki

from lurch.audio import digest
from lurch.config import Settings
from lurch.entries import Entry, Sense

MODEL_ID = 1607392319
POS_NAMES = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}
FIELDS = [
    "Word", "Pos", "Cue", "Definition", "Synonyms", "Related", "Antonyms", "Forms", "OtherMeanings",
    "Sentence", "SentenceCloze", "WordAudio", "SentenceAudio",
]
CARDS = ("recognition", "recall", "listening")
INCLUDE = re.compile(r"<!--include:(\w+)-->")
MIN_STEM = 4


def read_template(name: str) -> str:
    text = files("lurch").joinpath("templates", name).read_text(encoding="utf-8")
    return INCLUDE.sub(lambda match: read_template(f"{match.group(1)}.html"), text)


def build_model() -> genanki.Model:
    templates = [
        {"name": card.capitalize(), "qfmt": read_template(f"{card}_front.html"), "afmt": read_template(f"{card}_back.html")}
        for card in CARDS
    ]
    css = files("lurch").joinpath("templates", "style.css").read_text(encoding="utf-8")
    return genanki.Model(MODEL_ID, "Lurch Vocabulary", fields=[{"name": field} for field in FIELDS], templates=templates, css=css)


def stems(words: list[str]) -> str:
    return "|".join(re.escape(word[: max(MIN_STEM, len(word) - 3)]) for word in words)


def highlight(sentence: str, words: list[str]) -> str:
    return re.sub(rf"\b((?:{stems(words)})\w*)", r"<b>\1</b>", html.escape(sentence), count=1, flags=re.I)


def blank(sentence: str, words: list[str]) -> str:
    return re.sub(rf"\b(?:{stems(words)})\w*", '<span class="blank">_____</span>', html.escape(sentence), count=1, flags=re.I)


def chips(items: list[str]) -> str:
    return "".join(f"<span>{html.escape(item)}</span>" for item in items)


def sound(name: str) -> str:
    return f"[sound:{name}]" if name else ""


def note_fields(entry: Entry, sense: Sense) -> list[str]:
    sentence = sense.sentences[0].text if sense.sentences else ""
    others = "".join(
        f"<div><b>{html.escape(other.cue)}</b>: {html.escape(other.definition)}</div>" for other in entry.senses if other is not sense
    )
    values = {
        "Word": sense.headword,
        "Pos": POS_NAMES[sense.pos],
        "Cue": sense.cue if len(entry.senses) > 1 else "",
        "Definition": html.escape(sense.definition[:1].upper() + sense.definition[1:]),
        "Synonyms": chips(sense.synonyms[:4]),
        "Related": chips(sense.related),
        "Antonyms": chips(sense.antonyms[:3]),
        "Forms": ", ".join(entry.forms),
        "OtherMeanings": others,
        "Sentence": highlight(sentence, entry.headwords) if sentence else "",
        "SentenceCloze": blank(sentence, entry.headwords) if sentence else "",
        "WordAudio": sound(sense.word_audio),
        "SentenceAudio": sound(sense.sentence_audio),
    }
    return [values[field] for field in FIELDS]


def build_deck(entries: list[Entry], settings: Settings) -> Path:
    model = build_model()
    deck = genanki.Deck(int(digest(settings.deck_name)[:8], 16), settings.deck_name)
    media: set[str] = set()
    for entry in entries:
        for sense in entry.senses:
            deck.add_note(
                genanki.Note(
                    model=model,
                    fields=note_fields(entry, sense),
                    guid=genanki.guid_for(sense.headword, sense.synset),
                    tags=[f"pos::{POS_NAMES[sense.pos]}"],
                )
            )
            media |= {sense.word_audio, sense.sentence_audio} - {""}
    package = genanki.Package(deck)
    package.media_files = [str(settings.audio_dir / name) for name in sorted(media)]
    settings.build_dir.mkdir(parents=True, exist_ok=True)
    path = settings.build_dir / f"{re.sub(r'[^a-z0-9]+', '_', settings.deck_name.lower()).strip('_')}.apkg"
    package.write_to_file(path)
    return path
