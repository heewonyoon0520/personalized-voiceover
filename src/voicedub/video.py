"""ffmpeg helpers: probe durations and lay narration over an exercise video."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise RuntimeError(f"{tool} not found on PATH (macOS: brew install ffmpeg)")
    return path


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [_require("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def has_audio(path: Path) -> bool:
    out = subprocess.run(
        [_require("ffprobe"), "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return bool(out)


@dataclass(frozen=True)
class MixOptions:
    lead_in: float = 0.5  # seconds of video before narration starts
    tail: float = 0.5  # seconds kept after narration ends
    keep_original_audio: bool = True  # keep background music under the voice
    original_volume: float = 0.15


def output_duration(video_duration: float, narration_duration: float, opts: MixOptions) -> float:
    return max(video_duration, opts.lead_in + narration_duration + opts.tail)


def build_mux_command(
    video: Path,
    narration: Path,
    out: Path,
    *,
    video_duration: float,
    narration_duration: float,
    video_has_audio: bool,
    opts: MixOptions = MixOptions(),
) -> list[str]:
    total = output_duration(video_duration, narration_duration, opts)
    extra = total - video_duration
    delay_ms = int(opts.lead_in * 1000)

    filters = [f"[1:a]adelay=delays={delay_ms}:all=1,apad[narr]"]
    if opts.keep_original_audio and video_has_audio:
        filters.append(f"[0:a]volume={opts.original_volume},apad[bg]")
        filters.append("[bg][narr]amix=inputs=2:duration=longest:normalize=0[aout]")
    else:
        filters.append("[narr]anull[aout]")

    if extra > 0.01:
        # Narration is longer than the clip: hold the last frame.
        filters.append(f"[0:v]tpad=stop_mode=clone:stop_duration={extra:.3f}[vout]")
        video_args = ["-map", "[vout]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    else:
        video_args = ["-map", "0:v", "-c:v", "copy"]

    return [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video), "-i", str(narration),
        "-filter_complex", ";".join(filters),
        *video_args,
        "-map", "[aout]", "-c:a", "aac", "-b:a", "160k",
        "-t", f"{total:.3f}",
        "-movflags", "+faststart",
        str(out),
    ]


def mux(cmd: list[str]) -> None:
    _require("ffmpeg")
    Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)
