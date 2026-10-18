from functools import cache

import wn
from wn.morphy import Morphy

LEXICON = "oewn:2024"


@cache
def english() -> wn.Wordnet:
    if not wn.lexicons(lexicon=LEXICON):
        wn.download(LEXICON)
    return wn.Wordnet(LEXICON)


@cache
def morphy() -> Morphy:
    return Morphy(english())
