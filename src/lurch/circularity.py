from dataclasses import dataclass

from wn import Synset

from lurch.models import closest
from lurch.morphology import circular_terms, content_terms, lemmas_of, overlaps
from lurch.wordnet import english

LINKS = ("pertainym", "derivation")
MIN_SIMILARITY = 0.65
MIN_OTHER_TERMS = 4


@dataclass(frozen=True)
class Resolution:
    kind: str
    synset: Synset | None = None
    headword: str | None = None


def is_circular(word: str, definition: str) -> bool:
    terms = circular_terms(word, definition)
    return bool(terms) and len([t for t in content_terms(definition) if t not in terms]) < MIN_OTHER_TERMS


def own_sense(word: str, synset: Synset):
    return next(sense for sense in synset.senses() if sense.word().lemma() == word)


def linked_base(word: str, synset: Synset, bases: set[str]) -> Resolution | None:
    targets = [
        target
        for relation in LINKS
        for target in own_sense(word, synset).get_related(relation)
        if target.word().lemma().lower() in bases
        and target.word().lemma().lower() != word
        and not circular_terms(target.word().lemma().lower(), target.synset().definition())
    ]
    if not targets:
        return None
    target, _ = closest(synset.definition(), targets, lambda t: t.synset().definition())
    return Resolution("hop", target.synset(), target.word().lemma())


def suffix_base(word: str, synset: Synset, bases: set[str]) -> Resolution | None:
    candidates = [
        candidate
        for base in bases
        if len(base) < len(word) and overlaps(word, base)
        for candidate in english().synsets(base)
        if base in candidate.lemmas() and not circular_terms(base, candidate.definition())
    ]
    if not candidates:
        return None
    best, similarity = closest(synset.definition(), candidates, lambda c: c.definition())
    if similarity < MIN_SIMILARITY:
        return None
    return Resolution("hop", best, next(base for base in bases if base in best.lemmas()))


def classify(word: str, synset: Synset) -> Resolution:
    definition = synset.definition()
    terms = circular_terms(word, definition)
    if not terms or len([t for t in content_terms(definition) if t not in terms]) >= MIN_OTHER_TERMS:
        return Resolution("clean", synset, word)
    bases = set().union(*(lemmas_of(term) for term in terms))
    own_terms = {term for term in terms if word in lemmas_of(term)}
    if bases <= {word} | own_terms:
        return Resolution("drop")
    return linked_base(word, synset, bases) or suffix_base(word, synset, bases) or Resolution("drop")
