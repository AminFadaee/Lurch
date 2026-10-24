import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_VOICES = "af_heart,af_bella,af_nicole,af_sarah,am_michael,am_adam,am_eric,am_liam"


@dataclass(frozen=True)
class Settings:
    voices: tuple[str, ...]
    deck_name: str
    words_file: Path
    arbiter_model: str = ""
    writer_model: str = ""
    ollama_url: str = "http://localhost:11434"
    data_dir: Path = Path("data")
    cache_dir: Path = Path(".cache")
    build_dir: Path = Path("build")

    @property
    def entries_file(self) -> Path:
        return self.data_dir / "entries.json"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        voices = os.getenv("LURCH_VOICES", DEFAULT_VOICES).split(",")
        return cls(
            voices=tuple(voice.strip() for voice in voices if voice.strip()),
            deck_name=os.getenv("LURCH_DECK_NAME", "English Vocabulary"),
            words_file=Path(os.getenv("LURCH_WORDS", "words.txt")),
            arbiter_model=os.getenv("LURCH_ARBITER_MODEL", ""),
            writer_model=os.getenv("LURCH_WRITER_MODEL", ""),
            ollama_url=os.getenv("LURCH_OLLAMA_URL", "http://localhost:11434"),
        )
