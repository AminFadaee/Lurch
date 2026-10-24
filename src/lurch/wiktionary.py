import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

USER_AGENT = "Lurch/0.1 (https://github.com/AminFadaee/Lurch)"
WIKTIONARY_URL = "https://kaikki.org/dictionary/English/meaning/{first}/{prefix}/{word}.jsonl"
SIMPLE_URL = "https://simple.wiktionary.org/w/api.php?action=query&prop=extracts&explaintext=1&redirects=1&format=json&titles={word}"
POS_CODES = {"noun": "n", "verb": "v", "adj": "a", "adjective": "a", "adv": "r", "adverb": "r"}
SKIPPED_GLOSS = re.compile(r"^(alternative|obsolete|archaic|dated|misspelling|plural|present participle|past|eye dialect|nonstandard)", re.I)
DATED_QUOTATION = re.compile(r"^\d{3,4}\b")
LEADING_TAG = re.compile(r"^\([^)]*\)\s*")


@dataclass
class Gloss:
    source: str
    pos: str
    text: str
    synonyms: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    synset: object = None


def fetch(url: str, path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        text = urllib.request.urlopen(request, timeout=40).read().decode("utf-8")
    except urllib.error.HTTPError as error:
        if error.code != 404:
            return ""
        text = ""
    except urllib.error.URLError:
        return ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def usable_example(text: str) -> str:
    line = text.split("\n")[-1].strip()
    return "" if DATED_QUOTATION.match(line) or "[...]" in line else line


def wiktionary_glosses(word: str, cache_dir: Path) -> list[Gloss]:
    url = WIKTIONARY_URL.format(first=word[0], prefix=word[:2], word=urllib.parse.quote(word))
    glosses = []
    for line in fetch(url, cache_dir / "wiktionary" / f"{word}.jsonl").splitlines():
        entry = json.loads(line)
        pos = POS_CODES.get(entry.get("pos", ""))
        if entry.get("word") != word or not pos:
            continue
        for sense in entry.get("senses", []):
            text = (sense.get("glosses") or [""])[-1]
            if not text or SKIPPED_GLOSS.match(text) or "form_of" in sense or "alt_of" in sense:
                continue
            examples = [usable_example(example.get("text", "")) for example in sense.get("examples", [])]
            glosses.append(
                Gloss(
                    "wiktionary",
                    pos,
                    text,
                    [synonym["word"] for synonym in sense.get("synonyms", [])],
                    [example for example in examples if example],
                    sense.get("tags", []),
                )
            )
    return glosses


def plain_definition(text: str, word: str) -> str:
    text = LEADING_TAG.sub("", text)
    text = re.sub(rf"^(?:the |a |an )?{word}(?: of [^,]*?)? (?:is|are) ", "", text, flags=re.I)
    text = re.sub(rf"^If (?:something|someone|a thing|a person) is {word}, (?:it|he|she|they) (?:is|are) ", "", text, flags=re.I)
    return re.sub(r"^It means ", "", text)


def simple_glosses(word: str, cache_dir: Path) -> list[Gloss]:
    url = SIMPLE_URL.format(word=urllib.parse.quote(word))
    pages = json.loads(fetch(url, cache_dir / "simple" / f"{word}.json") or '{"query": {"pages": {}}}')["query"]["pages"]
    extract = next(iter(pages.values()), {}).get("extract", "")
    glosses, pos, current = [], None, None
    for line in (line.strip() for line in extract.splitlines()):
        header = re.match(r"^=+\s*(\w+)\s*=+$", line)
        if header:
            pos, current = POS_CODES.get(header.group(1).lower()), None
        elif not line or not pos or line.startswith(("IPA", "(UK)", "(US)", "Hyphenation")):
            continue
        elif line.startswith("(") or current is None:
            current = Gloss("simple", pos, plain_definition(line, word))
            glosses.append(current)
        else:
            current.examples.append(line)
    return glosses
