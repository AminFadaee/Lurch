from lurch.llm import Ollama

DEFINITIONS = """English word: "{word}" ({pos}).
Reference descriptions of one meaning (they may be hard to read): {reference}
Write {count} different plain-English definitions of exactly this meaning for a learner. Each is at most 15 words, in simple common words, and must not contain the word or any word built from it.
Reply with JSON only: {{"definitions": ["...", "..."]}}"""

SENTENCES = """English word: "{word}" ({pos}). Meaning: {definition}
Write {count} different natural example sentences of 8 to 16 words that use "{word}" as a {pos} in exactly this meaning, each in a clear everyday situation whose context shows what the word means. A sentence must not define the word, must not put it in quotes and must not be about language or words.
Reply with JSON only: {{"sentences": ["...", "..."]}}"""

TEMPERATURE = 0.7


class Writer:
    def __init__(self, llm: Ollama):
        self.llm = llm

    def texts(self, prompt: str, key: str, seed: int) -> list[str]:
        items = self.llm.json(prompt, temperature=TEMPERATURE, seed=seed).get(key, [])
        return [item.strip() for item in items if isinstance(item, str) and item.strip()] if isinstance(items, list) else []

    def definitions(self, word: str, pos: str, reference: list[str], count: int = 3, seed: int = 1) -> list[str]:
        return self.texts(DEFINITIONS.format(word=word, pos=pos, reference=" | ".join(reference), count=count), "definitions", seed)

    def sentences(self, word: str, pos: str, definition: str, count: int = 4, seed: int = 1) -> list[str]:
        return self.texts(SENTENCES.format(word=word, pos=pos, definition=definition, count=count), "sentences", seed)
