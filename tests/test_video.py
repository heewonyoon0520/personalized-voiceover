from pathlib import Path

from voicedub.video import MixOptions, build_mux_command


def cmd(video_duration, narration_duration, has_audio=True, **opts):
    return build_mux_command(Path("in.mp4"), Path("n.mp3"), Path("out.mp4"),
                             video_duration=video_duration, narration_duration=narration_duration,
                             video_has_audio=has_audio, opts=MixOptions(**opts))


def test_short_narration_copies_video():
    c = cmd(15.0, 10.0)
    assert c[c.index("-c:v") + 1] == "copy"
    assert c[c.index("-t") + 1] == "15.000"
    assert "amix" in c[c.index("-filter_complex") + 1]


def test_long_narration_holds_last_frame():
    c = cmd(10.0, 12.0)
    graph = c[c.index("-filter_complex") + 1]
    assert "tpad=stop_mode=clone:stop_duration=3.000" in graph
    assert c[c.index("-t") + 1] == "13.000"


def test_replace_audio_skips_original_track():
    c = cmd(15.0, 10.0, keep_original_audio=False)
    assert "[0:a]" not in c[c.index("-filter_complex") + 1]


def test_silent_video_skips_original_track():
    c = cmd(15.0, 10.0, has_audio=False)
    assert "[0:a]" not in c[c.index("-filter_complex") + 1]
