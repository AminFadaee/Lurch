import random
import re
from collections import Counter

from lurch.llm import Ollama

SHUFFLES = 5
CLEAR_VOTES = 4

PROMPT = """You are choosing the best material for an English vocabulary flashcard for learners.
Word: "{word}" ({pos}), the meaning labelled "{cue}".

Definitions:
{definitions}

Example sentences:
{sentences}

Pick the best definition: accurate for this meaning, plain, short, in simple common words, and not circular (it must not reuse the word or its root).
Pick the best example sentence: natural, everyday, clear context that shows this meaning, uses the word as a {pos}, no rare words, no names, not about language, not a definition.
Reply with JSON only: {{"best_definition": number, "best_example": number}}"""


def numbered(items: list[str]) -> str:
    return "\n".join(f"{number}) {text}" for number, text in enumerate(items, 1))


class Arbiter:
    def __init__(self, llm: Ollama):
        self.llm = llm

    def vote(self, word: str, pos: str, cue: str, definitions: list[str], sentences: list[str]) -> tuple[Counter, Counter]:
        definition_votes: Counter = Counter()
        sentence_votes: Counter = Counter()
        for seed in range(1, SHUFFLES + 1):
            order = random.Random(seed)
            shown_definitions, shown_sentences = definitions[:], sentences[:]
            order.shuffle(shown_definitions)
            order.shuffle(shown_sentences)
            prompt = PROMPT.format(word=word, pos=pos, cue=cue, definitions=numbered(shown_definitions), sentences=numbered(shown_sentences))
            answer = self.llm.json(prompt, seed=seed, max_tokens=60)
            for votes, shown, key in ((definition_votes, shown_definitions, "best_definition"), (sentence_votes, shown_sentences, "best_example")):
                number = int(re.sub(r"\D", "", str(answer.get(key, ""))) or 0)
                if 1 <= number <= len(shown):
                    votes[shown[number - 1]] += 1
        return definition_votes, sentence_votes


def clear_winner(votes: Counter, static: list[str]) -> str | None:
    if not votes:
        return None
    text, count = votes.most_common(1)[0]
    return text if text in static and count >= CLEAR_VOTES else None
