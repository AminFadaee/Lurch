from functools import cache

from transformers import pipeline

LABELS = ["sexual content", "violence, death or suffering", "hate or insults", "ordinary everyday text"]
REJECT_AT = 0.75


@cache
def classifier():
    return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")


@cache
def inappropriate(text: str) -> bool:
    result = classifier()(text, LABELS)
    return result["labels"][0] != LABELS[-1] and result["scores"][0] >= REJECT_AT
