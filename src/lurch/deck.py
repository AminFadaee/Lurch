import html
import re
from importlib.resources import files
from pathlib import Path

import genanki

from lurch.audio import digest
from lurch.config import Settings
from lurch.entries import POS_NAMES, Entry, Sense

MODEL_ID = 1607392321
FIELDS = ["Word", "Subtitle", "Definition", "Sentence", "Details", "WordAudio", "SentenceAudio"]
CARDS = ("meaning", "listening")
MIN_STEM = 4


def read_template(name: str) -> str:
    return files("lurch").joinpath("templates", name).read_text(encoding="utf-8")


def build_model() -> genanki.Model:
    templates = [
        {"name": card.capitalize(), "qfmt": read_template(f"{card}_front.html"), "afmt": read_template(f"{card}_back.html")}
        for card in CARDS
    ]
    return genanki.Model(MODEL_ID, "Lurch Vocabulary", fields=[{"name": field} for field in FIELDS], templates=templates, css=read_template("style.css"))


def stems(words: list[str]) -> str:
    return "|".join(re.escape(word[: max(MIN_STEM, len(word) - 3)]) for word in words)


def highlight(sentence: str, words: list[str]) -> str:
    return re.sub(rf"\b((?:{stems(words)})\w*)", r"<b>\1</b>", html.escape(sentence), count=1, flags=re.I)


def chip(label: str, items: list[str]) -> str:
    return f'<span class="chip"><i>{label}</i>{html.escape(", ".join(items))}</span>' if items else ""


def sound(name: str) -> str:
    return f"[sound:{name}]" if name else ""


def details(entry: Entry, sense: Sense) -> str:
    chips = [chip("Synonyms", sense.synonyms[:4]), chip("Related", sense.related), chip("Opposite", sense.antonyms[:3]), chip("Also", entry.forms)]
    facts = f'<div class="facts">{"".join(chips)}</div>' if any(chips) else ""
    alternates = "".join(f'<div class="alt">{highlight(sentence.text, entry.headwords)}</div>' for sentence in sense.sentences[1:])
    more = f'<details class="more"><summary>More examples</summary>{alternates}</details>' if alternates else ""
    others = "".join(f"<div><b>{html.escape(other.cue or POS_NAMES[other.pos])}</b>: {html.escape(other.definition)}</div>" for other in entry.senses if other is not sense)
    return facts + more + (f'<div class="others">{others}</div>' if others else "")


def note_fields(entry: Entry, sense: Sense) -> list[str]:
    cue = f" · {sense.cue}" if len(entry.senses) > 1 and sense.cue else ""
    values = {
        "Word": sense.headword,
        "Subtitle": POS_NAMES[sense.pos] + cue,
        "Definition": html.escape(sense.definition[:1].upper() + sense.definition[1:]),
        "Sentence": highlight(sense.sentences[0].text, entry.headwords) if sense.sentences else "",
        "Details": details(entry, sense),
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
                    guid=genanki.guid_for(sense.headword, sense.key),
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
