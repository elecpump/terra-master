# 训练依赖与硬件 smoke

本工具只验证依赖、数值计算、PPO 更新及模型保存/加载，不连接 Terraria，也不提供 Terraria 的 Gym 适配器。游戏场景、死亡终止语义等前置条件未完成前，不启动 Terraria 训练。

## 安装

目标环境为 Windows x64 / Python 3.11。核心桥接脚本仍只依赖标准库；训练栈采用独立锁文件 `requirements-training-win-py311.lock`，可安装在项目 `.venv`：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-training-win-py311.lock
.\.venv\Scripts\python.exe -m pip check
```

PyTorch 锁定为 2.8.0 的 CUDA 12.8 构建，使用官方 wheel 直链及 SHA-256；其余依赖固定完整版本。该锁只适用于 Windows CPython 3.11，不可直接拿去 Linux 或其他 Python 版本安装。[PyTorch 官方对应版本安装说明](https://pytorch.org/get-started/previous-versions/#v280)提供 CUDA 12.8 构建；[SB3 2.7.1 安装要求](https://stable-baselines3.readthedocs.io/en/v2.7.1/guide/install.html)作为兼容核对依据。是否能使用当前 GPU 以实际运算测试为准。

## 验证

```powershell
.\.venv\Scripts\python.exe smoke_training.py --device cpu --output-dir runs/smoke-cpu
.\.venv\Scripts\python.exe smoke_training.py --device cuda --output-dir runs/smoke-cuda
```

每次固定 seed=42、CartPole-v1、256 steps、n_steps=64、batch_size=32、n_epochs=2、两层 32 单元 MLP，使用一个 PyTorch CPU 线程。CUDA 模式要求真实 CUDA 可用，禁止静默回退 CPU。

先运行矩阵乘法及反向传播，再执行环境 checker、短 PPO 更新、参数有限值检查。保存模型并重新加载，核对全部参数逐项相等及固定观测上的确定性动作一致。报告保存版本、实际设备、CUDA runtime、GPU 架构、模型哈希、墙钟时间；模型存放在被 Git 忽略的 runs 目录。

这是兼容性 smoke，不是性能基准或模型质量评估。小型 MLP 可能更适合 CPU；GPU smoke 通过不等于 Terraria 游戏 tick 加速，也不证明大模型或长时间训练稳定。256 步 CartPole 结果不能作为 Terraria 学习证据。
