"""Publish one non-repeating Quran verse to a Telegram channel."""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from quran import QuranError, TOTAL_AYAHS, Verse, fetch_verse
from state import BotState, StateError, load_state, save_state
from telegram import TelegramError, send_message


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "state.json"
TIMEZONE_NAME = "Asia/Baghdad"
SLOT_NAMES = {"fajr", "dhuhr", "maghrib", "manual"}
random_source = random.SystemRandom()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish one Quran verse to Telegram")
    parser.add_argument("--dry-run", action="store_true", help="fetch/display only")
    parser.add_argument("--validate", action="store_true", help="validate state only")
    parser.add_argument("--slot", choices=sorted(SLOT_NAMES))
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    return parser


def get_baghdad_now() -> datetime:
    try:
        return datetime.now(ZoneInfo(TIMEZONE_NAME))
    except ZoneInfoNotFoundError as error:
        raise RuntimeError(f"timezone data does not contain {TIMEZONE_NAME}") from error


def get_slot_name(explicit_slot: str | None) -> str:
    slot = explicit_slot or os.getenv("QURAN_SLOT", "manual").strip().lower()
    if slot not in SLOT_NAMES:
        raise RuntimeError("QURAN_SLOT/--slot must be fajr, dhuhr, maghrib, or manual")
    return slot


def build_slot_key(slot_name: str, now: datetime) -> str:
    date_part = now.strftime("%Y-%m-%d")
    if slot_name == "manual":
        return f"{date_part}-manual-{now.strftime('%H%M%S')}"
    return f"{date_part}-{slot_name}"


def choose_unused_ayah(state: BotState) -> tuple[BotState, int]:
    working_state = state.prepare_for_selection()
    used = set(working_state.used_ayahs)
    if TOTAL_AYAHS - len(used) <= 0:
        raise RuntimeError("no unused ayah is available")

    while True:
        candidate = random_source.randint(1, TOTAL_AYAHS)
        if candidate not in used:
            return working_state, candidate


def format_message(verse: Verse) -> str:
    return (
        f"﴿ {verse.text} ﴾\n\n"
        f"📖 {verse.surah_name} — الآية {verse.ayah_number}\n\n"
        "🤍 تذكير بآية من كتاب الله"
    )


def print_preview(verse: Verse, cycle: int, slot_key: str) -> None:
    print(f"Dry run — cycle: {cycle} — ayah ID: {verse.ayah_id} — slot: {slot_key}")
    print("Would post:")
    print(format_message(verse))
    print("State was not modified.")


def validate_state_file(path: Path) -> int:
    state = load_state(path)
    print(
        f"State is valid: cycle={state.cycle}, "
        f"used_ayahs={len(state.used_ayahs)}/{TOTAL_AYAHS}, "
        f"recent_slots={len(state.last_posts)}"
    )
    return 0


def run(args: argparse.Namespace) -> int:
    if args.validate:
        return validate_state_file(args.state_path)

    slot_name = get_slot_name(args.slot)
    now = get_baghdad_now()
    slot_key = build_slot_key(slot_name, now)
    state = load_state(args.state_path)

    if slot_name != "manual" and state.has_posted_slot(slot_key):
        print(f"Slot {slot_key} was already posted successfully; exiting without a duplicate.")
        return 0

    working_state, ayah_id = choose_unused_ayah(state)
    verse = fetch_verse(ayah_id)

    if args.dry_run:
        print_preview(verse, working_state.cycle, slot_key)
        return 0

    bot_token = os.getenv("BOT_TOKEN", "")
    channel_id = os.getenv("CHANNEL_ID", "")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is missing")
    if not channel_id:
        raise RuntimeError("CHANNEL_ID is missing")

    message_id = send_message(bot_token, channel_id, format_message(verse))
    working_state.used_ayahs.append(ayah_id)
    working_state.record_post(slot_key, ayah_id, now.isoformat(timespec="seconds"))
    save_state(args.state_path, working_state)
    print(
        f"Published ayah ID {ayah_id} in cycle {working_state.cycle} "
        f"for slot {slot_key}; Telegram message ID {message_id}."
    )
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args()
    try:
        return run(args)
    except (QuranError, TelegramError, StateError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
