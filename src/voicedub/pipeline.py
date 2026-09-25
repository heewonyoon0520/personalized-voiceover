"""Exercise catalog + the end-to-end dub step."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from . import video
from .elevenlabs import ElevenLabsClient
from .narrator import Narrator
from .profile import VoiceBucket
from .voices import VoiceChoice, VoiceSelector

# Run commands from the repo root, or point VOICEDUB_ROOT at it.
ROOT = Path(os.environ.get("VOICEDUB_ROOT", Path.cwd()))
CACHE_DIR = ROOT / ".cache"
DEFAULT_MODEL = "eleven_multilingual_v2"
# Faster than this gets hard to follow, especially for older patients.
MAX_FIT_SPEED = 1.1


@dataclass(frozen=True)
class Exercise:
    id: str
    title: dict[str, str]
    description: dict[str, str]
    video: Path | None

    def text_for(self, language: str) -> str:
        if language not in self.description:
            raise KeyError(
                f"exercise '{self.id}' has no '{language}' description "
                f"(available: {', '.join(sorted(self.description))})"
            )
        return self.description[language]


def load_exercises(path: Path = ROOT / "data" / "exercises.json") -> dict[str, Exercise]:
    raw = json.loads(path.read_text())
    return {
        e["id"]: Exercise(
            id=e["id"],
            title=e.get("title", {}),
            description=e["description"],
            video=(path.parent.parent / e["video"]) if e.get("video") else None,
        )
        for e in raw["exercises"]
    }


def build_services(offline: bool = False) -> tuple[VoiceSelector, Narrator]:
    """Wire up the selector and narrator from env. `offline` uses only
    the voice map and caches, which is handy for tests and demos."""
    load_dotenv(ROOT / ".env")
    client = None if offline else ElevenLabsClient(os.environ.get("ELEVENLABS_API_KEY", ""))
    selector = VoiceSelector(client, ROOT / "config" / "voice_map.json", CACHE_DIR / "voice_cache.json")
    narrator = Narrator(client, CACHE_DIR / "audio", os.environ.get("ELEVENLABS_MODEL_ID") or DEFAULT_MODEL)
    return selector, narrator


@dataclass
class DubResult:
    bucket: VoiceBucket
    voice: VoiceChoice
    narration: Path
    speed: float
    video_duration: float | None
    narration_duration: float
    output: Path | None
    extended_by: float  # seconds of frozen last frame added


def dub(
    exercise: Exercise,
    bucket: VoiceBucket,
    *,
    selector: VoiceSelector,
    narrator: Narrator,
    out: Path | None,
    video_path: Path | None = None,
    voice: VoiceChoice | None = None,
    fit_to_video: bool = True,
    opts: video.MixOptions = video.MixOptions(),
) -> DubResult:
    """Narrate `exercise` for `bucket`. With no video, only the audio is made.
    Pass `voice` to skip selection (e.g. a baseline voice for comparison)."""
    text = exercise.text_for(bucket.language)
    voice = voice or selector.select(bucket)
    narration = narrator.synthesize(text, voice.voice_id, bucket.language)
    narration_duration = video.probe_duration(narration)

    video_path = video_path or exercise.video
    if video_path is None or out is None:
        return DubResult(bucket, voice, narration, 1.0, None, narration_duration, None, 0.0)
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    video_duration = video.probe_duration(video_path)
    speed = 1.0
    available = video_duration - opts.lead_in - opts.tail
    if fit_to_video and available > 0 and narration_duration > available:
        # Speed up a little rather than freeze the video; anything left over
        # is covered by holding the last frame.
        speed = min(MAX_FIT_SPEED, narration_duration / available)
        narration = narrator.synthesize(text, voice.voice_id, bucket.language, speed=speed)
        narration_duration = video.probe_duration(narration)

    cmd = video.build_mux_command(
        video_path, narration, out,
        video_duration=video_duration,
        narration_duration=narration_duration,
        video_has_audio=video.has_audio(video_path),
        opts=opts,
    )
    video.mux(cmd)
    total = video.output_duration(video_duration, narration_duration, opts)
    return DubResult(bucket, voice, narration, speed, video_duration, narration_duration, out,
                     max(0.0, total - video_duration))
