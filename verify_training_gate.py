"""Reversibly invalidate an isolated profile's marker and verify reset is rejected."""
import argparse
import json
from pathlib import Path
import time

from benchmark_steps import Benchmark
from bridge_client import request


def invalid_markers(marker):
    return {
        "disabled_purpose": json.dumps(dict(marker, purpose="gate-verification-disabled")),
        "broken_json": "{",
        "oversized_schema": json.dumps(dict(marker, schema=2**80)),
        "missing_id": json.dumps({k: v for k, v in marker.items() if k != "profileId"}),
        "wrong_root": json.dumps(dict(marker, saveRoot=str(Path(marker["saveRoot"]).parent))),
    }


def wait_allowed(expected, seconds=4):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        state = request("observe")
        if (state.get("status") == "in_world" and
                state.get("training", {}).get("allowed") is expected):
            return state
        time.sleep(.1)
    raise TimeoutError("Training gate did not refresh; keep game running")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    marker_path = args.profile.resolve()
    original = marker_path.read_bytes()
    marker = json.loads(original)
    if marker_path.parent != Path(marker["saveRoot"]).resolve():
        raise ValueError("Marker directory mismatch")
    client = Benchmark(marker["profileId"])
    before = client.preflight()
    report = {"status": "failed", "before": before, "cases": {}, "instanceId": client.instance_id}
    try:
        for name, content in invalid_markers(marker).items():
            case = report["cases"][name] = {"rejections": {}}
            marker_path.write_text(content, encoding="utf-8")
            case["disabled"] = wait_allowed(False)
            for command in ("checkpoint", "reset"):
                try:
                    request(command)
                except ValueError as exc:
                    if "training_profile_required" not in str(exc):
                        raise
                    case["rejections"][command] = str(exc)
                else:
                    raise AssertionError(f"{command} unexpectedly accepted")
            marker_path.write_bytes(original)
            case["restored"] = wait_allowed(True)
            client.preflight()
    finally:
        marker_path.write_bytes(original)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["restored"] = wait_allowed(True)
    report["status"] = "ok"
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("TRAINING GATE PASSED; original marker restored")


if __name__ == "__main__":
    main()
