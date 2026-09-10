import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from verify_background import verify


class BackgroundVerificationTests(unittest.TestCase):
    def run_case(self, fail_after_write=False, focused=False):
        with tempfile.TemporaryDirectory() as directory:
            marker_path = Path(directory) / "terramaster-training.json"
            original = json.dumps({"schema": 1, "purpose": "training", "saveRoot": directory,
                                   "profileId": "profile", "runInBackground": True}).encode()
            marker_path.write_bytes(original)
            tick = [1]

            def request(command):
                enabled = json.loads(marker_path.read_bytes())["runInBackground"]
                if fail_after_write and not enabled:
                    raise OSError("Disconnected")
                if command == "ping":
                    return {"version": "0.4.3", "bridge": "TerraBridge", "instanceId": "instance", "processId": 1}
                if command == "runtime":
                    return {"status": "ok", "instanceId": "instance", "worldSession": "world", "menu": False,
                            "osFocused": focused, "paused": not enabled, "backgroundEnabled": enabled,
                            "sampledAtUnixMs": time.time() * 1000}
                self.assertEqual(command, "observe")
                tick[0] += int(enabled)
                return {"status": "in_world", "worldSession": "world", "tick": tick[0],
                        "training": {"allowed": True, "profileId": "profile"}}

            report = {}
            with patch("verify_background.request", side_effect=request), patch("verify_background.time.sleep"), \
                    patch("verify_background.window_focus", return_value=focused):
                if fail_after_write or focused:
                    with self.assertRaises((OSError, ValueError)):
                        verify(marker_path, report)
                else:
                    verify(marker_path, report)
                    self.assertEqual(report["status"], "ok")
            self.assertEqual(marker_path.read_bytes(), original)

    def test_gate_counterfactual(self):
        self.run_case()

    def test_restores_marker_after_disconnect(self):
        self.run_case(fail_after_write=True)

    def test_focused_game_rejected_before_marker_change(self):
        self.run_case(focused=True)
