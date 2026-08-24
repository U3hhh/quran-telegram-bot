"""Quran verse retrieval using the AlQuran Cloud API."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


TOTAL_AYAHS = 6236
API_URL = "https://api.alquran.cloud/v1/ayah/{ayah_id}/quran-uthmani"
HTTP_TIMEOUT_SECONDS = 20
MAX_RETRIES = 3


class QuranError(RuntimeError):
    """Raised when a Quran verse cannot be fetched or validated."""


@dataclass(frozen=True)
class Verse:
    """The fields needed to publish one verse."""

    ayah_id: int
    text: str
    surah_name: str
    ayah_number: int


def _is_retryable_http_error(error: urllib.error.HTTPError) -> bool:
    return error.code == 429 or 500 <= error.code <= 599


def _request_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "quran-telegram-bot/1.0",
        },
        method="GET",
    )

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                raw_body = response.read()
            payload = json.loads(raw_body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise QuranError("Quran API returned a JSON value with an invalid shape")
            return payload
        except urllib.error.HTTPError as error:
            last_error = error
            if not _is_retryable_http_error(error) or attempt == MAX_RETRIES - 1:
                raise QuranError(f"Quran API returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
            last_error = error
            if attempt == MAX_RETRIES - 1:
                raise QuranError("Quran API request failed after retries") from error

        time.sleep(2**attempt)

    raise QuranError("Quran API request failed") from last_error


def fetch_verse(ayah_id: int) -> Verse:
    """Fetch and validate a verse by its stable global ayah ID."""

    if not isinstance(ayah_id, int) or isinstance(ayah_id, bool) or not 1 <= ayah_id <= TOTAL_AYAHS:
        raise QuranError(f"Ayah ID must be an integer between 1 and {TOTAL_AYAHS}")

    payload = _request_json(API_URL.format(ayah_id=ayah_id))
    if payload.get("code") != 200 or payload.get("status") != "OK":
        raise QuranError("Quran API returned an unsuccessful response")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise QuranError("Quran API response is missing data")

    returned_id = data.get("number")
    text = data.get("text")
    surah = data.get("surah")
    ayah_number = data.get("numberInSurah")

    if returned_id != ayah_id:
        raise QuranError("Quran API returned a different ayah ID")
    if not isinstance(text, str) or not text.strip():
        raise QuranError("Quran API returned empty ayah text")
    if not isinstance(surah, dict) or not isinstance(surah.get("name"), str) or not surah["name"].strip():
        raise QuranError("Quran API returned an invalid Arabic surah name")
    if not isinstance(ayah_number, int) or isinstance(ayah_number, bool) or ayah_number < 1:
        raise QuranError("Quran API returned an invalid ayah number")

    return Verse(
        ayah_id=ayah_id,
        text=text.strip(),
        surah_name=surah["name"].strip(),
        ayah_number=ayah_number,
    )
