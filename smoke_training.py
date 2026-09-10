"""Small CPU/CUDA dependency check on CartPole, never controls Terraria."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "cuda"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {"status": "failed", "device": args.device, "environment": "CartPole-v1",
              "seed": 42, "steps": 256, "python": platform.python_version()}
    started = time.perf_counter()
    env = None
    try:
        import gymnasium as gym
        import numpy as np
        import torch
        from stable_baselines3 import PPO
        from stable_baselines3.common.env_checker import check_env

        report["versions"] = {p: importlib.metadata.version(p) for p in ("torch", "gymnasium", "stable-baselines3", "numpy")}
        report["cudaRuntime"] = torch.version.cuda
        report["cudaAvailable"] = torch.cuda.is_available()
        torch.set_num_threads(1)
        torch.manual_seed(42)
        if args.device == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA unavailable; no CPU fallback permitted")
            report["gpu"] = torch.cuda.get_device_name(0)
            report["computeCapability"] = list(torch.cuda.get_device_capability(0))
            report["compiledArchitectures"] = torch.cuda.get_arch_list()
        # Test real kernels and backward, not just device enumeration.
        x = torch.randn(256, 256, device=args.device, requires_grad=True)
        loss = (x @ x.T).square().mean()
        loss.backward()
        if not torch.isfinite(loss) or not torch.isfinite(x.grad).all():
            raise RuntimeError("Nonfinite tensor/gradient")
        if args.device == "cuda":
            torch.cuda.synchronize()
        report["tensorDevice"] = str(x.device)
        report["finiteBackward"] = True
        env = gym.make("CartPole-v1")
        check_env(env.unwrapped)
        model = PPO("MlpPolicy", env, device=args.device, seed=42, n_steps=64,
                    batch_size=32, n_epochs=2, policy_kwargs={"net_arch": [32, 32]}, verbose=0)
        model.learn(total_timesteps=256)
        if not all(torch.isfinite(p).all() for p in model.policy.parameters()):
            raise RuntimeError("Nonfinite trained parameters")
        report["policyDevice"] = str(next(model.policy.parameters()).device)
        if next(model.policy.parameters()).device.type != args.device or model.num_timesteps != 256:
            raise RuntimeError("Unexpected policy device or sample count")
        model_path = args.output_dir / "cartpole-smoke.zip"
        model.save(model_path)
        restored = PPO.load(model_path, env=env, device=args.device)
        obs, _ = env.reset(seed=123)
        action, _ = model.predict(obs, deterministic=True)
        restored_action, _ = restored.predict(obs, deterministic=True)
        if not np.array_equal(action, restored_action):
            raise RuntimeError("Prediction changed after save/load")
        for name, tensor in model.policy.state_dict().items():
            if not torch.equal(tensor, restored.policy.state_dict()[name]):
                raise RuntimeError("Parameters changed after save/load")
        report.update(status="ok", totalTimesteps=model.num_timesteps, saveLoadExact=True,
                      modelSha256=hashlib.sha256(model_path.read_bytes()).hexdigest())
        if args.device == "cuda":
            report["peakAllocatedBytes"] = torch.cuda.max_memory_allocated()
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if env:
            env.close()
        report["elapsedSeconds"] = time.perf_counter() - started
        report["generatedAt"] = datetime.now(timezone.utc).isoformat()
        (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
