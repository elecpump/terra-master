"""Qualify a 30-minute run without treating runtime continuity as training readiness."""
import argparse
import hashlib
import json
from pathlib import Path


def qualify(report):
    samples = report.get("samples", [])
    seconds = {True: 0.0, False: 0.0}
    gaps = []
    for previous, current in zip(samples, samples[1:]):
        delta = current["elapsedSeconds"] - previous["elapsedSeconds"]
        if delta <= 0 or delta > 5:
            gaps.append(delta)
            continue
        focus = previous.get("osFocused")
        if type(focus) is bool and current.get("osFocused") is focus:
            seconds[focus] += delta
    issues = []
    if report.get("status") != "ok":
        issues.append("runtime_measurement_failed")
    if report.get("elapsedSeconds", 0) < 1800:
        issues.append("less_than_30_minutes")
    if (not samples or samples[0]["elapsedSeconds"] > 5 or
            samples[-1]["elapsedSeconds"] < 1800 or
            samples[-1]["elapsedSeconds"] != report.get("elapsedSeconds")):
        issues.append("incomplete_sample_coverage")
    if not samples or any(type(s.get("osFocused")) is not bool for s in samples):
        issues.append("missing_os_focus")
    if seconds[True] < 600 or seconds[False] < 600:
        issues.append("less_than_10_minutes_in_each_focus_state")
    if gaps:
        issues.append("invalid_or_over_5_second_sampling_gap")
    return {"status": "ok" if not issues else "not_ready", "issues": issues,
            "foregroundSampledSeconds": seconds[True], "backgroundSampledSeconds": seconds[False],
            "elapsedSeconds": report.get("elapsedSeconds"), "sampleCount": len(samples),
            "deadSamples": report.get("deadSamples"), "samplingGaps": gaps,
            "peakWorkingSetBytes": report.get("peakWorkingSetBytes"),
            "peakPrivateBytes": report.get("peakPrivateBytes"), "trainingReady": False,
            "criteria": ">=1800 seconds total, >=600 seconds per focus state, no runtime issues or >5-second sample gaps",
            "limitation": "Focus duration is estimated between equal-focus sample endpoints. This checks runtime continuity, not action correctness, determinism or a death-free training scene."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.report.read_bytes()
    result = qualify(json.loads(raw))
    result.update(sourceReport=str(args.report), sourceSha256=hashlib.sha256(raw).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
