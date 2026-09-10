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

    def test_focus_requires_fresh_matching_runtime_samples(self):
        samples = [row(1, 0), row(121, 2)]
        for index, sample in enumerate(samples):
            sample.update(osFocused=index == 0, runtimeAgeMs=5, runtime={"status": "ok", "instanceId": "one",
                          "worldSession": "world", "focused": index == 0})
        result = summarize(samples, 2)
        self.assertTrue(result["focusVerified"])
        self.assertEqual(result["focusedSamples"], 1)
        self.assertEqual(result["unfocusedSamples"], 1)
        for change in (lambda s: s.update(runtimeAgeMs=501),
                       lambda s: s["runtime"].update(instanceId="other"),
                       lambda s: s["runtime"].update(worldSession="other"),
                       lambda s: s["runtime"].update(focused="false")):
            bad = copy.deepcopy(samples)
            change(bad[-1])
            result = summarize(bad, 2)
            self.assertIsNone(result["engineFocusMismatchSamples"])
            self.assertEqual(result["status"], "not_ready")

    def test_engine_focus_is_not_os_focus(self):
        samples = [row(1, 0), row(121, 2)]
        for sample in samples:
            sample.update(osFocused=False, runtimeAgeMs=5, runtime={"status": "ok", "instanceId": "one",
                          "worldSession": "world", "focused": True})
        result = summarize(samples, 2)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["unfocusedSamples"], 2)
        self.assertEqual(result["engineFocusMismatchSamples"], 2)
        del samples[0]["osFocused"]
        self.assertFalse(summarize(samples, 2)["focusVerified"])


if __name__ == "__main__":
    unittest.main()
