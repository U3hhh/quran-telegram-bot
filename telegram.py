"""Small, dependency-free client for Telegram's Bot API."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
HTTP_TIMEOUT_SECONDS = 20


class TelegramError(RuntimeError):
    """Raised when Telegram does not confirm a message was sent."""


def send_message(bot_token: str, channel_id: str, text: str) -> int:
    """Send exactly one message and return Telegram's message ID.

    This function deliberately makes one request only. A timeout can happen
    after Telegram accepted a message, so automatically retrying could post a
    duplicate verse.
    """

    if not bot_token.strip():
        raise TelegramError("BOT_TOKEN is empty")
    if not channel_id.strip():
        raise TelegramError("CHANNEL_ID is empty")

    body = json.dumps(
        {
            "chat_id": channel_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        TELEGRAM_API_URL.format(token=bot_token),
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "quran-telegram-bot/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            raw_body = response.read()
    except urllib.error.HTTPError as error:
        raise TelegramError(f"Telegram API returned HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise TelegramError("Telegram API request failed or timed out; message status is unknown") from error

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise TelegramError("Telegram API returned invalid JSON") from error

    if not isinstance(payload, dict) or payload.get("ok") is not True:
        description = payload.get("description") if isinstance(payload, dict) else None
        if isinstance(description, str) and description:
            raise TelegramError(f"Telegram rejected the message: {description}")
        raise TelegramError("Telegram API returned an unsuccessful response")

    result = payload.get("result")
    message_id = result.get("message_id") if isinstance(result, dict) else None
    if not isinstance(message_id, int):
        raise TelegramError("Telegram API response did not include a message ID")

    return message_id
