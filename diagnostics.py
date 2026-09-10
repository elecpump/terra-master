"""Read-only TerraBridge 0.3/0.4 doctor and passive benchmark (no action/reset calls)."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys
import time

from bridge_client import request

ROOT = Path(__file__).resolve().parent


def compatible(ping):
    return (ping.get("protocol") == 1 and ping.get("bridge") == "TerraBridge"
            and ping.get("status") == "ok" and ping.get("version") in ("0.3", "0.4", "0.4.1"))


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    index = (len(ordered) - 1) * fraction
    lo = math.floor(index)
    hi = math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def sample_summary(samples):
    """Reject discontinuities rather than converting them to throughput."""
    issues = []
    if len(samples) < 2:
        issues.append("insufficient_samples")
    observations = [s["observation"] for s in samples]
    if any(o.get("status") != "in_world" for o in observations):
        issues.append("not_in_world")
    elif observations:
        worlds = {o["world"]["id"] for o in observations}
        sessions = {o.get("worldSession") for o in observations}
        ticks = [o["tick"] for o in observations]
        if len(worlds) != 1 or len(sessions) != 1 or any(b < a for a, b in zip(ticks, ticks[1:])):
            issues.append("world_or_tick_discontinuity")
        if any(s["sample_age_ms"] < -100 or s["sample_age_ms"] > 500 for s in samples):
            issues.append("stale_snapshot_or_clock_skew")
        if any(o["player"]["dead"] for o in observations):
            issues.append("player_dead")
        if any(o.get("control", {}).get("active") for o in observations):
            issues.append("external_control_active")
        if len(ticks) > 1 and ticks[-1] == ticks[0]:
            issues.append("tick_not_advancing")
    elapsed = samples[-1]["elapsed_s"] - samples[0]["elapsed_s"] if len(samples) > 1 else 0
    tick_delta = None
    if len(observations) > 1 and not {"not_in_world", "world_or_tick_discontinuity"}.intersection(issues):
        tick_delta = observations[-1]["tick"] - observations[0]["tick"]
    latencies = [s["request_ms"] for s in samples]
    return {
        "status": "ok" if not issues else "not_ready", "issues": issues,
        "sample_count": len(samples), "elapsed_s": elapsed, "tick_delta": tick_delta,
        "tick_per_wall_second": tick_delta / elapsed if elapsed > 0 and not issues else None,
        "observe_latency_ms": {"p50": percentile(latencies, .5), "p95": percentile(latencies, .95)},
        "transition_per_second": None, "step_latency_ms": None, "reset_latency_ms": None,
        "game_memory_bytes": None,
        "limitations": "Passive observations only; no transitions, reset or process-memory measurement. "
                        "Focus and external/manual inputs are not observable in protocol 1. "
                        "Tick samples do not establish whole-world synchronization.",
    }


def collect(seconds, interval, port, send=request, samples=None):
    samples = [] if samples is None else samples
    started = time.perf_counter()
    while True:
        before = time.perf_counter()
        observation = send("observe", port)
        after = time.perf_counter()
        stamp = observation.get("sampledAtUnixMs")
        samples.append({"elapsed_s": after - started, "request_ms": (after - before) * 1000,
                        "sample_age_ms": time.time() * 1000 - stamp if stamp is not None else None,
                        "observation": observation})
        if after - started >= seconds:
            return samples
        time.sleep(min(interval, seconds - (after - started)))


def doctor(port, send=request):
    report = {"status": "not_ready", "issues": [], "port": port,
              "python": {"version": platform.python_version(), "executable": sys.executable,
                         "project_venv": Path(sys.prefix).resolve() == ROOT / ".venv"},
              "training_marker": "unknown_protocol_1", "device": {"cuda": "not_tested"},
              "dependencies": {}}
    for package in ("gymnasium", "stable-baselines3", "torch"):
        try:
            report["dependencies"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report["dependencies"][package] = None
    manifest_path = ROOT / "runtime-manifest.json"
    try:
        report["runtime_manifest"] = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        for name, entry in report["runtime_manifest"]["artifacts"].items():
            path = Path(entry["path"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            if digest != entry["sha256"]:
                report["issues"].append(f"artifact_missing_or_changed:{name}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["issues"].append("runtime_manifest_unavailable_or_invalid")
        report["manifest_error"] = str(exc)
    try:
        report["ping"] = send("ping", port)
        if report.get("runtime_manifest") and report["ping"].get("version") != report["runtime_manifest"].get("expectedBridgeVersion"):
            report["issues"].append("loaded_bridge_version_differs_from_manifest")
        if not compatible(report["ping"]):
            report["issues"].append("incompatible_bridge")
        else:
            report["samples"] = []
            collect(1, .25, port, send, report["samples"])
            report["sampling"] = sample_summary(report["samples"])
            report["training_marker"] = report["samples"][-1]["observation"].get("training", "unknown_protocol_1")
            report["issues"].extend(report["sampling"]["issues"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["issues"].append("bridge_unavailable_or_invalid_response")
        report["error"] = str(exc)
    report["status"] = "ok" if not report["issues"] else "not_ready"
    report["training_ready"] = False
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("doctor", "bench"))
    parser.add_argument("--port", type=int, default=17655)
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--interval", type=float, default=.25)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not (1 <= args.port <= 65535 and 1 <= args.seconds <= 1800 and .05 <= args.interval <= 1):
        parser.error("port: 1..65535; seconds: 1..1800; interval: 0.05..1")
    if args.command == "doctor":
        report = doctor(args.port)
    else:
        report = {"status": "not_ready", "mode": "passive_observe", "samples": []}
        try:
            report["ping"] = request("ping", args.port)
            if not compatible(report["ping"]):
                raise ValueError("Requires TerraBridge 0.3, 0.4 or 0.4.1 / protocol 1")
            collect(args.seconds, args.interval, args.port, samples=report["samples"])
            report.update(sample_summary(report["samples"]))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            report["status"] = "not_ready"
            report["error"] = str(exc)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["report_schema"] = 1
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    if args.output:
        print(json.dumps({"status": report["status"], "output": str(args.output),
                          "issues": report.get("issues", []), "error": report.get("error")}, ensure_ascii=False))
    else:
        print(text)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
