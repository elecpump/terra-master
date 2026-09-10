# M0 隔离训练实例与基准

0.4 保留 protocol 1 文本命令与实时世界运行方式，观测 schema 升至 2。训练门禁用于防止意外修改普通存档，不是抵御恶意本机用户的安全机制。

## 创建、构建与启动

```powershell
.\.venv\Scripts\python.exe training_profile.py training-m0
.\build_bridge.ps1 -SavePath "$PWD\profiles\training-m0"
.\start_training.ps1 -Name training-m0
```

创建命令只接受简单 profile 名称；存在的目录拒绝覆盖，不导入、复制或编辑普通角色和世界。重新使用已有目录时跳过第一行。更新模组前正常保存并退出对应实例，不绕过文件锁覆盖加载中的包。

启动使用安装版自带 launcher 与 `-tmlsavedirectory`。此参数会把 SavePath 和共享保存路径指向给定目录，核对依据为安装版提交 [666f699 的 Program.TML.cs](https://github.com/tModLoader/tModLoader/blob/666f69962d3bdffde54fc14025f02634965b4e7c/patches/tModLoader/Terraria/Program.TML.cs#L255)。启动脚本检查端口占用并记录 launcher PID，但该 PID 不等同于游戏 PID，不执行进程终止操作。

在游戏中创建名称均以 `TM-Training-` 开头的本地角色与世界。选择经典角色、小型经典世界可用于当前 smoke。不要启用云存档。进入世界、站稳后，`observe.training.allowed` 应为 true；角色和世界均需实际保存在此 profile 的 Players/Worlds 目录。

模组在游戏线程检查 marker 的 schema/purpose/profileId/saveRoot、单人状态、角色/世界名称、本地路径和重解析点。每秒刷新一次，checkpoint/reset 执行前再次核验；未通过时清除检查点并拒绝训练重置。普通移动命令保留供 Campaign 正常行动使用。退出世界更换 worldSession；模组加载生成 instanceId，用于检测观测回退和基准过程中重连。

## 验收命令

```powershell
.\.venv\Scripts\python.exe benchmark_steps.py steps --profile profiles/training-m0/terramaster-training.json --steps 30 --budget 30 --output runs/m0-v04/steps.json
.\.venv\Scripts\python.exe verify_steps.py
.\.venv\Scripts\python.exe verify_controls.py
.\.venv\Scripts\python.exe verify_training_gate.py --profile profiles/training-m0/terramaster-training.json --output runs/m0-v04/gate.json
```

这些命令会接管输入或恢复玩家检查点，运行时使用独立训练实例和单一客户端。主动基准先 checkpoint 并立即 reset，核验位置、生命、魔力、朝向与零速度；通过后才轮换 1/6/15 帧 idle 动作，最后再次 reset 核验。报告 schema 2 的 `preflightReset` 单独保存试恢复结果，`resets` 保存末尾恢复；`preflightSeconds` 记录初始检查耗时。报告包括完成快照、执行帧数、端到端吞吐、动作分组延迟和末尾 reset 时间。总计时从首次预检前开始，包含 checkpoint 和两次 reset；旧 schema 1 报告不重算，不能直接作为同口径速度对比。世界在请求间持续运行。

`--budget` 限制后续操作的提交，正在执行的操作有 5 秒服务端截止时间；单次 socket 最多等待 3 秒，客户端轮询截止为 6 秒，因此退出可能略晚于预算。超预算结果标为失败。失败不重放动作，也不使用全局 stop 取消可能属于其他客户端的新动作；已有 protocol 1 不能提供完整会话隔离或定向取消，留待 M1。

`verify_training_gate.py` 依次测试无效 purpose、破损 JSON、超出 Int32 范围的 schema、缺失 profileId、错误 saveRoot，确认 checkpoint/reset 均被服务器拒绝，每例恢复 marker 并重新验证可用性，最终在 finally 恢复原始字节。它不更改角色或世界文件。云存档和路径重定向仍未实机测试。

## 暂停与恢复

开启自动暂停并打开物品栏/设置，确认游戏 tick 停止后运行：

```powershell
.\.venv\Scripts\python.exe benchmark_steps.py paused-timeout --profile profiles/training-m0/terramaster-training.json --output runs/m0-v04/paused-timeout.json
```

命令先确认一秒内 tick 不变，再提交 idle 1 帧；必须返回 timeout、executedFrames=0，且整个测试期间 tick 不变。恢复游戏后应复查该 operationId 的缓存结果仍为 timeout，再运行一个新 step 确认恢复。前半段通过不代表恢复段已验收。

原型 0.3 的历史证据保留在根目录；0.4 控制与 step 回归写到 `evidence/*-v04.json`，避免覆盖旧证据。真实运行清单应使用隔离模组包采集：

```powershell
.\capture_runtime.ps1 -ModPath "$PWD\profiles\training-m0\Mods\TerraBridge.tmod"
```

## 只读运行与内存采样

```powershell
.\.venv\Scripts\python.exe measure_runtime.py --seconds 60 --output runs/runtime-60s.json
```

采样 duration 范围 2–1800 秒；每秒读取 ping/observe，每十个样本读取已核对进程路径的工作集和 private bytes。记录实例重启、世界会话变化、帧号停滞/回退、陈旧快照及采样不足；死亡样本单独计数。该工具不发动作、不 reset、不管理进程，不会声称训练就绪。新版用 Windows 前台进程独立记录焦点，0.4.1–0.4.3 同时读取 runtime 与引擎焦点作对照。

30 分钟验收目标是前后台各 15 分钟，最低要求总计 1800 秒、每种状态至少 600 秒、无运行异常或超过 5 秒的采样空档。相邻样本焦点一致时估算该间隔的焦点时长；不把切换间隔归入任何一侧。死亡数量如实报告，运行连续性通过不等于场景或训练就绪。

```powershell
.\.venv\Scripts\python.exe measure_runtime.py --seconds 1800 --output runs/stability/report.json --progress-output runs/stability/progress.json
.\.venv\Scripts\python.exe summarize_stability.py runs/stability/report.json --output evidence/stability-summary.json
```

`--progress-output` 每约 30 秒写出简要进展，最终写入结论。完整逐秒报告放在 runs 中；汇总包含原报告 SHA-256，可核对原始证据。未达到时长、焦点覆盖或采样完整性时汇总明确失败，不以短测拼凑 30 分钟结果。

本阶段仍不提供完整世界 reset、死亡 terminated transition、PPO 训练、同步推进或多实例能力。独立存档不等于受控导航场景；自然生成世界仍会刷怪、演化和杀死角色。
