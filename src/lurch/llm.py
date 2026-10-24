import hashlib
import json
import sys
import urllib.error
import urllib.request
from functools import cache
from pathlib import Path

from lurch.config import Settings


class Ollama:
    def __init__(self, url: str, model: str, cache_dir: Path):
        self.url = url.rstrip("/")
        self.model = model
        self.cache_dir = cache_dir / "llm"

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=5) as response:
                names = {model["name"] for model in json.load(response)["models"]}
        except (urllib.error.URLError, OSError, KeyError, ValueError):
            return False
        return self.model in names

    def json(self, prompt: str, temperature: float = 0.0, seed: int = 0, max_tokens: int = 400) -> dict:
        key = hashlib.sha256(f"{self.model}|{temperature}|{seed}|{max_tokens}|{prompt}".encode()).hexdigest()[:24]
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "think": False,
            "options": {"temperature": temperature, "seed": seed, "num_predict": max_tokens},
        }
        request = urllib.request.Request(f"{self.url}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=1800) as response:
                data = json.loads(json.load(response)["message"]["content"])
        except (urllib.error.URLError, OSError, KeyError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data


@cache
def connect(settings: Settings):
    from lurch.judge import Judge
    from lurch.writer import Writer

    def warn(message: str) -> None:
        print(message, file=sys.stderr)

    judge = writer = None
    if settings.judge_model:
        llm = Ollama(settings.ollama_url, settings.judge_model, settings.cache_dir)
        if not llm.available():
            warn(f"Judge model {settings.judge_model} is not available in Ollama; continuing without it")
        elif not Judge(llm).self_check():
            warn(f"Judge model {settings.judge_model} failed its self-check; continuing without it")
        else:
            judge = Judge(llm)
    if settings.writer_model and judge:
        llm = Ollama(settings.ollama_url, settings.writer_model, settings.cache_dir)
        if llm.available():
            writer = Writer(llm)
        else:
            warn(f"Writer model {settings.writer_model} is not available in Ollama; continuing without it")
    elif settings.writer_model:
        warn("A writer model needs a working judge model; continuing without generated text")
    return judge, writer
