"""Patient profile -> coarse voice bucket.

Only the bucket (language, gender, age band) is used to pick a voice. The
patient's exact age never leaves this module, and every patient in the same
bucket shares the same rendered narration, so audio can be pre-rendered and
cached instead of generated per patient.
"""

from __future__ import annotations

from dataclasses import dataclass

# Age-band labels match the ElevenLabs Voice Library `age` filter.
AGE_BANDS: tuple[tuple[int, int, str], ...] = (
    (0, 34, "young"),
    (35, 59, "middle_aged"),
    (60, 150, "old"),
)
AGE_BAND_NAMES = tuple(name for _, _, name in AGE_BANDS)

VOICE_GENDERS = ("female", "male")
PATIENT_GENDERS = VOICE_GENDERS + ("other",)

SUPPORTED_LANGUAGES = {
    "ko": "한국어",
    "en": "English",
    "ja": "日本語",
    "zh": "中文",
    "es": "Español",
    "de": "Deutsch",
    "fr": "Français",
    "vi": "Tiếng Việt",
}


def age_band_for(age: int) -> str:
    for low, high, name in AGE_BANDS:
        if low <= age <= high:
            return name
    raise ValueError(f"age out of range: {age}")


@dataclass(frozen=True)
class VoiceBucket:
    language: str
    gender: str
    age_band: str

    def __post_init__(self) -> None:
        if self.language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language: {self.language}")
        if self.gender not in VOICE_GENDERS:
            raise ValueError(f"unsupported voice gender: {self.gender}")
        if self.age_band not in AGE_BAND_NAMES:
            raise ValueError(f"unknown age band: {self.age_band}")

    @property
    def key(self) -> str:
        return f"{self.language}:{self.gender}:{self.age_band}"

    @classmethod
    def from_key(cls, key: str) -> "VoiceBucket":
        language, gender, age_band = key.split(":")
        return cls(language, gender, age_band)


@dataclass(frozen=True)
class PatientProfile:
    age: int
    gender: str  # "female" | "male" | "other"
    language: str  # ISO 639-1, the language selected in the app

    def __post_init__(self) -> None:
        if self.gender not in PATIENT_GENDERS:
            raise ValueError(f"gender must be one of {PATIENT_GENDERS}")
        if self.language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language: {self.language}")
        age_band_for(self.age)

    def bucket(self, fallback_gender: str = "female") -> VoiceBucket:
        """Map to a voice bucket. Patients who chose "other" (or did not say)
        get `fallback_gender`; make this a user setting in the real app."""
        gender = self.gender if self.gender in VOICE_GENDERS else fallback_gender
        return VoiceBucket(self.language, gender, age_band_for(self.age))
