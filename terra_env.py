"""Synchronous Python facade over a live, continuously running Terraria world.

reset restores a recorded player checkpoint, NOT the world or inventory.
No gymnasium dependency or training algorithm is required for this prototype.
"""
import time
from bridge_client import request


class TerraEnv:
    ACTIONS = ("idle", "left", "right", "jump", "left_jump", "right_jump")

    def __init__(self, port=17655, frames=6):
        if not 1 <= frames <= 120:
            raise ValueError("frames must be 1..120")
        self.port = port
        self.frames = frames
        self.previous = None
        ping = request("ping", self.port)
        if ping.get("version") != "0.4" or ping.get("bridge") != "TerraBridge":
            raise ValueError("TerraEnv requires TerraBridge 0.4 with training profile validation")

    def _run(self, command):
        ack = request(command, self.port)
        operation_id = ack["operationId"]
        try:
            end = time.monotonic() + 6
            while time.monotonic() < end:
                result = request(f"result {operation_id}", self.port)
                if result["status"] == "completed":
                    return result
                if result["status"] != "pending":
                    raise RuntimeError(f"Operation failed: {result}")
                time.sleep(0.01)
            raise TimeoutError("Game paused or bridge operation timed out")
        except BaseException:
            try:
                request("stop", self.port)
            except (OSError, ValueError):
                pass
            raise

    def checkpoint(self):
        """Record an alive, stationary, unmounted player's baseline in this world."""
        result = self._run("checkpoint")
        self.previous = result["observation"]
        return self.previous

    def reset(self):
        result = self._run("reset")
        self.previous = result["observation"]
        return self.previous, {"reset_scope": "player_checkpoint", "operationId": result["operationId"]}

    def step(self, action):
        if action not in self.ACTIONS:
            raise ValueError(f"action must be one of {self.ACTIONS}")
        if self.previous is None:
            raise RuntimeError("Call checkpoint() or reset() first")
        result = self._run(f"step {action} {self.frames}")
        observation = result["observation"]
        if result["executedFrames"] != self.frames:
            raise RuntimeError(f"Unexpected frame count: {result}")
        # Placeholder locomotion reward: horizontal progress measured in tiles.
        reward = (observation["player"]["x"] - self.previous["player"]["x"]) / 16
        self.previous = observation
        return observation, reward, observation["player"]["dead"], False, {
            "operationId": result["operationId"], "executedFrames": result["executedFrames"],
            "world_continues_between_steps": True,
        }

    def close(self):
        request("stop", self.port)
