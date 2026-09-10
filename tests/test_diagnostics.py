import unittest
from unittest.mock import patch

from diagnostics import collect, compatible, doctor, sample_summary


def sample(tick, elapsed, world=1, age=10, status="in_world"):
    return {"elapsed_s": elapsed, "request_ms": 2, "sample_age_ms": age,
            "observation": {"status": status, "tick": tick, "world": {"id": world},
                            "player": {"dead": False}, "control": {"active": False}}}


class DiagnosticsTests(unittest.TestCase):
    def test_valid_rate_is_not_transition_throughput(self):
        result = sample_summary([sample(10, 0), sample(70, 1)])
        self.assertEqual(result["tick_per_wall_second"], 60)
        self.assertIsNone(result["transition_per_second"])
        self.assertEqual(result["status"], "ok")

    def test_pause_menu_and_world_change_reject_rate(self):
        for end in [sample(10, 1), sample(70, 1, age=1000), sample(70, 1, world=2),
                    sample(2, 1), sample(70, 1, status="menu"), sample(70, 1, age=-1000)]:
            with self.subTest(end=end):
                result = sample_summary([sample(10, 0), end])
                self.assertEqual(result["status"], "not_ready")
                self.assertIsNone(result["tick_per_wall_second"])

    def test_reject_wrong_bridge_version(self):
        self.assertFalse(compatible({"protocol": 1, "bridge": "TerraBridge", "status": "ok", "version": "0.2"}))

    def test_offline_is_machine_readable(self):
        def offline(command, port):
            self.assertEqual(command, "ping")
            raise OSError("offline")
        result = doctor(17655, offline)
        self.assertEqual(result["status"], "not_ready")
        self.assertIn("bridge_unavailable_or_invalid_response", result["issues"])
        self.assertFalse(result["training_ready"])

    def test_doctor_never_sends_mutating_commands(self):
        calls = []
        def send(command, port):
            calls.append(command)
            if command == "ping":
                return {"protocol": 1, "bridge": "TerraBridge", "status": "ok", "version": "0.3"}
            return sample(1, 0)["observation"]
        with patch("diagnostics.time.perf_counter", side_effect=[0, 0, 0, 1, 1]), patch("diagnostics.time.sleep"):
            doctor(17655, send)
        self.assertEqual(calls, ["ping", "observe", "observe"])

    def test_disconnect_keeps_partial_samples(self):
        samples = []
        with patch("diagnostics.time.sleep"), patch("diagnostics.time.perf_counter", side_effect=[0, 0, .1, .2]):
            with self.assertRaises(OSError):
                collect(1, .25, 17655,
                        send=unittest.mock.Mock(side_effect=[sample(1, 0)["observation"], OSError("lost")]),
                        samples=samples)
        self.assertEqual(len(samples), 1)


if __name__ == "__main__":
    unittest.main()
