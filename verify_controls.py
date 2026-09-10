"""Wait for active gameplay, then test short right/jump commands and expiry."""
import json
from pathlib import Path
import time

from bridge_client import request


def main():
    print("Waiting up to 120s for TerraBridge 0.4 and foreground single-player gameplay...", flush=True)
    end = time.monotonic() + 120
    previous = None
    while time.monotonic() < end:
        try:
            ping = request("ping")
            state = request()
            if (ping.get("version") == "0.4" and state.get("status") == "in_world"
                    and state.get("training", {}).get("allowed")
                    and previous and state.get("tick", 0) > previous.get("tick", 0)
                    and time.time() * 1000 - state["sampledAtUnixMs"] < 500):
                break
            previous = state
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    else:
        raise RuntimeError("No fresh gameplay. Load bridge 0.4 and keep game foreground.")

    results = []
    try:
        # Invalid commands must be rejected before affecting the player.
        for command in ("act right 1001", "act right -1", "act fly 100"):
            try:
                request(command)
            except ValueError:
                continue
            raise AssertionError(f"Invalid command accepted: {command}")
        for action in ("right", "jump"):
            before = request()
            ack = request(f"act {action} 250")
            observed = []
            until = time.monotonic() + 0.8
            while time.monotonic() < until:
                time.sleep(0.04)
                observed.append(request())
            after = observed[-1]
            applied = any(s.get("control", {}).get("appliedId") == ack["actionId"]
                          and s["control"]["appliedFrames"] > 0 for s in observed)
            expired = (after["tick"] > before["tick"] and
                       not after["control"]["active"] and after["control"]["action"] == "stop")
            results.append(dict(action=action, ack=ack, before=before, samples=observed,
                                applied=applied, expired=expired))
            assert applied, f"{action} never applied on game thread"
            assert expired, f"{action} did not expire during live gameplay"
            print(f"{action}: applied and automatically released", flush=True)
        request("act left 1000")
        stop = request("stop")
        time.sleep(0.2)
        state = request()
        assert state["control"]["actionId"] == stop["actionId"]
        assert state["control"]["action"] == "stop" and not state["control"]["active"]
        results.append(dict(test="explicit_stop", state=state))
    finally:
        try:
            request("stop")
        finally:
            output = Path(__file__).parent / "evidence" / "control-verification-v04.json"
            output.parent.mkdir(exist_ok=True)
            output.write_text(
                json.dumps(results, indent=2), encoding="utf-8")
    print("LIVE CONTROL CHECKS PASSED; evidence saved to evidence/control-verification-v04.json", flush=True)


if __name__ == "__main__":
    main()
