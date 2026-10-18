import hashlib
from functools import cache
from pathlib import Path

import numpy as np
import soundfile
from kokoro import KPipeline

from lurch.entries import Entry

SAMPLE_RATE = 24000
REPO_ID = "hexgrad/Kokoro-82M"


@cache
def pipeline(language: str) -> KPipeline:
    return KPipeline(lang_code=language, repo_id=REPO_ID)


def digest(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def pick_voice(text: str, voices: tuple[str, ...]) -> str:
    return voices[int(digest(text), 16) % len(voices)]


class Speaker:
    def __init__(self, voices: tuple[str, ...], directory: Path):
        self.voices = voices
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)

    def say(self, text: str) -> str:
        voice = pick_voice(text, self.voices)
        name = f"en-{digest(voice + text)[:16]}.mp3"
        path = self.directory / name
        if not path.exists():
            audio = np.concatenate([chunk for _, _, chunk in pipeline(voice[0])(text, voice=voice)])
            soundfile.write(path, audio, SAMPLE_RATE, format="MP3")
        return name


def add_audio(entries: list[Entry], speaker: Speaker) -> None:
    for entry in entries:
        for sense in entry.senses:
            sense.word_audio = speaker.say(sense.headword)
            sense.sentence_audio = speaker.say(sense.sentences[0].text) if sense.sentences else ""
