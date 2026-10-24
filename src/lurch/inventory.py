from dataclasses import dataclass
from pathlib import Path

import numpy as np

from lurch.models import embed
from lurch.wiktionary import Gloss, simple_glosses, wiktionary_glosses
from lurch.wordnet import english

ANCHOR_SIMILARITY = 0.68
ATTACH_SIMILARITY = 0.65
WORDNET_POS = {"n": "n", "v": "v", "a": "a", "s": "a", "r": "r"}


@dataclass
class Meaning:
    pos: str
    glosses: list[Gloss]
    order: int

    @property
    def anchors(self) -> list[Gloss]:
        wiktionary = [gloss for gloss in self.glosses if gloss.source == "wiktionary"]
        return wiktionary or [gloss for gloss in self.glosses if gloss.source == "wordnet"]

    @property
    def support(self) -> int:
        return len({gloss.source for gloss in self.glosses})


def wordnet_glosses(headword: str) -> list[Gloss]:
    return [
        Gloss("wordnet", WORDNET_POS[synset.pos], synset.definition(), synset.lemmas(), synset.examples(), [], synset)
        for synset in english().synsets(headword)
        if headword in synset.lemmas() and synset.pos in WORDNET_POS
    ]


def mean_similarity(vectors: dict[int, np.ndarray], group: list[Gloss], gloss: Gloss) -> float:
    return float(np.mean([vectors[id(member)] @ vectors[id(gloss)] for member in group]))


def build_meanings(headword: str, cache_dir: Path) -> list[Meaning]:
    wiktionary = wiktionary_glosses(headword, cache_dir)
    others = simple_glosses(headword, cache_dir)
    wordnet = wordnet_glosses(headword)
    anchors, others = (wiktionary, others + wordnet) if wiktionary else (wordnet, others)
    if not anchors:
        return []
    everything = anchors + others
    vectors = dict(zip(map(id, everything), embed([gloss.text for gloss in everything])))
    groups: list[list[Gloss]] = []
    for gloss in anchors:
        for group in groups:
            if group[0].pos == gloss.pos and mean_similarity(vectors, group, gloss) >= ANCHOR_SIMILARITY:
                group.append(gloss)
                break
        else:
            groups.append([gloss])
    for gloss in others:
        scored = [(mean_similarity(vectors, group, gloss), group) for group in groups if group[0].pos == gloss.pos]
        if scored and max(scored, key=lambda item: item[0])[0] >= ATTACH_SIMILARITY:
            max(scored, key=lambda item: item[0])[1].append(gloss)
    meanings = [Meaning(group[0].pos, group, order) for order, group in enumerate(groups)]
    return sorted(meanings, key=lambda meaning: (-meaning.support, meaning.order))
