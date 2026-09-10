import copy
import unittest

from summarize_stability import qualify


class StabilityQualificationTests(unittest.TestCase):
    def setUp(self):
        self.report = {"status": "ok", "elapsedSeconds": 1800, "deadSamples": 30,
                       "samples": [{"elapsedSeconds": i, "osFocused": i >= 900} for i in range(1801)]}

    def test_both_focus_states_required_and_deaths_reported(self):
        result = qualify(self.report)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["deadSamples"], 30)
        self.assertFalse(result["trainingReady"])
        for row in self.report["samples"]:
            row["osFocused"] = False
        self.assertEqual(qualify(self.report)["status"], "not_ready")

    def test_short_failed_gapped_or_unknown_runs_rejected(self):
        for change in (lambda r: r.update(status="not_ready"),
                       lambda r: r.update(elapsedSeconds=1799),
                       lambda r: r["samples"][1].update(osFocused=None),
                       lambda r: r["samples"].__delitem__(slice(0, 10)),
                       lambda r: r["samples"].__delitem__(slice(1, 10))):
            report = copy.deepcopy(self.report)
            change(report)
            self.assertEqual(qualify(report)["status"], "not_ready")
