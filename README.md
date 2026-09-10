# TerraMaster：游戏接入原型

项目设计入口：[完整架构](doc/ARCHITECTURE.md) · [执行计划](doc/EXECUTION_PLAN.md) · [项目上下文](doc/PROJECT_CONTEXT.md)。长期目标为自主探索与最终通关；以下内容记录当前已实现原型。

目前实现本机 TCP 观测、短时动作控制、按帧计数的 step 与玩家检查点重置（TerraBridge 0.3）。完整世界仍实时运行，尚未实现完整场景重置或训练算法。

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

## 动作验收

运行 `python verify_controls.py` 后切回游戏。脚本等待实时更新，执行短时右移与跳跃，检查非法指令拒绝、游戏线程应用计数、到期释放和 stop；结果写入 `control_verification.json`。它会实际操作角色，请在测试世界运行。这些为实时限时动作，不保证精确执行固定帧数。

2026-09-09 实机验收通过：右移 250ms 应用 15 帧，x 从 51214 到 51230.184；跳跃 250ms 应用 15 帧，y 从 6419.8164 降至 6328.129（向上约 92 像素）。两次动作均自动释放，主动 stop 生效，超长/负数时长及未知动作被拒绝。详细观测见 `control_verification.json`。

## step 与玩家检查点（0.3）

```python
from terra_env import TerraEnv

env = TerraEnv(frames=6)
env.checkpoint()  # 在测试世界站稳后记录起点
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
- 自动验证：`python verify_steps.py`，随后保持游戏前台且角色站稳。该脚本会移动角色、恢复记录的生命和魔力，证据写入 `step_verification.json`。

2026-09-09 0.3 实机验收通过：1、6、15 帧动作的 executedFrames 分别精确为 1、6、15；三次 reset 均恢复坐标 (51214, 6422)、生命、魔力和朝向，速度为零；重复读取已完成结果完全一致。并发操作拒绝及 stop 取消 pending 操作也已验证。证据见 `step_verification.json`。5 秒超时分支尚未做实机暂停验收。
