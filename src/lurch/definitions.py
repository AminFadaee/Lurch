import re

import numpy as np
from wordfreq import zipf_frequency

from lurch.circularity import is_circular
from lurch.inventory import Meaning
from lurch.models import embed
from lurch.morphology import content_terms, overlaps
from lurch.wiktionary import Gloss

CANDIDATES = 5
MAX_WORDS = 18
UNPLAIN = re.compile(r"\b(especially|usually|often|informal|archaic|obsolete)\b", re.I)
ANAPHORA = re.compile(r"\b(such an?|this|these|the former|the latter)\b", re.I)
OLD_FASHIONED = {"obsolete", "archaic", "rare", "dated"}
ANCHOR_BONUS = 0.10


def quality(text: str, tags: list[str]) -> float:
    words = re.findall(r"[A-Za-z']+", text)
    if not words:
        return 0.0
    readability = float(np.clip((np.mean([zipf_frequency(word.lower(), "en") for word in words]) - 3.5) / 2.0, 0, 1))
    brevity = float(np.clip((25 - len(words)) / 15, 0, 1))
    messy = 2 * bool(ANAPHORA.search(text)) + len(re.findall(r"[;()]", text)) + bool(UNPLAIN.search(text)) + 2 * bool(OLD_FASHIONED & set(tags))
    clean = float(np.clip(1 - 0.35 * messy, 0, 1))
    return 0.4 * readability + 0.3 * brevity + 0.3 * clean


def rank_definitions(headword: str, meaning: Meaning) -> list[Gloss]:
    unique = list(reversed({gloss.text.lower(): gloss for gloss in reversed(meaning.glosses)}.values()))
    anchors = {id(gloss) for gloss in meaning.anchors}
    vectors = embed([gloss.text for gloss in unique])
    similarity = vectors @ vectors.T
    central = (similarity.sum(axis=1) - 1) / max(len(unique) - 1, 1) if len(unique) > 1 else np.ones(1)
    scored = [
        (0.5 * quality(gloss.text, gloss.tags) + 0.5 * float(central[i]) + ANCHOR_BONUS * (id(gloss) in anchors), gloss)
        for i, gloss in enumerate(unique)
        if not is_circular(headword, gloss.text) and not ANAPHORA.search(gloss.text)
    ]
    ranked = [gloss for _, gloss in sorted(scored, key=lambda item: -item[0])]
    return [gloss for gloss in ranked if len(gloss.text.split()) <= MAX_WORDS] or ranked


def key_word(headword: str, definitions: list[str]) -> str:
    shortest = min(definitions, key=lambda text: len(text.split()))
    terms = [term for term in dict.fromkeys(content_terms(shortest)) if not overlaps(headword, term)]
    if not terms:
        return ""
    vectors = embed(definitions + terms)
    centre = vectors[: len(definitions)].mean(axis=0)
    return terms[int(np.argmax(vectors[len(definitions) :] @ centre))]
