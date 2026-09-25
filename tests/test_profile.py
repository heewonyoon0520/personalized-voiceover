import pytest

from voicedub.profile import PatientProfile, VoiceBucket, age_band_for


@pytest.mark.parametrize("age,band", [(20, "young"), (34, "young"), (35, "middle_aged"),
                                      (59, "middle_aged"), (60, "old"), (88, "old")])
def test_age_bands(age, band):
    assert age_band_for(age) == band


def test_bucket_key():
    assert PatientProfile(67, "female", "ko").bucket().key == "ko:female:old"


def test_other_gender_uses_fallback():
    assert PatientProfile(40, "other", "en").bucket("male").gender == "male"


def test_bucket_roundtrip():
    assert VoiceBucket.from_key("ja:male:young") == VoiceBucket("ja", "male", "young")


def test_rejects_unknown_language():
    with pytest.raises(ValueError):
        PatientProfile(40, "female", "xx")
