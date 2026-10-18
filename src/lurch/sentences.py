import bz2
import re
import urllib.request
from pathlib import Path

import numpy as np

from lurch.entries import Entry, Sense, Sentence
from lurch.models import embed, reranker

TATOEBA_URL = "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences_detailed.tsv.bz2"
MIN_WORDS, MAX_WORDS, TARGET_WORDS = 6, 22, 12
MAX_DEFINITION_SIMILARITY = 0.8
MIN_SCORE, MIN_MARGIN = 0.5, 0.2
PER_SENSE = 3
ABOUT_LANGUAGE = re.compile(
    r"\b(translate|translation|spell|spelled|spelling|pronounce|word|words|synonym|dictionary|definition|defined|vocabulary)\b",
    re.I,
)

Pool = list[tuple[str, str]]


def download(cache_dir: Path) -> Path:
    path = cache_dir / "eng_sentences_detailed.tsv.bz2"
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(TATOEBA_URL, path)
    return path


def forms_pattern(words: list[str]) -> str:
    return "|".join(rf"{re.escape(word)}(?:s|es|ly|ies)?" for word in words)


def word_pattern(words: list[str]) -> re.Pattern:
    return re.compile(rf"\b(?:{forms_pattern(words)})\b", re.I)


def acceptable(text: str, words: list[str]) -> bool:
    forms = forms_pattern(words)
    quoted = re.search(rf"[\"“‘'«]\s*(?:{forms})\s*[\"”’'»]", text, re.I)
    defining = re.search(rf"^(?:the\s+)?(?:{forms})\s+(?:is|are|was|means|refers)\b", text, re.I)
    return not (quoted or defining or ABOUT_LANGUAGE.search(text))


def read_sentences(path: Path):
    with bz2.open(path, "rt", encoding="utf-8") as lines:
        for line in lines:
            sentence_id, _, text, *_ = line.split("\t")
            if MIN_WORDS <= len(text.split()) <= MAX_WORDS:
                yield sentence_id, text


def collect(entries: list[Entry], path: Path) -> dict[str, Pool]:
    patterns = {entry.word: word_pattern(entry.headwords) for entry in entries if entry.senses}
    pools: dict[str, Pool] = {word: [] for word in patterns}
    by_word = {entry.word: entry for entry in entries}
    for sentence_id, text in read_sentences(path):
        for word, pattern in patterns.items():
            if pattern.search(text) and acceptable(text, by_word[word].headwords):
                pools[word].append((sentence_id, text))
    return pools


def rank_single(sense: Sense, pool: Pool) -> list[Sentence]:
    headword = word_pattern([sense.headword])
    vectors = embed([sense.definition] + [text for _, text in pool])
    similarities = vectors[1:] @ vectors[0]
    ordered = sorted(
        zip(pool, similarities),
        key=lambda item: (not headword.search(item[0][1]), abs(len(item[0][1].split()) - TARGET_WORDS)),
    )
    return [Sentence(sentence_id, text) for (sentence_id, text), similarity in ordered if similarity < MAX_DEFINITION_SIMILARITY][:PER_SENSE]


def rank_multiple(entry: Entry, pool: Pool) -> None:
    pairs = [(text, f"{sense.headword}: {sense.definition}") for _, text in pool for sense in entry.senses]
    scores = np.array(reranker().predict(pairs, batch_size=32)).reshape(len(pool), len(entry.senses))
    for column, sense in enumerate(entry.senses):
        matches = []
        for row, (sentence_id, text) in enumerate(pool):
            order = np.argsort(-scores[row])
            score, margin = float(scores[row][column]), float(scores[row][column] - scores[row][order[1]])
            if order[0] == column and score >= MIN_SCORE and margin >= MIN_MARGIN:
                matches.append(Sentence(sentence_id, text, round(score, 3), round(margin, 3)))
        sense.sentences = sorted(matches, key=lambda sentence: -sentence.score)[:PER_SENSE]


def attach_sentences(entries: list[Entry], path: Path) -> None:
    pools = collect(entries, path)
    for entry in entries:
        pool = pools.get(entry.word)
        if not pool:
            continue
        if len(entry.senses) == 1:
            entry.senses[0].sentences = rank_single(entry.senses[0], pool)
        else:
            rank_multiple(entry, pool)
