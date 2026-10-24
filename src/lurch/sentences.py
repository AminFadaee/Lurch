import bz2
import urllib.request
from pathlib import Path

import numpy as np

from lurch.appropriate import inappropriate
from lurch.entries import POS_NAMES, Entry, Sense, Sentence
from lurch.fit import confident_assignment, fit_scores
from lurch.judge import Judge
from lurch.sentence_rules import MAX_WORDS, MIN_WORDS, rule_score, usable, word_pattern
from lurch.writer import Writer

TATOEBA_URL = "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences_detailed.tsv.bz2"
MAX_DEFINITION_SIMILARITY = 0.8
PER_SENSE = 3
SCREENED = 4
GENERATED = "generated"
WRITER_ATTEMPTS = (1, 2)
FIT_WEIGHT = 0.35
DICTIONARY_BONUS = 0.15
UNKNOWN_FIT = 0.5


def download(cache_dir: Path) -> Path:
    path = cache_dir / "eng_sentences_detailed.tsv.bz2"
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(TATOEBA_URL, path)
    return path


def read_sentences(path: Path):
    with bz2.open(path, "rt", encoding="utf-8") as lines:
        for line in lines:
            sentence_id, _, text, *_ = line.split("\t")
            if MIN_WORDS <= len(text.split()) <= MAX_WORDS:
                yield sentence_id, text


def collect(entries: list[Entry], path: Path) -> dict[str, list[Sentence]]:
    patterns = {entry.word: word_pattern(entry.headwords) for entry in entries if entry.senses}
    pools: dict[str, list[Sentence]] = {word: [] for word in patterns}
    by_word = {entry.word: entry for entry in entries}
    for sentence_id, text in read_sentences(path):
        for word, pattern in patterns.items():
            if pattern.search(text) and usable(text, by_word[word].headwords):
                pools[word].append(Sentence(sentence_id, text, "tatoeba"))
    return pools


def sigmoid(value: float) -> float:
    return 1 / (1 + np.exp(-value / 2))


def rank_candidates(entry: Entry, pool: list[Sentence]) -> list[list[tuple[float, Sentence]]]:
    words = entry.headwords
    definitions = [sense.definition for sense in entry.senses]
    ranked: list[list[tuple[float, Sentence]]] = [[] for _ in entry.senses]
    pattern = word_pattern(words)
    for column, sense in enumerate(entry.senses):
        for example in sense.examples:
            if pattern.search(example.text) and usable(example.text, words):
                score = FIT_WEIGHT * UNKNOWN_FIT + DICTIONARY_BONUS + rule_score(example.text, words)
                ranked[column].append((score, example))
    if pool:
        combined, cosine = fit_scores(entry.senses[0].headword, [sentence.text for sentence in pool], definitions)
        for row, column in enumerate(confident_assignment(combined)):
            if column is not None and cosine[row][column] < MAX_DEFINITION_SIMILARITY:
                score = FIT_WEIGHT * sigmoid(float(combined[row][column])) + rule_score(pool[row].text, words)
                ranked[column].append((score, pool[row]))
    seen: set[str] = set()
    for column in ranked:
        column.sort(key=lambda item: -item[0])
        column[:] = [item for item in column if item[1].text.lower() not in seen and not seen.add(item[1].text.lower())]
    return ranked


def screen(candidates: list[Sentence]) -> list[Sentence]:
    screened = []
    for sentence in candidates:
        if not inappropriate(sentence.text):
            screened.append(sentence)
        if len(screened) == SCREENED:
            break
    return screened


def accepted(sense: Sense, candidates: list[Sentence], judge: Judge | None) -> list[Sentence]:
    if not candidates:
        return []
    bad = judge.bad_sentences(sense.headword, POS_NAMES[sense.pos], sense.definition, [c.text for c in candidates]) if judge else set()
    return [sentence for index, sentence in enumerate(candidates) if index not in bad]


def generate(entry: Entry, sense: Sense, judge: Judge, writer: Writer) -> list[Sentence]:
    pattern = word_pattern(entry.headwords)
    for seed in WRITER_ATTEMPTS:
        written = [text for text in writer.sentences(sense.headword, POS_NAMES[sense.pos], sense.definition, seed=seed)]
        candidates = [Sentence("", text, GENERATED) for text in written if pattern.search(text) and usable(text, entry.headwords)]
        candidates = sorted(candidates, key=lambda sentence: -rule_score(sentence.text, entry.headwords))
        survivors = accepted(sense, screen(candidates), judge)
        if survivors:
            return survivors[:PER_SENSE]
    return []


def attach_sentences(entries: list[Entry], path: Path, judge: Judge | None, writer: Writer | None) -> None:
    pools = collect(entries, path)
    for entry in entries:
        if not entry.senses:
            continue
        ranked = rank_candidates(entry, pools.get(entry.word, []))
        for sense, candidates in zip(entry.senses, ranked):
            survivors = accepted(sense, screen([sentence for _, sentence in candidates]), judge)[:PER_SENSE]
            if not survivors and writer and judge:
                survivors = generate(entry, sense, judge, writer)
            sense.sentences = survivors
        evidenced = [sense for sense in entry.senses if sense.sentences]
        if len(entry.senses) > 1 and evidenced:
            entry.log += [f"dropped meaning without an acceptable sentence: {sense.cue or sense.pos}: {sense.definition}" for sense in entry.senses if not sense.sentences]
            entry.senses = evidenced
