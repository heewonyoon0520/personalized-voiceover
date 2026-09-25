"""Text-to-speech with a content-addressed disk cache.

The cache key covers everything that changes the audio, so the same
(text, voice, model, speed) is only ever billed once.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .elevenlabs import ElevenLabsClient

# Fixed seed so re-renders of the same text sound the same.
SEED = 7


class Narrator:
    def __init__(self, client: ElevenLabsClient | None, cache_dir: Path, model_id: str):
        self._client = client
        self._cache_dir = cache_dir
        self.model_id = model_id

    def synthesize(self, text: str, voice_id: str, language: str, speed: float = 1.0) -> Path:
        speed = round(speed, 2)
        key = hashlib.sha256(
            json.dumps(
                {"text": text, "voice": voice_id, "model": self.model_id, "lang": language, "speed": speed, "seed": SEED},
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()[:24]
        path = self._cache_dir / f"{key}.mp3"
        if path.exists():
            return path
        if self._client is None:
            raise RuntimeError("no ElevenLabs client configured and narration is not cached")
        audio = self._client.text_to_speech(
            voice_id, text, model_id=self.model_id, language_code=language, speed=speed, seed=SEED
        )
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio)
        return path
