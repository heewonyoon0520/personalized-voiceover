"""Thin REST client for the ElevenLabs endpoints this prototype uses.

Uses plain HTTP rather than the SDK so the request/response shapes are
visible in one place: https://elevenlabs.io/docs/api-reference
"""

from __future__ import annotations

from typing import Any

import requests

API_BASE = "https://api.elevenlabs.io"

# Models that accept `language_code` on text-to-speech. eleven_multilingual_v2
# rejects it and infers the language from the text instead.
MODELS_WITH_LANGUAGE_CODE = {"eleven_flash_v2_5", "eleven_turbo_v2_5"}

# ElevenLabs accepts voice_settings.speed in this range.
MIN_SPEED, MAX_SPEED = 0.7, 1.2


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabsClient:
    def __init__(self, api_key: str, timeout: float = 120.0, base_url: str = API_BASE):
        if not api_key:
            raise ElevenLabsError("ELEVENLABS_API_KEY is not set (see .env.example)")
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["xi-api-key"] = api_key

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        resp = self._session.request(method, self._base + path, timeout=self._timeout, **kwargs)
        if not resp.ok:
            raise ElevenLabsError(f"{method} {path} -> {resp.status_code}: {resp.text[:500]}")
        return resp

    def search_shared_voices(
        self,
        *,
        language: str | None = None,
        gender: str | None = None,
        age: str | None = None,
        page_size: int = 30,
        sort: str = "usage_character_count_1y",
    ) -> list[dict]:
        """GET /v1/shared-voices (Voice Library)."""
        params = {"page_size": page_size, "sort": sort}
        for name, value in (("language", language), ("gender", gender), ("age", age)):
            if value:
                params[name] = value
        return self._request("GET", "/v1/shared-voices", params=params).json().get("voices", [])

    def add_shared_voice(self, public_owner_id: str, voice_id: str, new_name: str) -> str:
        """POST /v1/voices/add/{public_user_id}/{voice_id}; returns the library voice_id."""
        resp = self._request(
            "POST", f"/v1/voices/add/{public_owner_id}/{voice_id}", json={"new_name": new_name}
        )
        return resp.json()["voice_id"]

    def text_to_speech(
        self,
        voice_id: str,
        text: str,
        *,
        model_id: str,
        language_code: str | None = None,
        speed: float = 1.0,
        stability: float = 0.6,
        similarity_boost: float = 0.75,
        seed: int | None = None,
        output_format: str = "mp3_44100_128",
    ) -> bytes:
        """POST /v1/text-to-speech/{voice_id}; returns encoded audio bytes."""
        body: dict[str, Any] = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "speed": min(MAX_SPEED, max(MIN_SPEED, speed)),
            },
        }
        if language_code and model_id in MODELS_WITH_LANGUAGE_CODE:
            body["language_code"] = language_code
        if seed is not None:
            body["seed"] = seed
        resp = self._request(
            "POST",
            f"/v1/text-to-speech/{voice_id}",
            params={"output_format": output_format},
            json=body,
        )
        return resp.content
