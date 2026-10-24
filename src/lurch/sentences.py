import bz2
import urllib.request
from pathlib import Path

import numpy as np

from collections import Counter

from lurch.appropriate import inappropriate
from lurch.arbiter import Arbiter, clear_winner
from lurch.circularity import is_circular
from lurch.definitions import MAX_WORDS as MAX_DEFINITION_WORDS
from lurch.entries import POS_NAMES, Entry, Sense, Sentence
from lurch.fit import confident_assignment, fit_scores
from lurch.sentence_rules import MAX_WORDS, MIN_WORDS, rule_score, usable, word_pattern
from lurch.writer import Writer

TATOEBA_URL = "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences_detailed.tsv.bz2"
MAX_DEFINITION_SIMILARITY = 0.8
PER_SENSE = 3
STATIC_SENTENCES = 6
GENERATED = "generated"
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


def screen(candidates: list[Sentence], limit: int) -> list[Sentence]:
    screened = []
    for sentence in candidates:
        if not inappropriate(sentence.text):
            screened.append(sentence)
        if len(screened) == limit:
            break
    return screened


def written_for(entry: Entry, sense: Sense, writer: Writer) -> tuple[str, list[Sentence]]:
    reference = sense.definitions[0].text if sense.definitions else " | ".join(sense.references)
    definition, examples = writer.entry(sense.headword, POS_NAMES[sense.pos], sense.cue, reference)
    if not definition or len(definition.split()) > MAX_DEFINITION_WORDS or is_circular(sense.headword, definition):
        definition = ""
    pattern = word_pattern(entry.headwords)
    usable_examples = [text for text in examples if pattern.search(text) and usable(text, entry.headwords)]
    return definition, [Sentence("", text, GENERATED) for text in usable_examples if not inappropriate(text)]


def on_other_meaning(entry: Entry, generated: list[list[Sentence]]) -> list[list[Sentence]]:
    owners = [(column, sentence) for column, sentences in enumerate(generated) for sentence in sentences]
    if len(entry.senses) < 2 or not owners:
        return generated
    combined, _ = fit_scores(entry.senses[0].headword, [sentence.text for _, sentence in owners], [sense.definition for sense in entry.senses])
    kept: list[list[Sentence]] = [[] for _ in generated]
    for (column, sentence), assigned in zip(owners, confident_assignment(combined)):
        if assigned in (None, column):
            kept[column].append(sentence)
    return kept


def order_sentences(static: list[Sentence], generated: list[Sentence], votes: Counter) -> list[Sentence]:
    clear = clear_winner(votes, [sentence.text for sentence in static])
    pool = generated + static
    if clear:
        main = next(sentence for sentence in static if sentence.text == clear)
    elif generated:
        main = max(generated, key=lambda sentence: (votes[sentence.text], -generated.index(sentence)))
    elif static:
        main = max(static, key=lambda sentence: (votes[sentence.text], -static.index(sentence)))
    else:
        return []
    rest = sorted((s for s in pool if s is not main and (votes[s.text] > 0 or s.source == GENERATED)), key=lambda s: -votes[s.text])
    return [main] + rest[: PER_SENSE - 1]


def choose_definition(sense: Sense, written: str, votes: Counter) -> tuple[str, str]:
    clear = clear_winner(votes, [candidate.text for candidate in sense.definitions])
    if clear:
        return clear, next(candidate.source for candidate in sense.definitions if candidate.text == clear)
    if written:
        return written, GENERATED
    return sense.definition, sense.definition_source


def attach_sentences(entries: list[Entry], path: Path, arbiter: Arbiter | None, writer: Writer | None) -> None:
    pools = collect(entries, path)
    for entry in entries:
        drafts = [(sense, *(written_for(entry, sense, writer) if writer else ("", []))) for sense in entry.senses]
        drafts = [(sense, definition, examples) for sense, definition, examples in drafts if sense.definition or definition]
        for sense, definition, _ in drafts:
            if not sense.definition:
                sense.definition, sense.definition_source = definition, GENERATED
        entry.senses = [sense for sense, _, _ in drafts]
        if not drafts:
            continue
        ranked = rank_candidates(entry, pools.get(entry.word, []))
        generated = on_other_meaning(entry, [examples for _, _, examples in drafts])
        for column, (sense, written_definition, _) in enumerate(drafts):
            static = screen([sentence for _, sentence in ranked[column]], STATIC_SENTENCES)
            definitions = [candidate.text for candidate in sense.definitions] + ([written_definition] if written_definition else [])
            sentences = [sentence.text for sentence in static + generated[column]]
            if arbiter and (len(definitions) > 1 or len(sentences) > 1):
                definition_votes, sentence_votes = arbiter.vote(sense.headword, POS_NAMES[sense.pos], sense.cue, definitions, sentences)
            else:
                definition_votes = sentence_votes = Counter()
            sense.definition, sense.definition_source = choose_definition(sense, written_definition, definition_votes)
            sense.sentences = order_sentences(static, generated[column], sentence_votes)
            main = sense.sentences[0].source if sense.sentences else "nothing"
            entry.log.append(f"{sense.headword} ({sense.cue or sense.pos}): definition from {sense.definition_source}, example from {main}")
        evidenced = [sense for sense in entry.senses if sense.sentences]
        if len(entry.senses) > 1 and evidenced:
            entry.log += [f"dropped meaning without an acceptable sentence: {sense.cue or sense.pos}: {sense.definition}" for sense in entry.senses if not sense.sentences]
            entry.senses = evidenced
