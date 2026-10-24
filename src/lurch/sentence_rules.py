import re

import numpy as np
from wordfreq import zipf_frequency

MIN_WORDS, MAX_WORDS, TARGET_WORDS = 6, 22, 12
MIN_CLEAN = 0.6
RARE_ZIPF = 3.5
MAX_RARE_PENALISED = 3
ABOUT_LANGUAGE = re.compile(
    r"\b(translate|translation|spell|spelled|spelling|pronounce|word|words|synonym|dictionary|definition|defined|vocabulary)\b",
    re.I,
)
DEFINING = re.compile(r"\b(means|refers to|is defined as|stands for|is a term|is known as|is when|is the term)\b", re.I)


def forms_pattern(words: list[str]) -> str:
    return "|".join(rf"{re.escape(word)}(?:s|es|ly|ies)?" for word in words)


def word_pattern(words: list[str]) -> re.Pattern:
    return re.compile(rf"\b(?:{forms_pattern(words)})\b", re.I)


def acceptable(text: str, words: list[str]) -> bool:
    forms = forms_pattern(words)
    quoted = re.search(rf"[\"“‘'«]\s*(?:{forms})\s*[\"”’'»]", text, re.I)
    defining = re.search(rf"^(?:the\s+)?(?:{forms})\s+(?:is|are|was|means|refers)\b", text, re.I)
    return not (quoted or defining or ABOUT_LANGUAGE.search(text) or DEFINING.search(text))


def features(text: str, words: list[str]) -> tuple[float, float, float, int]:
    tokens = re.findall(r"[A-Za-z']+", text)
    target = word_pattern(words)
    others = [token for token in tokens if not target.fullmatch(token)]
    frequencies = [zipf_frequency(token.lower(), "en") for token in others]
    readability = float(np.clip((np.mean(frequencies) - 3.5) / 2.0, 0, 1)) if frequencies else 0.0
    length = float(np.clip(min((len(tokens) - 5) / 4, (28 - len(tokens)) / 10, 1), 0, 1))
    proper = sum(token[0].isupper() for token in tokens[1:] if token != "I") / max(len(tokens), 1)
    clean = float(np.clip(1 - 2.5 * proper - 0.5 * bool(re.search(r"[\"“”]", text)) - 0.5 * bool(re.search(r"\d", text)), 0, 1))
    return readability, length, clean, sum(frequency < RARE_ZIPF for frequency in frequencies)


def usable(text: str, words: list[str]) -> bool:
    return MIN_WORDS <= len(text.split()) <= MAX_WORDS and acceptable(text, words) and features(text, words)[2] >= MIN_CLEAN


def rule_score(text: str, words: list[str]) -> float:
    readability, length, clean, rare = features(text, words)
    return 0.2 * readability + 0.15 * length + 0.15 * clean - 0.15 * min(rare, MAX_RARE_PENALISED)
