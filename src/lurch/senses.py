import hashlib

from lurch.circularity import classify
from lurch.config import Settings
from lurch.definitions import CANDIDATES, MAX_WORDS, key_word, rank_definitions
from lurch.entries import Candidate, Entry, Sense, Sentence
from lurch.inventory import Meaning, build_meanings
from lurch.models import embed
from lurch.morphology import overlaps
from lurch.related import broader_terms, dedupe_spellings, frequency, related_terms
from lurch.wordnet import english
from lurch.writer import Writer

PARTS_OF_SPEECH = "nvasr"
SENSES_PER_WORD = 3
MIN_SYNONYMS = 2
MAX_SYNONYMS = 5
MIN_SYNONYM_ZIPF = 3.0
MIN_SYNONYM_SIMILARITY = 0.58


def resolve(word: str) -> tuple[list[str], list[str]]:
    headwords, log, clean = [], [], False
    for synset in english().synsets(word):
        if word not in synset.lemmas() or synset.pos not in PARTS_OF_SPEECH:
            continue
        resolution = classify(word, synset)
        if resolution.kind == "drop":
            log.append(f"dropped (circular): [{synset.pos}] {synset.definition()}")
            continue
        clean = clean or resolution.kind == "clean"
        if resolution.kind == "hop":
            log.append(f"hop: {word} -> {resolution.headword}: {resolution.synset.definition()}")
        headwords.append(resolution.headword)
    return ([word] if clean else list(dict.fromkeys(headwords))) or [word], log


def single_words(headword: str, lemmas: list[str]) -> list[str]:
    return [lemma for lemma in dict.fromkeys(lemmas) if lemma.islower() and "-" not in lemma and " " not in lemma and not overlaps(headword, lemma)]


def synonyms_of(headword: str, meaning: Meaning, definition: str) -> list[str]:
    curated = single_words(headword, [lemma for gloss in meaning.glosses if gloss.source == "wordnet" for lemma in gloss.synonyms])
    listed = [word for word in single_words(headword, [lemma for gloss in meaning.glosses if gloss.source == "wiktionary" for lemma in gloss.synonyms]) if frequency(word) >= MIN_SYNONYM_ZIPF]
    if listed:
        vectors = embed([definition] + listed)
        listed = [word for word, similarity in sorted(zip(listed, vectors[1:] @ vectors[0]), key=lambda item: -item[1]) if similarity >= MIN_SYNONYM_SIMILARITY]
    return dedupe_spellings(list(dict.fromkeys(curated + listed)))[:MAX_SYNONYMS]


def describe(headword: str, meaning: Meaning, use_neighbours: bool, writer: Writer | None, log: list[str]) -> Sense | None:
    synset = next((gloss.synset for gloss in meaning.glosses if gloss.synset is not None), None)
    everything = rank_definitions(headword, meaning)
    concise = [gloss for gloss in everything if len(gloss.text.split()) <= MAX_WORDS]
    ranked = concise or ([] if writer else everything)
    references = [gloss.text for gloss in meaning.glosses][:2]
    if not ranked and not writer:
        log.append(f"no usable definition for {headword} ({references[0]})")
        return None
    synonyms = synonyms_of(headword, meaning, (ranked or meaning.glosses)[0].text)
    cue = (synonyms or broader_terms(synset) or [key_word(headword, [gloss.text for gloss in meaning.anchors])])[0]
    definitions = [Candidate(gloss.text, gloss.source) for gloss in ranked[:CANDIDATES]]
    definition = definitions[0] if definitions else Candidate("", "")
    related = related_terms(headword, meaning.pos, definition.text or references[0], synset, set(synonyms), use_neighbours) if len(synonyms) < MIN_SYNONYMS else []
    antonyms = sorted({a.word().lemma() for sense in synset.senses() for a in sense.get_related("antonym")}) if synset else []
    examples = list(dict.fromkeys((gloss.source, example) for gloss in meaning.glosses for example in gloss.examples))
    key = synset.id if synset else hashlib.md5(meaning.glosses[0].text.encode()).hexdigest()[:12]
    return Sense(
        headword=headword,
        key=key,
        pos=meaning.pos,
        definition=definition.text,
        definition_source=definition.source,
        cue=cue,
        synonyms=synonyms,
        related=related,
        antonyms=antonyms,
        definitions=definitions,
        references=references,
        examples=[Sentence("", example, origin) for origin, example in examples],
    )


def build_entry(word: str, settings: Settings, writer: Writer | None) -> Entry:
    headwords, log = resolve(word)
    meanings = [(headword, meaning) for headword in headwords for meaning in build_meanings(headword, settings.cache_dir)]
    meanings = sorted(meanings, key=lambda item: -item[1].support)[:SENSES_PER_WORD]
    senses = [sense for headword, meaning in meanings if (sense := describe(headword, meaning, len(meanings) == 1, writer, log))]
    if not senses:
        log.append("no usable meaning found")
    found = {sense.headword for sense in senses}
    return Entry(word, sorted(found | {word}), sorted({word} - found), senses, log)


def build_entries(words: list[str], settings: Settings, writer: Writer | None) -> list[Entry]:
    return [build_entry(word, settings, writer) for word in words]
