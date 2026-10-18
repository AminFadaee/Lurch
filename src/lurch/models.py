from functools import cache

import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer


@cache
def encoder() -> SentenceTransformer:
    return SentenceTransformer("BAAI/bge-base-en-v1.5")


@cache
def reranker() -> CrossEncoder:
    return CrossEncoder("BAAI/bge-reranker-large")


def embed(texts: list[str]) -> np.ndarray:
    return encoder().encode(texts, normalize_embeddings=True)


def closest(reference: str, candidates: list, text) -> tuple[object, float]:
    vectors = embed([reference] + [text(candidate) for candidate in candidates])
    similarities = vectors[1:] @ vectors[0]
    best = int(similarities.argmax())
    return candidates[best], float(similarities[best])
