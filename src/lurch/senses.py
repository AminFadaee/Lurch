from dataclasses import dataclass

from wn import Synset

from lurch.circularity import classify
from lurch.entries import Entry, Sense
from lurch.models import embed
from lurch.related import broader_terms, dedupe_spellings, related_terms
from lurch.wordnet import english

PARTS_OF_SPEECH = "nvasr"
SENSES_PER_WORD = 3
MIN_SYNONYMS = 2
MAX_SYNONYMS = 5


@dataclass(frozen=True)
class Candidate:
    headword: str
    synset: Synset
    rank: int


def resolve(word: str) -> tuple[list[Candidate], list[str]]:
    candidates, log = [], []
    for rank, synset in enumerate(english().synsets(word)):
        if word not in synset.lemmas() or synset.pos not in PARTS_OF_SPEECH:
            continue
        resolution = classify(word, synset)
        if resolution.kind == "drop":
            log.append(f"dropped (circular): [{synset.pos}] {synset.definition()}")
            continue
        if resolution.kind == "hop":
            log.append(f"hop: {word} -> {resolution.headword}: {resolution.synset.definition()}")
        candidates.append(Candidate(resolution.headword, resolution.synset, rank))
    return candidates, log


def pick_varied(candidates: list[Candidate]) -> list[Candidate]:
    unique = sorted({candidate.synset.id: candidate for candidate in candidates}.values(), key=lambda c: c.rank)
    if len(unique) <= SENSES_PER_WORD:
        return unique
    vectors = embed([candidate.synset.definition() for candidate in unique])
    chosen = [0]
    while len(chosen) < SENSES_PER_WORD:
        rest = [i for i in range(len(unique)) if i not in chosen]
        chosen.append(max(rest, key=lambda i: min(1 - vectors[i] @ vectors[j] for j in chosen)))
    return [unique[i] for i in chosen]


def describe(candidate: Candidate, use_neighbours: bool) -> Sense:
    synset, headword = candidate.synset, candidate.headword
    synonyms = dedupe_spellings(
        [lemma for lemma in synset.lemmas() if lemma.lower() != headword and lemma.islower() and "-" not in lemma and " " not in lemma]
    )[:MAX_SYNONYMS]
    related = related_terms(headword, synset, set(synonyms), use_neighbours) if len(synonyms) < MIN_SYNONYMS else []
    antonyms = sorted({a.word().lemma() for sense in synset.senses() for a in sense.get_related("antonym")})
    return Sense(
        headword=headword,
        synset=synset.id,
        pos=synset.pos,
        definition=synset.definition(),
        rank=candidate.rank,
        cue=(synonyms or broader_terms(synset) or [""])[0],
        synonyms=synonyms,
        related=related,
        antonyms=antonyms,
    )


def build_entry(word: str) -> Entry:
    candidates, log = resolve(word)
    picked = pick_varied(candidates)
    senses = [describe(candidate, use_neighbours=len(picked) == 1) for candidate in picked]
    if not senses:
        log.append("no usable sense found")
    headwords = {sense.headword for sense in senses}
    return Entry(word, sorted(headwords | {word}), sorted({word} - headwords), senses, log)


def build_entries(words: list[str]) -> list[Entry]:
    return [build_entry(word) for word in words]
