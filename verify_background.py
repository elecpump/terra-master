"""Verify background opt-in by toggling only an already-verified training marker."""
import argparse
import json
from pathlib import Path
import time

from bridge_client import request
from measure_runtime import window_focus


def verify(marker_path, report):
    marker_path = marker_path.resolve()
    original = marker_path.read_bytes()
    marker = json.loads(original)
    if (marker.get("schema") != 1 or marker.get("purpose") != "training" or
            Path(marker["saveRoot"]).resolve() != marker_path.parent or
            marker.get("runInBackground") is not True):
        raise ValueError("Enabled training marker required")
    ping = request("ping")
    if ping.get("version") != "0.4.3" or ping.get("bridge") != "TerraBridge":
        raise ValueError("Requires TerraBridge 0.4.3")
    first = request("observe")
    identity = (ping["instanceId"], first.get("worldSession"))

    def sample():
        runtime = request("runtime")
        state = request("observe")
        if ((runtime.get("instanceId"), runtime.get("worldSession")) != identity or
                state.get("worldSession") != identity[1] or state.get("status") != "in_world" or
                state.get("training", {}).get("allowed") is not True or
                state["training"].get("profileId") != marker["profileId"] or
                runtime.get("status") != "ok" or runtime.get("menu") is not False or
                not -100 <= time.time() * 1000 - runtime.get("sampledAtUnixMs", 0) <= 500):
            raise ValueError("Runtime/session/training identity invalid")
        if runtime.get("osFocused") is not False or window_focus(ping["processId"]) is not False:
            raise ValueError("Both native focus measurements must report unfocused")
        return {"runtime": runtime, "observation": state}

    before = sample()
    if before["runtime"].get("paused") is not False:
        raise ValueError("Close manual pause before background verification")
    report.update(instanceId=identity[0], worldSession=identity[1], before=before, phases={})
    try:
        for enabled in (False, True):
            marker_path.write_text(json.dumps(dict(marker, runInBackground=enabled)), encoding="utf-8")
            # Refresh uses wall time, including while the world is paused.
            time.sleep(2)
            a = sample()
            time.sleep(2)
            b = sample()
            report["phases"][str(enabled)] = [a, b]
            if any(r["runtime"].get("backgroundEnabled") is not enabled or
                   r["runtime"].get("paused") is not (not enabled) for r in (a, b)):
                raise ValueError("Background gate/pause state mismatch")
            advanced = b["observation"]["tick"] > a["observation"]["tick"]
            if advanced != enabled or (not enabled and a["observation"]["tick"] != b["observation"]["tick"]):
                raise ValueError("World progression did not follow background gate")
        report["status"] = "ok"
    finally:
        marker_path.write_bytes(original)
        report["markerRestored"] = marker_path.read_bytes() == original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"status": "failed"}
    try:
        verify(args.profile, report)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report.update(status="failed", error=str(exc))
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("phases", "before")}))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
