"""Persistent, atomic state for non-repeating Quran cycles."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quran import TOTAL_AYAHS


MAX_SLOT_HISTORY = 30


class StateError(RuntimeError):
    """Raised when state.json is missing required or valid data."""


@dataclass
class BotState:
    cycle: int = 1
    used_ayahs: list[int] = field(default_factory=list)
    last_posts: dict[str, dict[str, Any]] = field(default_factory=dict)

    def copy(self) -> "BotState":
        return BotState(
            cycle=self.cycle,
            used_ayahs=list(self.used_ayahs),
            last_posts={key: dict(value) for key, value in self.last_posts.items()},
        )

    def prepare_for_selection(self) -> "BotState":
        """Reset only an already-complete cycle in a working copy."""
        working = self.copy()
        if len(working.used_ayahs) == TOTAL_AYAHS:
            working.cycle += 1
            working.used_ayahs.clear()
        return working

    def has_posted_slot(self, slot_key: str) -> bool:
        return slot_key in self.last_posts

    def record_post(self, slot_key: str, ayah_id: int, posted_at: str) -> None:
        self.last_posts[slot_key] = {"ayah_id": ayah_id, "posted_at": posted_at}
        if len(self.last_posts) > MAX_SLOT_HISTORY:
            oldest_keys = list(self.last_posts)[:-MAX_SLOT_HISTORY]
            for key in oldest_keys:
                del self.last_posts[key]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "used_ayahs": self.used_ayahs,
            "last_posts": self.last_posts,
        }


def _validate_state(data: Any) -> BotState:
    if not isinstance(data, dict):
        raise StateError("state.json must contain a JSON object")

    cycle = data.get("cycle")
    used_ayahs = data.get("used_ayahs")
    last_posts = data.get("last_posts")
    if not isinstance(cycle, int) or isinstance(cycle, bool) or cycle < 1:
        raise StateError("state.json has an invalid cycle number")
    if not isinstance(used_ayahs, list) or len(used_ayahs) > TOTAL_AYAHS:
        raise StateError("state.json used_ayahs must be a list of valid ayah IDs")

    normalized_ids: list[int] = []
    for ayah_id in used_ayahs:
        if not isinstance(ayah_id, int) or isinstance(ayah_id, bool) or not 1 <= ayah_id <= TOTAL_AYAHS:
            raise StateError("state.json contains an invalid ayah ID")
        normalized_ids.append(ayah_id)
    if len(set(normalized_ids)) != len(normalized_ids):
        raise StateError("state.json contains duplicate ayah IDs")

    if not isinstance(last_posts, dict):
        raise StateError("state.json last_posts must be an object")
    for slot_key, post in last_posts.items():
        if not isinstance(slot_key, str) or not slot_key or not isinstance(post, dict):
            raise StateError("state.json contains an invalid posting record")
        if "ayah_id" in post:
            post_ayah_id = post["ayah_id"]
            if not isinstance(post_ayah_id, int) or isinstance(post_ayah_id, bool) or not 1 <= post_ayah_id <= TOTAL_AYAHS:
                raise StateError("state.json contains an invalid posted ayah ID")

    return BotState(
        cycle=cycle,
        used_ayahs=normalized_ids,
        last_posts={str(key): dict(value) for key, value in last_posts.items()},
    )


def load_state(path: Path) -> BotState:
    """Load state or return a fresh state if the file does not exist."""

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return BotState()
    except OSError as error:
        raise StateError(f"could not read {path}: {error}") from error

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise StateError(f"{path} is corrupted JSON; no state was changed") from error
    return _validate_state(data)


def save_state(path: Path, state: BotState) -> None:
    """Atomically replace state.json after a successful Telegram post."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name
            json.dump(state.to_dict(), temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    except OSError as error:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
        raise StateError(f"could not save {path}: {error}") from error
