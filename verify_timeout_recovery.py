"""Verify the same paused operation stays timed out after gameplay resumes."""
import argparse
import json
from pathlib import Path

from benchmark_steps import Benchmark, completed
from bridge_client import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paused-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prior = json.loads(args.paused_report.read_text(encoding="utf-8"))
    if prior.get("status") != "ok" or prior.get("mode") != "paused-timeout":
        raise ValueError("Successful paused-timeout report required")
    client = Benchmark(prior["profileId"])
    client.instance_id = prior["instanceId"]
    client.world_session = prior["worldSession"]
    report = {"status": "failed", "pausedReport": str(args.paused_report)}
    try:
        report["resumed"] = client.preflight()
        if report["resumed"]["tick"] <= prior["final"]["tick"]:
            raise ValueError("World has not resumed")
        expected = {k: v for k, v in prior["timeoutResult"].items() if k != "requestWallSeconds"}
        report["cachedTimeout"] = request(f'result {expected["operationId"]}')
        if report["cachedTimeout"] != expected:
            raise ValueError("Old timeout changed after resume")
        report["newStep"] = client.run("step idle 6")
        completed(report["newStep"], "step", 6)
        report["status"] = "ok"
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("TIMEOUT RECOVERY PASSED")


if __name__ == "__main__":
    main()
