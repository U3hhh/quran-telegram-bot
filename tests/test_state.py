import json
import tempfile
import unittest
from pathlib import Path

from quran import TOTAL_AYAHS
from state import BotState, StateError, load_state, save_state


class StateTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data" / "state.json"
            state = BotState(cycle=2, used_ayahs=[3, 10])
            state.record_post("2026-08-24-fajr", 3, "2026-08-24T05:17:00+03:00")
            save_state(path, state)
            self.assertEqual(load_state(path).to_dict(), state.to_dict())

    def test_completed_cycle_resets_copy(self) -> None:
        state = BotState(cycle=4, used_ayahs=list(range(1, TOTAL_AYAHS + 1)))
        working = state.prepare_for_selection()
        self.assertEqual(state.cycle, 4)
        self.assertEqual(working.cycle, 5)
        self.assertEqual(working.used_ayahs, [])

    def test_duplicate_ids_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps({"cycle": 1, "used_ayahs": [1, 1], "last_posts": {}}), encoding="utf-8")
            with self.assertRaises(StateError):
                load_state(path)

    def test_slot_history_is_bounded(self) -> None:
        state = BotState()
        for index in range(35):
            state.record_post(f"slot-{index}", index + 1, "now")
        self.assertEqual(len(state.last_posts), 30)
        self.assertNotIn("slot-0", state.last_posts)
        self.assertIn("slot-34", state.last_posts)


if __name__ == "__main__":
    unittest.main()
