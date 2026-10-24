from functools import cache

import numpy as np
from sentence_transformers import CrossEncoder

from lurch.models import embed, reranker

STATS = {"reranker": (0.016, 0.087), "cosine": (0.464, 0.086), "entailment": (0.274, 0.395)}
MIN_MARGIN = 2.5


@cache
def entailment_model() -> CrossEncoder:
    return CrossEncoder("cross-encoder/nli-deberta-v3-base")


def standardise(name: str, values: np.ndarray) -> np.ndarray:
    mean, deviation = STATS[name]
    return (values - mean) / deviation


def fit_scores(word: str, texts: list[str], definitions: list[str]) -> tuple[np.ndarray, np.ndarray]:
    shape = (len(texts), len(definitions))
    rerank = np.array(reranker().predict([(text, f"{word}: {d}") for text in texts for d in definitions], batch_size=32)).reshape(shape)
    vectors = embed(texts + definitions)
    cosine = vectors[: len(texts)] @ vectors[len(texts) :].T
    hypotheses = [(text, f'In this sentence, "{word}" means {d[:1].lower() + d[1:]}') for text in texts for d in definitions]
    logits = entailment_model().predict(hypotheses, batch_size=32)
    exponent = np.exp(logits - logits.max(axis=1, keepdims=True))
    entailment = (exponent / exponent.sum(axis=1, keepdims=True))[:, 1].reshape(shape)
    combined = standardise("reranker", rerank) + standardise("cosine", cosine) + standardise("entailment", entailment)
    return combined, cosine


def confident_assignment(combined: np.ndarray) -> list[int | None]:
    assigned: list[int | None] = []
    for row in combined:
        order = np.argsort(-row)
        assigned.append(int(order[0]) if len(row) == 1 or row[order[0]] - row[order[1]] >= MIN_MARGIN else None)
    return assigned
