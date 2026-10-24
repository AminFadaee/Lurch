from lurch.llm import Ollama

ENTRY = """English word: "{word}" ({pos}), the meaning labelled "{cue}".
Reference description of this meaning (it may be hard to read): {reference}
Write a plain-English definition of exactly this meaning for a learner: at most 15 words, simple common words, in your own words, and it must not contain the word or any word built from it.
Write {count} different natural example sentences of 8 to 16 words that use "{word}" as a {pos} in exactly this meaning, each in a clear everyday situation whose context shows what the word means. An example must not define the word, must not put it in quotes and must not be about language or words.
Reply with JSON only: {{"definition": "...", "examples": ["...", "..."]}}"""


class Writer:
    def __init__(self, llm: Ollama):
        self.llm = llm

    def entry(self, word: str, pos: str, cue: str, reference: str, count: int = 3) -> tuple[str, list[str]]:
        data = self.llm.json(ENTRY.format(word=word, pos=pos, cue=cue, reference=reference, count=count), max_tokens=500)
        definition = data.get("definition", "")
        examples = data.get("examples", [])
        examples = examples if isinstance(examples, list) else []
        return (definition.strip() if isinstance(definition, str) else ""), [item.strip() for item in examples if isinstance(item, str) and item.strip()]
