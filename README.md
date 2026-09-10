# TerraMaster：游戏接入原型

项目设计入口：[完整架构](docs/ARCHITECTURE.md) · [执行计划](docs/EXECUTION_PLAN.md) · [项目上下文](docs/PROJECT_CONTEXT.md)。长期目标为自主探索与最终通关；以下内容记录当前已实现原型。

目前实现本机 TCP 观测、短时动作控制、按帧计数的 step 与玩家检查点重置（TerraBridge 0.4，protocol 1）。0.4 增加隔离训练存档校验、实例/世界会话标识与主动性能验收；完整世界仍实时运行，尚未实现完整场景重置或 Terraria 训练管线。

## M0 第三切片：最终包与 GPU 依赖（2026-09-10）

最终 0.4 包已重载，五类异常 marker（含超大 schema 数值）均被安全拒绝且原始 marker 恢复。新增只读运行/内存采样和 CPU/CUDA 依赖 smoke，17 项离线测试通过。

项目 `.venv` 已使用 **PyTorch 2.8.0+cu128**，配合 Gymnasium 1.2.3、SB3 2.7.1。RTX 5090 D v2 实际 CUDA 运算、反向传播、256 步 CartPole PPO、模型保存加载均通过；完整版本锁为 [requirements-training-win-py311.lock](requirements-training-win-py311.lock)，复跑见 [smoke 指南](docs/dependency-smoke.md)。没有启动 Terraria 模型训练。

60 秒采样的峰值工作集约 869 MiB，但含 19 个死亡样本；后续采样检测到停滞。最终包补做的三次 step 成功，reset 因位置/玩家状态检查被拒绝，整轮标为失败。30 分钟前后台稳定性与 D1 仍未完成。详见 [第三切片报告](docs/m0-final-report.md)。

## M0 第二切片：隔离存档与主动验收（2026-09-10）

参见 [隔离实例与验收指南](docs/training-profile.md)。`training_profile.py` 创建全新独立目录；`build_bridge.ps1 -SavePath` 构建到该目录；`start_training.ps1` 使用安装版 launcher 启动，拒绝端口冲突。普通存档不会被自动复制或修改。

0.4 的 checkpoint/reset 仅接受有效训练 marker 下的本地 `TM-Training-` 角色和世界，校验失败直接拒绝。`observe.training` 提供状态，`worldSession` 区分进入世界，ping 提供 instanceId、processId、timeMode、observationSchema。`TerraEnv`、两个主动回归脚本要求 0.4；只读 doctor/bench 兼容 0.3/0.4。

本次结果：

- 安装版编译打包 0 错误、0 警告；隔离实例实际加载 0.4，训练角色和世界校验通过。
- 30 次混合 1/6/15 帧 idle 动作，合计精确执行 220 帧；含预检和一次 reset 共 5.091 秒，吞吐 5.89 transition/s。混合延迟 p50 116 ms / p95 280 ms；reset 30.8 ms。不是固定 6 帧策略的吞吐。
- 控制、输入释放、1/6/15 帧移动与检查点恢复通过。撤销 marker 时 checkpoint/reset 均被服务器拒绝，恢复 marker 后重新允许。
- 暂停时 idle 1 帧约 5 秒返回 timeout、执行 0 帧；恢复后旧超时结果不变，新 6 帧 step 完成。
- 14 项离线测试通过。原始记录见 [第二切片报告](docs/m0-active-report.md)。最终补充的损坏 marker 数字格式异常处理已编译；实机记录来自补充前的 0.4 包，两个包哈希分别保留，当时尚未重载，该缺口已由第三切片闭环。

M0 尚未完成 30 分钟前后台稳定性、内存测量与训练依赖 smoke；D1 同步实验尚未开始。训练目录中的自然世界仍会刷怪、造成伤害，隔离目录不等于可重复重置的训练场景。

## M0 首个切片历史：诊断与被动基准（2026-09-10）

新增标准库工具 [diagnostics.py](diagnostics.py)，保留原型接口与模组 0.3。先建立项目环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\capture_runtime.ps1
.\.venv\Scripts\python.exe diagnostics.py doctor --output runs/m0/doctor.json
.\.venv\Scripts\python.exe diagnostics.py bench --seconds 5 --output runs/m0/bench.json
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- `doctor` 核对已安装程序集/模组 SHA-256、桥接版本、Python 环境、依赖及一秒内 tick 新鲜度。退出码 0 表示本次诊断通过，1 表示未就绪；**不表示可以训练**，`training_ready` 固定为 false。
- `bench` 只发送 ping/observe，不移动角色或恢复检查点。记录 tick/s、观测请求 p50/p95、原始快照和采样耗时；帧号回退、切世界、死亡、暂停/陈旧快照均不输出有效 tick/s。请求失败时保留此前采样。
- step/transition 吞吐、reset 时间和游戏内存尚未测量，对应字段为 null。当前协议也不能验证训练标记、窗口焦点、人工输入或完整实体同步。
- [capture_runtime.ps1](capture_runtime.ps1) 记录安装版和源码哈希；可指定 `-TmlInstallPath`、`-ModPath`、`-OutputPath`。仅在有意更新基线时重新采集；doctor 用现有清单检测安装文件漂移。磁盘包哈希不能证明游戏当前加载的包与源码对应。
- `.venv/`、`runs/`、`profiles/`、存档、模型与构建缓存被 Git 排除，小型验收证据保存在 `evidence/`。当前依赖锁为空第三方依赖集；Gymnasium/SB3/PyTorch 与 CUDA 验证留待后续切片。

本次实机结果：TerraBridge 0.3 / protocol 1；21 个观测样本，5.022 秒推进 301 tick（59.93 tick/s），观测请求延迟 p50 0.40 ms / p95 23.24 ms。6 项离线测试通过。详见 [基线报告](docs/baseline-report.md)。这是短时被动采样，M0 的 30 分钟前后台稳定性、隔离训练存档、暂停超时验收及 D1 同步实验仍未完成。

## 已验证环境

- 游戏安装：`D:\software\Steam\steamapps\common\tModLoader`
- 游戏版本：Terraria 1.4.4.9 / tModLoader 2026.07.3.0，.NET 8
- 参考源码：`D:\code\tModLoader`。该源码 targets 使用 .NET 10，不能直接当作已安装稳定版的构建依赖。
- 使用游戏自带编译器构建 TerraBridge 成功：0 errors / 0 warnings，不需要单独安装 SDK。

## 构建与加载

在此目录运行 `powershell -ExecutionPolicy Bypass -File .\build_bridge.ps1`。
可传入 `-TmlInstallPath '你的游戏安装目录'`。

构建产物默认位于 `%USERPROFILE%\Documents\My Games\Terraria\tModLoader\Mods\TerraBridge.tmod`。
游戏中启用 **Terra RL Bridge** 后重新加载模组；也可正常退出并重启游戏。
进入测试世界后执行：

```powershell
python bridge_client.py ping
python bridge_client.py observe
python bridge_client.py watch
python bridge_client.py act right --ms 250
python bridge_client.py act jump --ms 250
python bridge_client.py stop
```

`ping` 应返回 `protocol: 1, status: ok, bridge: TerraBridge`。
主菜单的观测为 `status: menu`；世界中为 `status: in_world`，包含玩家位置、速度、生命等。
移动玩家时观察 x/y 和 tick 是否变化。Ctrl+C 停止 watch。

## 协议与边界

- 仅监听 `127.0.0.1:17655`，一次连接一条 ASCII 命令，以换行结束。
- 支持 `ping\n`、`observe\n`、`act ACTION MS\n`、`stop\n`；响应为单行 UTF-8 JSON。
- ACTION 为 left / right / jump / left_jump / right_jump，持续时间为 1–1000 毫秒。新动作替换旧动作。
- 动作通过 ModPlayer.SetControls 在游戏线程修改输入；使用单调时钟到期，下一次游戏更新释放输入。断开客户端不会延长动作；暂停期间已过期的动作不会在恢复后继续执行。
- 动作响应 accepted 表示已接收；观测中的 control.appliedId 与 appliedFrames 才表示已在游戏线程应用。active 表示采样时是否尚未到期，必须同时检查快照新鲜度。
- 0.3 游戏线程每次更新发布快照；网络线程只读快照并提交命令，不访问游戏对象。
- 位置单位为像素；world 尺寸单位为方块；速度为游戏更新对应的像素速度。
- 游戏暂停时快照不再更新，检查 `sampleAgeMs` 和 `tick`。step 操作有 5 秒截止时间，暂停过久会失败。
- `ping` 只证明模组通信正常，不证明世界正在推进。
- 不直接编辑存档。动作会产生正常游戏后果；只在单人世界接管左右移动和跳跃，首轮实验使用测试世界。动作期间不要同时手动操作。
- 端口冲突会写入 `client.log`；同一时间只启动一个启用桥接的游戏实例。

## 当前验证状态

2026-09-09：模组已通过真实 tModLoader 编译并打包（0 errors / 0 warnings）。游戏重启后，真实 TCP `ping` 返回 `{"protocol":1,"status":"ok","bridge":"TerraBridge"}`，主菜单 `observe` 返回 `status: menu`。

进入世界后实测成功：约 1.1 秒内 tick 从 702 增至 768，玩家位置从 (51302.332, 6406) 变为 (51180.863, 6382.9507)，生命 100/100；速度与朝向也发生变化。游戏加载、通信及持续世界内遥测已验证。

实测切回聊天时曾出现 tick 停止；保持游戏前台后恢复。后续训练必须处理失焦/暂停，并实现动作与观测的时间对齐。

## 动作验收（历史 0.3，当前脚本要求 0.4）

运行 `python verify_controls.py` 后切回游戏。脚本等待实时更新，执行短时右移与跳跃，检查非法指令拒绝、游戏线程应用计数、到期释放和 stop；当前脚本结果写入 `evidence/control-verification-v04.json`。它会实际操作角色，请在 0.4 隔离训练世界运行。这些为实时限时动作，不保证精确执行固定帧数。

2026-09-09 实机验收通过：右移 250ms 应用 15 帧，x 从 51214 到 51230.184；跳跃 250ms 应用 15 帧，y 从 6419.8164 降至 6328.129（向上约 92 像素）。两次动作均自动释放，主动 stop 生效，超长/负数时长及未知动作被拒绝。详细观测见 `control_verification.json`。

## step 与玩家检查点（0.3 历史行为，当前入口要求 0.4）

```python
from terra_env import TerraEnv

env = TerraEnv(frames=6)
env.checkpoint()  # 0.4：在通过门禁的隔离训练世界站稳后记录起点
observation, info = env.reset()
observation, reward, terminated, truncated, info = env.step("right")
env.close()
```

- `step` 支持 idle / left / right / jump / left_jump / right_jump，每次 1–120 个玩家控制更新帧。返回最后一个执行帧结束时的不可变观测。
- 底层 `step right 6` 返回 operationId；用 `result ID` 轮询 pending / completed / timeout 等状态。仅保留最后一个已结束操作结果，单客户端串行使用。
- `checkpoint` 与 `reset` 同样异步提交、由游戏线程完成。操作进行中拒绝其他动作；`stop` 可取消操作。
- Python 的 `step()` 返回五元组，**尚不是 Gymnasium Env**。reward 暂为向右位移/16，仅用于接口验证；无目标终止或时间截断机制，玩家死亡会使操作失败，尚未实现死亡复活重置。
- `checkpoint()` 要求角色存活、静止、未骑乘和未使用抓钩。记录位置、生命、魔力与朝向；`reset()` 恢复这些值、清零速度与跳跃状态。重置点被实心方块占据时拒绝重置，退出世界后检查点失效。
- reset **不恢复地图、敌人、弹幕、时间、随机数、背包、装备或全部玩家状态（如 Buff）**，不是完整环境快照。
- **世界不会在 step 之间冻结**。执行帧数精确，但网络等待期间世界继续演化；结果缓存保证完成时的观测不被后续帧覆盖。当前架构不能声称确定性训练环境。
- 自动验证：`python verify_steps.py`，随后保持游戏前台且角色站稳。该脚本会移动角色、恢复记录的生命和魔力，当前证据写入 `evidence/step-verification-v04.json`。

2026-09-09 0.3 实机验收通过：1、6、15 帧动作的 executedFrames 分别精确为 1、6、15；三次 reset 均恢复坐标 (51214, 6422)、生命、魔力和朝向，速度为零；重复读取已完成结果完全一致。并发操作拒绝及 stop 取消 pending 操作也已验证。证据见 `step_verification.json`。0.3 当时未做的 5 秒暂停超时分支，现已由上述 0.4 暂停与恢复证据补齐。
