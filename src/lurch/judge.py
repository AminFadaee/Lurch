from lurch.llm import Ollama

SENTENCES = """You are checking example sentences for an English vocabulary flashcard.
Word: "{word}" ({pos}). Meaning: {definition}

Example sentences:
{items}

List every sentence that is unacceptable: it does not use the word in this exact meaning, is garbled or awkward, is about language or defines the word, is vague, or has rare words or names that make it hard to learn from.
Reply with JSON only: {{"unacceptable": [numbers]}}"""

CHECK_WORD = "bank"
CHECK_DEFINITION = "A place that keeps people's money safe."
CHECK_SENTENCES = [
    "She opened a savings account at the bank near her house.",
    'The word "bank" is hard to spell.',
    "Bank means something that people often talk about.",
    "I read about bank in a book yesterday.",
]
CHECK_EXPECTED_SENTENCES = {2, 3, 4}


class Judge:
    def __init__(self, llm: Ollama):
        self.llm = llm

    def unacceptable(self, prompt: str, count: int) -> set[int]:
        flagged = self.llm.json(prompt, max_tokens=200).get("unacceptable", [])
        flagged = flagged if isinstance(flagged, list) else []
        return {int(item) for item in flagged if str(item).strip().isdigit() and 1 <= int(item) <= count}

    def bad_sentences(self, word: str, pos: str, definition: str, sentences: list[str]) -> set[int]:
        items = "\n".join(f"{number}) {text}" for number, text in enumerate(sentences, 1))
        return {n - 1 for n in self.unacceptable(SENTENCES.format(word=word, pos=pos, definition=definition, items=items), len(sentences))}

    def self_check(self) -> bool:
        flagged = self.bad_sentences(CHECK_WORD, "noun", CHECK_DEFINITION, CHECK_SENTENCES)
        return {number + 1 for number in flagged} == CHECK_EXPECTED_SENTENCES
