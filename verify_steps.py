"""Live smoke test: record start, move in exact frames, reset twice."""
import json
from pathlib import Path
import time
from bridge_client import request
from terra_env import TerraEnv


def main():
    print("Waiting for bridge 0.4/0.4.1; enter a test world, stand still, keep game foreground.", flush=True)
    end = time.monotonic() + 180
    old = None
    while time.monotonic() < end:
        try:
            ping = request("ping")
            state = request()
            p = state.get("player", {})
            if (ping.get("version") in ("0.4", "0.4.1") and state.get("status") == "in_world"
                    and state.get("training", {}).get("allowed")
                    and old and state["tick"] > old.get("tick", 0)
                    and p.get("velocityX") == p.get("velocityY") == 0):
                break
            old = state
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    else:
        raise TimeoutError("Game not ready")
    env = TerraEnv()
    evidence = []
    try:
        baseline = env.checkpoint()
        evidence.append({"checkpoint": baseline})
        for frames in (1, 6, 15):
            env.frames = frames
            obs, reward, terminated, truncated, info = env.step("right")
            assert info["executedFrames"] == frames
            evidence.append(dict(frames=frames, observation=obs, reward=reward, info=info))
            print(f"step(right, {frames}): exact applied frame count verified", flush=True)
            reset, info = env.reset()
            for field in ("x", "y", "life", "mana", "direction"):
                assert reset["player"][field] == baseline["player"][field], (field, reset)
            assert reset["player"]["velocityX"] == reset["player"]["velocityY"] == 0
            evidence.append({"reset": reset, "info": info})
        # Same result ID must yield the immutable completion observation.
        last_id = info["operationId"]
        first = request(f"result {last_id}")
        time.sleep(0.1)
        assert first == request(f"result {last_id}")
        print("Checkpoint restoration and immutable result verified", flush=True)
    finally:
        env.close()
        output = Path(__file__).parent / "evidence" / "step-verification-v04.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("LIVE STEP/RESET CHECKS PASSED", flush=True)


if __name__ == "__main__":
    main()
