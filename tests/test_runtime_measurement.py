import copy
import unittest

from measure_runtime import summarize
from verify_training_gate import invalid_markers


def row(tick, elapsed, dead=False):
    return {"elapsedSeconds": elapsed, "instanceId": "one", "sampleAgeMs": 5,
            "observation": {"status": "in_world", "worldSession": "world", "tick": tick, "player": {"dead": dead}},
            "memory": {"pid": 10, "path": "game", "startedAt": "time", "workingSetBytes": 100, "privateBytes": 200}}


class RuntimeMeasurementTests(unittest.TestCase):
    def test_continuity_does_not_claim_training_or_focus(self):
        result = summarize([row(1, 0), row(121, 2, dead=True)], 2)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["deadSamples"], 1)
        self.assertFalse(result["trainingReady"])
        self.assertFalse(result["focusVerified"])
        self.assertEqual(result["peakPrivateBytes"], 200)

    def test_pause_restart_world_switch_and_short_run_fail(self):
        for change in (lambda r: r.update(sampleAgeMs=600),
                       lambda r: r.update(instanceId="two"),
                       lambda r: r["observation"].update(worldSession="new"),
                       lambda r: r["observation"].update(tick=1),
                       lambda r: r["memory"].update(startedAt="new"),
                       lambda r: r.update(elapsedSeconds=1)):
            end = row(121, 2)
            change(end)
            self.assertEqual(summarize([row(1, 0), end], 2)["status"], "not_ready")

    def test_invalid_marker_cases_leave_original_untouched(self):
        marker = {"schema": 1, "profileId": "id", "purpose": "training", "saveRoot": "D:/profiles/test"}
        original = copy.deepcopy(marker)
        cases = invalid_markers(marker)
        self.assertEqual(marker, original)
        self.assertEqual(len(cases), 5)
        self.assertIn(str(2**80), cases["oversized_schema"])


if __name__ == "__main__":
    unittest.main()
