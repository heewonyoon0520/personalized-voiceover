import json

from voicedub.elevenlabs import ElevenLabsError
from voicedub.profile import VoiceBucket
from voicedub.voices import DEFAULT_VOICES, VoiceSelector

BUCKET = VoiceBucket("ko", "female", "old")


class FakeLibrary:
    def __init__(self, results, add_fails=False):
        self.results = results  # sorted filter items -> voices
        self.add_fails = add_fails
        self.searches = []

    def search_shared_voices(self, **filters):
        self.searches.append(filters)
        return list(self.results.get(tuple(sorted(filters.items())), []))

    def add_shared_voice(self, public_owner_id, voice_id, new_name):
        if self.add_fails:
            raise ElevenLabsError("already added")
        return f"lib-{voice_id}"


def voice(vid, language="ko", verified=()):
    return {"voice_id": vid, "public_owner_id": "owner", "name": vid, "language": language,
            "verified_languages": [{"language": l} for l in verified]}


def key(**f):
    return tuple(sorted(f.items()))


def make(tmp_path, library, buckets=None):
    vm = tmp_path / "voice_map.json"
    vm.write_text(json.dumps({"buckets": buckets or {}}))
    return VoiceSelector(library, vm, tmp_path / "cache.json")


def test_voice_map_wins(tmp_path):
    lib = FakeLibrary({})
    choice = make(tmp_path, lib, {"ko:female:old": "approved"}).select(BUCKET)
    assert (choice.voice_id, choice.source) == ("approved", "voice_map")
    assert lib.searches == []


def test_exact_match_is_added_and_cached(tmp_path):
    lib = FakeLibrary({key(language="ko", gender="female", age="old"): [voice("v1")]})
    choice = make(tmp_path, lib).select(BUCKET)
    assert (choice.voice_id, choice.source) == ("lib-v1", "library:exact")

    again = make(tmp_path, FakeLibrary({})).select(BUCKET)
    assert (again.voice_id, again.source) == ("lib-v1", "cache")


def test_relaxes_age_then_language(tmp_path):
    lib = FakeLibrary({key(gender="female", age="old"): [voice("en1", language="en")]})
    choice = make(tmp_path, lib).select(BUCKET)
    assert choice.source == "library:any_language"
    assert len(lib.searches) == 3


def test_prefers_voice_verified_for_language(tmp_path):
    lib = FakeLibrary({key(gender="female", age="old"): [
        voice("en1", language="en"), voice("multi", language="en", verified=["ko"])]})
    assert make(tmp_path, lib).select(BUCKET).voice_id == "lib-multi"


def test_add_failure_uses_shared_id(tmp_path):
    lib = FakeLibrary({key(language="ko", gender="female", age="old"): [voice("v1")]}, add_fails=True)
    assert make(tmp_path, lib).select(BUCKET).voice_id == "v1"


def test_falls_back_to_default(tmp_path):
    choice = make(tmp_path, FakeLibrary({})).select(BUCKET)
    assert (choice.voice_id, choice.source) == (DEFAULT_VOICES["female"], "default")


def test_search_error_falls_back_to_default(tmp_path):
    class NoPermission(FakeLibrary):
        def search_shared_voices(self, **filters):
            raise ElevenLabsError("missing the permission voices_read")

    selector = make(tmp_path, NoPermission({}))
    assert selector.select(BUCKET).source == "default"
    assert not (tmp_path / "cache.json").exists()


def test_offline_uses_default(tmp_path):
    assert make(tmp_path, None).select(BUCKET).source == "default"
