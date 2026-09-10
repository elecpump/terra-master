"""Read-only bridge/process sampling with independent Windows foreground telemetry."""
import argparse
import ctypes
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

from bridge_client import request


def window_focus(pid):
    """OS foreground identity, independent of FNA's cached IsActive flag."""
    if sys.platform != "win32":
        return None
    if type(pid) is not int or pid <= 0:
        raise ValueError("Invalid bridge process ID")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
    handle = user32.GetForegroundWindow()
    owner = ctypes.c_ulong()
    if not handle or not user32.GetWindowThreadProcessId(handle, ctypes.byref(owner)):
        return None
    return owner.value == pid


def process_memory(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError("Invalid bridge process ID")
    # Read-only process query; no window input or process management.
    script = (f"$p = Get-Process -Id {pid} -ErrorAction Stop; "
              "$p.Refresh(); @{pid=$p.Id; path=$p.Path; "
              "startedAt=$p.StartTime.ToUniversalTime().ToString('o'); "
              "workingSetBytes=$p.WorkingSet64; privateBytes=$p.PrivateMemorySize64} | ConvertTo-Json -Compress")
    return json.loads(subprocess.check_output(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                                             timeout=5, text=True, creationflags=subprocess.CREATE_NO_WINDOW))


def summarize(samples, requested_seconds):
    issues = []
    if len(samples) < 2:
        issues.append("insufficient_samples")
    states = [s["observation"] for s in samples]
    if any(s.get("status") != "in_world" for s in states):
        issues.append("not_in_world")
    if any(s["sampleAgeMs"] is None or s["sampleAgeMs"] < -100 or s["sampleAgeMs"] > 500 for s in samples):
        issues.append("stale_snapshot_or_clock_skew")
    if len({s["instanceId"] for s in samples}) > 1:
        issues.append("instance_changed")
    if len({s.get("worldSession") for s in states}) > 1:
        issues.append("world_session_changed")
    ticks = [s.get("tick") for s in states]
    if all(t is not None for t in ticks) and any(b <= a for a, b in zip(ticks, ticks[1:])):
        issues.append("tick_stalled_or_rewound")
    elapsed = samples[-1]["elapsedSeconds"] if samples else 0
    if elapsed < requested_seconds:
        issues.append("incomplete_duration")
    memory = [s["memory"] for s in samples if s.get("memory")]
    if len({(s["pid"], s["path"], s["startedAt"]) for s in memory}) > 1:
        issues.append("process_identity_changed")
    dead = sum(s.get("player", {}).get("dead", False) for s in states)
    runtime_rows = [s for s in samples if "runtime" in s]
    for s in runtime_rows:
        r = s["runtime"]
        if (r.get("status") != "ok" or r.get("instanceId") != s["instanceId"] or
                r.get("worldSession") != s["observation"].get("worldSession") or
                type(r.get("focused")) is not bool or
                not -100 <= s.get("runtimeAgeMs", float("inf")) <= 500):
            issues.append("invalid_runtime_snapshot")
            break
    focus_verified = bool(samples) and all(type(s.get("osFocused")) is bool for s in samples)
    engine_verified = bool(samples) and len(runtime_rows) == len(samples) and "invalid_runtime_snapshot" not in issues
    return {"status": "ok" if not issues else "not_ready", "issues": issues,
            "sampleCount": len(samples), "elapsedSeconds": elapsed, "deadSamples": dead,
            "peakWorkingSetBytes": max((s["workingSetBytes"] for s in memory), default=None),
            "peakPrivateBytes": max((s["privateBytes"] for s in memory), default=None),
            "focusVerified": focus_verified,
            "focusSource": "windows_foreground_process" if focus_verified else "unavailable",
            "focusedSamples": sum(s["osFocused"] for s in samples) if focus_verified else None,
            "unfocusedSamples": sum(not s["osFocused"] for s in samples) if focus_verified else None,
            "engineFocusMismatchSamples": sum(s["osFocused"] != s["runtime"]["focused"] for s in samples)
                if focus_verified and engine_verified else None,
            "trainingReady": False,
            "limitation": "Read-only runtime continuity, not action/reset or foreground/background certification. Death samples are reported separately."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).parent / "runtime-manifest.json")
    args = parser.parse_args()
    if not 2 <= args.seconds <= 1800:
        parser.error("seconds must be 2..1800")
    samples = []
    report = {"schema": 2, "status": "failed", "requestedSeconds": args.seconds, "samples": samples}
    started = time.perf_counter()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        expected_process = Path(manifest["artifacts"]["tmodloader"]["path"]).parent / "dotnet" / "dotnet.exe"
        while True:
            ping = request("ping")
            if ping.get("bridge") != "TerraBridge" or ping.get("status") != "ok" or ping.get("version") not in ("0.4", "0.4.1") or not ping.get("instanceId"):
                raise ValueError("Requires TerraBridge 0.4/0.4.1 with instance/process identity")
            state = request("observe")
            row = {"elapsedSeconds": time.perf_counter() - started, "instanceId": ping["instanceId"],
                   "sampleAgeMs": time.time() * 1000 - state["sampledAtUnixMs"] if "sampledAtUnixMs" in state else None,
                   "observation": state}
            samples.append(row)
            row["osFocused"] = window_focus(ping["processId"])
            if ping["version"] == "0.4.1":
                row["runtime"] = request("runtime")
                row["runtimeAgeMs"] = time.time() * 1000 - row["runtime"].get("sampledAtUnixMs", 0)
            if len(samples) == 1 or len(samples) % 10 == 0:
                row["memory"] = process_memory(ping["processId"])
                if Path(row["memory"]["path"]).resolve() != expected_process.resolve():
                    raise ValueError("Bridge PID executable does not match installed runtime")
            if row["elapsedSeconds"] >= args.seconds:
                break
            time.sleep(min(1, args.seconds - row["elapsedSeconds"]))
        report.update(summarize(samples, args.seconds))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        report["error"] = str(exc)
    finally:
        report["generatedAt"] = datetime.now(timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
