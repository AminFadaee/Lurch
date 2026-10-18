from pathlib import Path


def read_words(path: Path) -> list[str]:
    lines = (line.split("#", 1)[0].strip().lower() for line in path.read_text(encoding="utf-8").splitlines())
    return list(dict.fromkeys(line for line in lines if line))
