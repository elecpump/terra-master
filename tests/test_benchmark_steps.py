import copy
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from benchmark_steps import Benchmark, require_training, run_benchmark, verify_paused
from training_profile import prepare


class FakeBridge:
    def __init__(self):
        self.calls = []
        self.instance = "instance-1"
        self.fail = None
        self.state = {"status": "in_world", "worldSession": "world-session",
                      "tick": 10, "sampledAtUnixMs": time.time() * 1000,
                      "training": {"allowed": True, "profileId": "profile"},
                      "player": {"dead": False, "x": 10, "y": 20, "velocityX": 0,
                                 "velocityY": 0, "life": 100, "mana": 20, "direction": 1}}
        self.next_id = 0
        self.result = None

    def __call__(self, command, port):
        self.calls.append(command)
        if command == "ping":
            return {"protocol": 1, "bridge": "TerraBridge", "version": "0.4", "status": "ok", "instanceId": self.instance}
        if command == "observe":
            return copy.deepcopy(self.state)
        if command.startswith("result "):
            if self.fail:
                raise OSError("Disconnected after action acknowledgement")
            return copy.deepcopy(self.result)
        self.next_id += 1
        parts = command.split()
        self.result = {"operationId": self.next_id, "kind": parts[0], "status": "completed",
                       "executedFrames": int(parts[2]) if parts[0] == "step" else 0,
                       "observation": copy.deepcopy(self.state)}
        return {"status": "accepted", "operationId": self.next_id}


class BenchmarkTests(unittest.TestCase):
    def test_full_benchmark_and_frame_accounting(self):
        bridge = FakeBridge()
        report = {"steps": [], "resets": []}
        run_benchmark(Benchmark("profile", send=bridge), report, steps=3)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["executedFrames"], 22)
        self.assertEqual([c for c in bridge.calls if c.startswith("step")], ["step idle 1", "step idle 6", "step idle 15"])
        self.assertEqual(len(report["resets"]), 1)

    def test_ordinary_world_never_receives_mutation(self):
        bridge = FakeBridge()
        bridge.state["training"]["allowed"] = False
        with self.assertRaises(ValueError):
            Benchmark("profile", send=bridge).run("checkpoint")
        self.assertEqual(bridge.calls, ["ping", "observe"])

    def test_wrong_profile_and_stale_or_dead_world_rejected(self):
        for change in (lambda s: s["training"].update(profileId="other"),
                       lambda s: s["training"].update(allowed="true"),
                       lambda s: s.update(control={"active": True}),
                       lambda s: s.update(sampledAtUnixMs=0),
                       lambda s: s["player"].update(dead=True)):
            bridge = FakeBridge()
            change(bridge.state)
            with self.assertRaises(ValueError):
                Benchmark("profile", send=bridge).run("checkpoint")
            self.assertNotIn("checkpoint", bridge.calls)

    def test_restart_and_world_change_stop_next_operation(self):
        for change in (lambda b: setattr(b, "instance", "instance-2"),
                       lambda b: b.state.update(worldSession="new-world")):
            bridge = FakeBridge()
            client = Benchmark("profile", send=bridge)
            client.preflight()
            change(bridge)
            with self.assertRaises(ValueError):
                client.run("reset")
            self.assertNotIn("reset", bridge.calls)

    def test_disconnect_does_not_retry_or_globally_cancel(self):
        bridge = FakeBridge()
        bridge.fail = True
        with self.assertRaises(OSError):
            Benchmark("profile", send=bridge).run("step idle 6")
        self.assertEqual(bridge.calls.count("step idle 6"), 1)
        self.assertNotIn("stop", bridge.calls)

    def test_completion_from_other_world_rejected(self):
        bridge = FakeBridge()
        def send(command, port):
            response = bridge(command, port)
            if command.startswith("result"):
                response["observation"]["worldSession"] = "other-world"
            return response
        with self.assertRaises(ValueError):
            Benchmark("profile", send=send).run("step idle 6")

    def test_paused_timeout_accepts_only_zero_frames(self):
        for frames in (0, 1):
            bridge = FakeBridge()
            def send(command, port):
                response = bridge(command, port)
                if command.startswith("result"):
                    response.update(status="timeout", executedFrames=frames)
                return response
            with patch("benchmark_steps.time.sleep"):
                report = {}
                if frames:
                    with self.assertRaises(ValueError):
                        verify_paused(Benchmark("profile", send=send), report)
                else:
                    verify_paused(Benchmark("profile", send=send), report)
                    self.assertEqual(report["status"], "ok")

    def test_profile_does_not_overwrite_or_escape_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            marker = prepare("test", workspace)
            root = Path(marker["saveRoot"])
            self.assertTrue((root / "Players").is_dir())
            for name in ("test", "../escape", "CON:", "UPPER", "a/b"):
                with self.assertRaises(ValueError):
                    prepare(name, workspace)
            self.assertEqual(list((root / "Players").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
