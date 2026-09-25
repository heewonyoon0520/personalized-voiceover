"""Pick a voice for a bucket.

Order of precedence:
  1. config/voice_map.json  - voices the team listened to and approved
  2. .cache/voice_cache.json - voices this tool picked earlier (stable per bucket)
  3. ElevenLabs Voice Library search, relaxing filters step by step
  4. per-gender default voice
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from .elevenlabs import ElevenLabsError
from .profile import VoiceBucket

# ElevenLabs premade voices, used only when nothing else matches.
DEFAULT_VOICES = {
    "female": "EXAVITQu4vr4xnSDxMaL",  # Sarah
    "male": "JBFqnCBsd6RMkjVDRZzb",  # George
}


class VoiceLibrary(Protocol):
    def search_shared_voices(self, *, language=None, gender=None, age=None) -> list[dict]: ...
    def add_shared_voice(self, public_owner_id: str, voice_id: str, new_name: str) -> str: ...


@dataclass
class VoiceChoice:
    voice_id: str
    name: str
    source: str  # voice_map | cache | library:<level> | default
    preview_url: str | None = None


def _speaks(voice: dict, language: str) -> bool:
    if voice.get("language") == language:
        return True
    return any(v.get("language") == language for v in voice.get("verified_languages") or [])


def _search_plan(bucket: VoiceBucket) -> list[tuple[str, dict]]:
    return [
        ("exact", {"language": bucket.language, "gender": bucket.gender, "age": bucket.age_band}),
        ("any_age", {"language": bucket.language, "gender": bucket.gender}),
        # Multilingual models can speak the target language with a voice from
        # another language; accent quality varies, so this is a last resort.
        ("any_language", {"gender": bucket.gender, "age": bucket.age_band}),
    ]


class VoiceSelector:
    def __init__(self, library: VoiceLibrary | None, voice_map_path: Path, cache_path: Path):
        self._library = library
        self._cache_path = cache_path
        voice_map = json.loads(voice_map_path.read_text()) if voice_map_path.exists() else {}
        self._voice_map: dict[str, str] = {k: v for k, v in voice_map.get("buckets", {}).items() if v}
        self._defaults = {**DEFAULT_VOICES, **{k: v for k, v in voice_map.get("defaults", {}).items() if v}}
        self._cache: dict[str, dict] = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    def select(self, bucket: VoiceBucket) -> VoiceChoice:
        if bucket.key in self._voice_map:
            return VoiceChoice(self._voice_map[bucket.key], bucket.key, "voice_map")
        if bucket.key in self._cache:
            return VoiceChoice(**{**self._cache[bucket.key], "source": "cache"})
        if self._library is not None:
            try:
                choice = self._search_library(bucket)
            except ElevenLabsError as e:
                # e.g. an API key without the voices_read permission
                print(f"warning: voice library search failed, using default voice: {e}", file=sys.stderr)
                choice = None
            if choice:
                self._cache[bucket.key] = asdict(choice)
                self._cache_path.parent.mkdir(parents=True, exist_ok=True)
                self._cache_path.write_text(json.dumps(self._cache, ensure_ascii=False, indent=2))
                return choice
        return self.default(bucket.gender)

    def default(self, gender: str) -> VoiceChoice:
        return VoiceChoice(self._defaults[gender], f"default-{gender}", "default")

    def _search_library(self, bucket: VoiceBucket) -> VoiceChoice | None:
        for level, filters in _search_plan(bucket):
            voices = self._library.search_shared_voices(**filters)
            # Results are already sorted by popularity; prefer voices verified
            # for the target language, keeping the popularity order otherwise.
            voices.sort(key=lambda v: not _speaks(v, bucket.language))
            if not voices:
                continue
            best = voices[0]
            try:
                voice_id = self._library.add_shared_voice(
                    best["public_owner_id"], best["voice_id"], f"voicedub {bucket.key}"
                )
            except ElevenLabsError:
                # Already in the library (or adding is not allowed on this
                # plan); the shared voice_id still works for TTS in most cases.
                voice_id = best["voice_id"]
            return VoiceChoice(voice_id, best.get("name", ""), f"library:{level}", best.get("preview_url"))
        return None
