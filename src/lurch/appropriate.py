from functools import cache

from transformers import pipeline

from lurch.sentence_rules import word_pattern

LABELS = ["sexual content", "violence, death or suffering", "hate or insults", "ordinary everyday text"]
REJECT_AT = 0.75
MASK = "X"


@cache
def classifier():
    return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")


@cache
def inappropriate(text: str, words: tuple[str, ...] = ()) -> bool:
    masked = word_pattern(list(words)).sub(MASK, text) if words else text
    result = classifier()(masked, LABELS)
    return result["labels"][0] != LABELS[-1] and result["scores"][0] >= REJECT_AT
