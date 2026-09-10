"""Bounded, single-client step/reset benchmark for verified TerraBridge 0.4/0.4.1/0.4.2/0.4.3 training saves."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from bridge_client import request
from diagnostics import percentile


def require_training(state, profile_id, world_session=None, fresh=True):
    if (state.get("status") != "in_world" or state.get("training", {}).get("allowed") is not True
            or state["training"].get("profileId") != profile_id):
        raise ValueError("Verified local training profile required")
    if not state.get("worldSession") or (world_session and state["worldSession"] != world_session):
        raise ValueError("World session changed")
    if state["player"]["dead"]:
        raise ValueError("Player dead; no valid benchmark transition")
    if state.get("control", {}).get("active"):
        raise ValueError("Another timed control is active")
    if fresh and not -100 <= time.time() * 1000 - state["sampledAtUnixMs"] <= 500:
        raise ValueError("Stale observation or clock skew")
    return state["worldSession"]


class Benchmark:
    def __init__(self, profile_id, port=17655, send=request):
        self.profile_id, self.port, self.send = profile_id, port, send
        self.instance_id = None
        self.world_session = None

    def preflight(self, fresh=True):
        ping = self.send("ping", self.port)
        if (ping.get("protocol") != 1 or ping.get("bridge") != "TerraBridge" or
                ping.get("version") not in ("0.4", "0.4.1", "0.4.2", "0.4.3") or ping.get("status") != "ok" or not ping.get("instanceId")):
            raise ValueError("Requires TerraBridge 0.4/0.4.1/0.4.2/0.4.3 / protocol 1")
        if self.instance_id and ping["instanceId"] != self.instance_id:
            raise ValueError("Bridge restarted")
        state = self.send("observe", self.port)
        self.world_session = require_training(state, self.profile_id, self.world_session, fresh)
        self.instance_id = ping["instanceId"]
        return state

    def run(self, command, fresh=True):
        self.preflight(fresh)
        started = time.perf_counter()
        ack = self.send(command, self.port)
        if ack.get("status") != "accepted" or type(ack.get("operationId")) is not int:
            raise ValueError("Invalid operation acknowledgement")
        operation_id = ack["operationId"]
        while time.perf_counter() - started < 6:
            result = self.send(f"result {operation_id}", self.port)
            if result.get("operationId") != operation_id:
                raise ValueError("Operation identity mismatch")
            if result.get("status") != "pending":
                result = dict(result, requestWallSeconds=time.perf_counter() - started)
                if result["status"] == "completed":
                    require_training(result["observation"], self.profile_id, self.world_session, fresh=False)
                return result
            time.sleep(.01)
        # Protocol 1 has no directed cancellation; never issue a global stop that
        # could cancel another client's newer action. Never retry a mutation.
        raise TimeoutError("No terminal result within client deadline; operation is not retried")


def completed(result, kind, frames=0):
    if (result.get("status") != "completed" or result.get("kind") != kind or
            result.get("executedFrames") != frames):
        raise ValueError(f"Invalid {kind} result: {result}")


def restored(result, baseline):
    completed(result, "reset")
    player = result["observation"]["player"]
    if (any(player[key] != baseline[key] for key in ("x", "y", "life", "mana", "direction")) or
            player["velocityX"] != 0 or player["velocityY"] != 0):
        raise ValueError("Player checkpoint restoration mismatch")


def run_benchmark(client, report, steps=30, budget=30):
    started = time.perf_counter()
    def check_budget():
        if time.perf_counter() - started >= budget:
            raise TimeoutError("Benchmark wall-clock budget exhausted")

    state = client.preflight()
    if state["player"]["velocityX"] != 0 or state["player"]["velocityY"] != 0:
        raise ValueError("Stand still before checkpoint")
    check_budget()
    checkpoint = client.run("checkpoint")
    report["checkpoint"] = checkpoint
    completed(checkpoint, "checkpoint")
    baseline = checkpoint["observation"]["player"]
    # Protocol 1 can accept a checkpoint that SolidCollision later rejects.
    # Verify the actual restore path before collecting any transitions.
    check_budget()
    report["preflightReset"] = client.run("reset")
    restored(report["preflightReset"], baseline)
    report["preflightSeconds"] = time.perf_counter() - started
    for index in range(steps):
        check_budget()
        frames = (1, 6, 15)[index % 3]
        result = client.run(f"step idle {frames}")
        report["steps"].append({"requestedFrames": frames, "result": result})
        completed(result, "step", frames)
    check_budget()
    reset = client.run("reset")
    report["resets"].append(reset)
    restored(reset, baseline)
    elapsed = time.perf_counter() - started
    if elapsed > budget:
        raise TimeoutError("Benchmark completed after wall-clock budget")
    latency = [row["result"]["requestWallSeconds"] * 1000 for row in report["steps"]]
    report.update(status="ok", elapsedSeconds=elapsed,
                  transitionsPerSecondIncludingPreflightAndReset=steps / elapsed,
                  stepLatencyMs={"p50": percentile(latency, .5), "p95": percentile(latency, .95)},
                  resetLatencyMs=reset["requestWallSeconds"] * 1000,
                  executedFrames=sum(row["result"]["executedFrames"] for row in report["steps"]))
    report["stepLatencyByFramesMs"] = {}
    for frames in (1, 6, 15):
        values = [row["result"]["requestWallSeconds"] * 1000 for row in report["steps"]
                  if row["requestedFrames"] == frames]
        report["stepLatencyByFramesMs"][str(frames)] = {
            "count": len(values), "p50": percentile(values, .5), "p95": percentile(values, .95)}


def verify_paused(client, report):
    before = client.preflight(fresh=False)
    time.sleep(1)
    after = client.preflight(fresh=False)
    if after["tick"] != before["tick"]:
        raise ValueError("Pause game before running timeout verification")
    result = client.run("step idle 1", fresh=False)
    report.update(before=before, after=after, timeoutResult=result)
    if result.get("status") != "timeout" or result.get("executedFrames") != 0:
        raise ValueError("Expected timeout with zero executed frames")
    final = client.preflight(fresh=False)
    if final["tick"] != after["tick"]:
        raise ValueError("World advanced during paused timeout test")
    report.update(status="ok", final=final,
                  limitation="Paused timeout only; resume/recovery must be verified separately")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("steps", "paused-timeout"))
    parser.add_argument("--profile", type=Path, required=True, help="terramaster-training.json")
    parser.add_argument("--port", type=int, default=17655)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--budget", type=float, default=30)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not (1 <= args.steps <= 300 and 1 <= args.budget <= 120 and 1 <= args.port <= 65535):
        parser.error("steps 1..300, budget 1..120 seconds, port 1..65535")
    report = {"schema": 2, "mode": args.mode, "status": "failed", "steps": [], "resets": [],
              "budgetSeconds": args.budget, "requestedSteps": args.steps,
              "timeMode": "realtime", "resetScope": "player_checkpoint", "action": "idle"}
    try:
        marker = json.loads(args.profile.read_text(encoding="utf-8-sig"))
        if marker.get("schema") != 1 or marker.get("purpose") != "training":
            raise ValueError("Invalid profile marker")
        report["profileId"] = marker["profileId"]
        client = Benchmark(marker["profileId"], args.port)
        if args.mode == "steps":
            run_benchmark(client, report, args.steps, args.budget)
        else:
            verify_paused(client, report)
        report["instanceId"] = client.instance_id
        report["worldSession"] = client.world_session
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report.update(status="failed", error=str(exc))
    finally:
        report["generatedAt"] = datetime.now(timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "error": report.get("error"), "output": str(args.output)}))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
