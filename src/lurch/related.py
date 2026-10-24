from difflib import SequenceMatcher
from functools import cache

import gensim.downloader
from wn import Synset
from wordfreq import zipf_frequency

from lurch.models import embed
from lurch.morphology import content_terms, overlaps
from lurch.wordnet import english

MIN_ZIPF = 2.5
MIN_SIMILARITY = 0.70
NEIGHBOURS = 80
SPELLING_VARIANT_RATIO = 0.88
BROADER_TERMS = 2


@cache
def vectors():
    return gensim.downloader.load("glove-wiki-gigaword-100")


def frequency(word: str) -> float:
    return zipf_frequency(word, "en")


def merged_pos(pos: str) -> str:
    return "a" if pos == "s" else pos


def dedupe_spellings(words: list[str]) -> list[str]:
    kept: list[str] = []
    for word in sorted(words, key=lambda w: -frequency(w)):
        if all(SequenceMatcher(None, word, other).ratio() < SPELLING_VARIANT_RATIO for other in kept):
            kept.append(word)
    return kept


def broader_terms(synset: Synset | None) -> list[str]:
    if synset is None:
        return []
    terms = {lemma for parent in synset.hypernyms() for lemma in parent.lemmas() if lemma.islower() and "-" not in lemma}
    return sorted(terms, key=lambda term: -frequency(term))[:BROADER_TERMS]


def neighbour_terms(headword: str, pos: str, definition: str) -> list[str]:
    if headword not in vectors():
        return []
    blocked = set(content_terms(definition))
    definitions: dict[str, list[str]] = {}
    for word, _ in vectors().most_similar(headword, topn=NEIGHBOURS):
        if not word.isalpha() or frequency(word) < MIN_ZIPF or overlaps(headword, word) or word in blocked:
            continue
        senses = [s for s in english().synsets(word) if word in s.lemmas() and merged_pos(s.pos) == merged_pos(pos)]
        if senses:
            definitions[word] = [s.definition() for s in senses]
    pairs = [(word, text) for word, texts in definitions.items() for text in texts]
    if not pairs:
        return []
    embedded = embed([definition] + [text for _, text in pairs])
    best: dict[str, float] = {}
    for (word, _), similarity in zip(pairs, embedded[1:] @ embedded[0]):
        best[word] = max(best.get(word, 0.0), float(similarity))
    return [word for word, score in sorted(best.items(), key=lambda item: -item[1]) if score >= MIN_SIMILARITY]


def related_terms(
    headword: str, pos: str, definition: str, synset: Synset | None, exclude: set[str], use_neighbours: bool, limit: int = 4
) -> list[str]:
    terms = broader_terms(synset) + (neighbour_terms(headword, pos, definition) if use_neighbours else [])
    unique = [term for term in dict.fromkeys(terms) if term not in exclude and term != headword]
    return dedupe_spellings(unique)[:limit]
