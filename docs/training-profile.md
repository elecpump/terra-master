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

这些命令会接管输入或恢复玩家检查点，运行时使用独立训练实例和单一客户端。主动基准仅发送 idle 动作，轮换 1/6/15 帧，最后一次 reset 核验位置、生命、魔力、朝向与零速度。报告包括完成快照、执行帧数、端到端吞吐、动作分组延迟和 reset 时间。网络耗时与预检会让实际吞吐低于理论值；世界在请求间持续运行。

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

采样 duration 范围 2–1800 秒；每秒读取 ping/observe，每十个样本读取已核对进程路径的工作集和 private bytes。记录实例重启、世界会话变化、帧号停滞/回退、陈旧快照及采样不足；死亡样本单独计数。该工具不发动作、不 reset、不管理进程，不会声称训练就绪。它没有观测实际前台窗口，因此即使持续 1800 秒通过也不能独自满足“30 分钟前后台稳定性”门槛。

本阶段仍不提供完整世界 reset、死亡 terminated transition、PPO 训练、同步推进或多实例能力。独立存档不等于受控导航场景；自然生成世界仍会刷怪、演化和杀死角色。
