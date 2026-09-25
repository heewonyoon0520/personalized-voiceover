"""voicedub CLI.

  voicedub voice     --age 67 --gender female --lang ko
  voicedub dub       --exercise glute_bridge --age 67 --gender female --lang ko
  voicedub prerender --langs ko,en
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

from .pipeline import ROOT, build_services, dub, load_exercises
from .profile import AGE_BAND_NAMES, PATIENT_GENDERS, SUPPORTED_LANGUAGES, VOICE_GENDERS, PatientProfile, VoiceBucket
from .video import MixOptions


def _add_profile_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--age", type=int, required=True)
    p.add_argument("--gender", choices=PATIENT_GENDERS, required=True)
    p.add_argument("--lang", choices=sorted(SUPPORTED_LANGUAGES), required=True, help="app language")
    p.add_argument("--fallback-gender", choices=VOICE_GENDERS, default="female",
                   help="voice gender for patients who chose 'other'")


def _add_mix_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--lead-in", type=float, default=0.5, help="seconds before narration starts")
    p.add_argument("--replace-audio", action="store_true", help="drop the original audio track")
    p.add_argument("--original-volume", type=float, default=0.15)
    p.add_argument("--no-fit", action="store_true", help="never speed up narration to fit the clip")


def _mix_options(args: argparse.Namespace) -> MixOptions:
    return MixOptions(lead_in=args.lead_in, keep_original_audio=not args.replace_audio,
                      original_volume=args.original_volume)


def _print_result(r) -> None:
    print(f"bucket     {r.bucket.key}")
    print(f"voice      {r.voice.name} ({r.voice.voice_id}) via {r.voice.source}")
    print(f"narration  {r.narration}  {r.narration_duration:.1f}s  speed={r.speed:.2f}")
    if r.output:
        note = f"  (+{r.extended_by:.1f}s held last frame)" if r.extended_by > 0 else ""
        print(f"video      {r.output}  source {r.video_duration:.1f}s{note}")


def cmd_voice(args: argparse.Namespace) -> None:
    bucket = PatientProfile(args.age, args.gender, args.lang).bucket(args.fallback_gender)
    selector, _ = build_services(offline=args.offline)
    choice = selector.select(bucket)
    print(f"bucket   {bucket.key}")
    print(f"voice    {choice.name} ({choice.voice_id})")
    print(f"source   {choice.source}")
    if choice.preview_url:
        print(f"preview  {choice.preview_url}")


def cmd_dub(args: argparse.Namespace) -> None:
    exercises = load_exercises()
    if args.exercise not in exercises:
        sys.exit(f"unknown exercise '{args.exercise}'. choose from: {', '.join(exercises)}")
    bucket = PatientProfile(args.age, args.gender, args.lang).bucket(args.fallback_gender)
    selector, narrator = build_services()
    out = args.out or ROOT / "output" / args.exercise / f"{bucket.key.replace(':', '_')}.mp4"
    result = dub(exercises[args.exercise], bucket, selector=selector, narrator=narrator, out=out,
                 video_path=args.video, fit_to_video=not args.no_fit, opts=_mix_options(args))
    _print_result(result)


def cmd_prerender(args: argparse.Namespace) -> None:
    """Render every bucket for every exercise, i.e. what would ship to a CDN."""
    exercises = load_exercises()
    ids = args.exercise or list(exercises)
    selector, narrator = build_services()
    buckets = [VoiceBucket(l, g, a) for l, g, a in itertools.product(
        args.langs.split(","), args.genders.split(","), args.age_bands.split(","))]
    for ex_id, bucket in itertools.product(ids, buckets):
        ex = exercises[ex_id]
        if bucket.language not in ex.description:
            print(f"skip {ex_id} {bucket.key}: no description in that language")
            continue
        out = ROOT / "output" / ex_id / f"{bucket.key.replace(':', '_')}.mp4"
        print(f"== {ex_id} {bucket.key}")
        _print_result(dub(ex, bucket, selector=selector, narrator=narrator, out=out,
                          fit_to_video=not args.no_fit, opts=_mix_options(args)))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="voicedub", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("voice", help="show which voice a patient would get")
    _add_profile_args(p)
    p.add_argument("--offline", action="store_true", help="only use voice_map / cache, no API calls")
    p.set_defaults(func=cmd_voice)

    p = sub.add_parser("dub", help="dub one exercise video for one patient")
    _add_profile_args(p)
    _add_mix_args(p)
    p.add_argument("--exercise", required=True)
    p.add_argument("--video", type=Path, help="override the video in data/exercises.json")
    p.add_argument("--out", type=Path)
    p.set_defaults(func=cmd_dub)

    p = sub.add_parser("prerender", help="render all voice buckets for the exercise catalog")
    _add_mix_args(p)
    p.add_argument("--exercise", action="append", help="limit to these ids (repeatable)")
    p.add_argument("--langs", default="ko,en")
    p.add_argument("--genders", default=",".join(VOICE_GENDERS))
    p.add_argument("--age-bands", default=",".join(AGE_BAND_NAMES))
    p.set_defaults(func=cmd_prerender)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
