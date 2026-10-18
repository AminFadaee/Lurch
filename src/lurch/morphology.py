import re

from nltk.stem.snowball import SnowballStemmer

from lurch.wordnet import morphy

STOP_WORDS = frozenset(
    "that this with from been were their there which when what into than then them they also such some only used "
    "using other more most very make made being does".split()
)
SUFFIXES = (
    "er", "or", "ist", "ly", "ally", "ness", "ion", "ation", "ment", "al", "ial", "ic", "ical", "ive", "ous", "ful",
    "less", "able", "ible", "ing", "ed", "en", "ize", "ise", "ify", "ity", "ism", "hood", "ship", "dom", "ance",
    "ence", "ant", "ent", "ary",
)
MIN_ROOT_LENGTH = 4

stem = SnowballStemmer("english").stem


def roots(word: str) -> set[str]:
    found, frontier = {word}, {word}
    for _ in range(2):
        step = set()
        for form in frontier:
            for suffix in SUFFIXES + ("s", "es"):
                base = form[: -len(suffix)]
                if form.endswith(suffix) and len(base) >= MIN_ROOT_LENGTH:
                    step |= {
                        base,
                        base + "e",
                        base + "y",
                        base[:-1] + "y" if base.endswith("i") else base,
                        base[:-1] if base[-1] == base[-2] else base,
                    }
        found |= step
        frontier = step
    return {root for root in found if len(root) >= MIN_ROOT_LENGTH}


def overlaps(a: str, b: str) -> bool:
    return stem(a) == stem(b) or bool(roots(a) & roots(b))


def content_terms(definition: str) -> list[str]:
    return [t for t in re.findall(r"[a-z]+", definition.lower()) if len(t) >= MIN_ROOT_LENGTH and t not in STOP_WORDS]


def circular_terms(word: str, definition: str) -> list[str]:
    return [term for term in content_terms(definition) if overlaps(word, term)]


def lemmas_of(token: str) -> set[str]:
    forms = (morphy()(token, pos) for pos in "nvar")
    return {lemma for found in forms for group in found.values() for lemma in group} | {token}
