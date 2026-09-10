# 0.4.1：检查点一致性与训练后台运行

日期：2026-09-10。状态：安装版编译、打包通过，23 项 Python 离线测试通过；已安装并进入训练世界，平地短基准、碰撞拒绝和系统确认的后台短时连续性通过。后台补丁分支的因果对照、手动暂停回归和长稳尚未验收。构建清单见 [runtime-build-v041.json](../evidence/runtime-build-v041.json)，当前运行清单已更新为训练目录的 0.4.1。

用户明确授权强制关闭后，核对训练目录启动参数与可执行文件，结束旧实例并安装新版。新 instanceId 为 `aeebe8a4aa5c41878aa0803281a6a47f`，PID 为 20760；实际加载 0.4.1，`backgroundHookInstalled` 与 `backgroundEnabled` 均为 true。

## 本轮实测

后续补验关闭了两个观测缺口：

- [碰撞拒绝](../evidence/checkpoint-collision-v041.json)：存活角色处于 (33479.402, 3565.4023)，runtime 报告实心碰撞；服务器实际返回 `checkpoint_location_solid_collision`，随后 reset 被 `Record checkpoint first` 拒绝。证明不接受该碰撞位置，不将此次位置视作旧失败位置的精确复现。
- [系统焦点后台采样](../evidence/runtime-os-background-v041.json)：10.182 秒、11 个样本全部由 Windows 前台进程查询确认游戏在后台，tick 连续推进，无陈旧快照；8 个样本角色死亡，仍不代表训练场景就绪。FNA 的 IsActive 同时全部为 true，说明它在该实例中不能代表真实前台窗口。未定位 SDL/FNA 未更新该字段的底层原因。

`measure_runtime.py` 报告 schema 2 使用 Windows `GetForegroundWindow` 和 `GetWindowThreadProcessId` 独立比较游戏 PID；无句柄或查询失败记 unknown，不把它当作后台。`focusVerified`、focused/unfocused 计数来自系统信息，`engineFocusMismatchSamples` 保留与 FNA 的差异。旧报告保留原语义，不能把其中的 `focusVerified=true` 追认为系统焦点验证。新增回归覆盖引擎/系统焦点不一致及信息缺失；23 项测试通过。

以下为此前探测记录，保留失败与局限：

- [平地基准](../evidence/benchmark-v041.json)：checkpoint、预检 reset、1/6/15 帧 idle 及末尾 reset 均通过。
- [前台采样](../evidence/runtime-focused-v041.json)：3 秒持续推进，4 个 focused=true 样本。
- 用户切回聊天后两轮采样仍全为 FNA focused=true；记录见 [切换后采样](../evidence/runtime-unfocused-v041.json)。这只证明当时持续更新，不能证明失焦分支生效。首次工具切换记录 [runtime-background-v041.json](../evidence/runtime-background-v041.json) 同样全为 focused=true，文件名不代表验收结论。
- [开关对照](../evidence/background-toggle-v041.json)：关闭和开启分别采样，开关生效，但 focused 均为 true、tick 均继续推进；原 marker 字节已恢复。不将该对照判为后台验收通过。
- [检查点探测](../evidence/checkpoint-probe-v041.json)：移动后保存被 `checkpoint_player_moving` 拒绝，runtime 显示旧检查点已失效；没有复现 `checkpoint_location_solid_collision`，整轮探测保留 failed 状态。

自然世界仍发生死亡；没有进行长时间训练。碰撞拒绝已由后续补验通过；后台补丁分支的因果对照和手动暂停回归继续列为待验证。

## 原因与修复

0.4 的 checkpoint 不检查碰撞，reset 却调用 `Collision.SolidCollision`，因此保存成功不能保证当时的位置满足恢复条件。0.4.1 的两个操作共用 `RestoreBlocker`：骑乘、抓钩、实心碰撞分别拒绝。checkpoint 还要求静止；失败的 checkpoint 请求执行后清除旧检查点，避免误用旧起点。reset 仍重新检查当前地形和玩家状态，不移除碰撞保护，不承诺地图变化后仍可恢复。斜坡等被当前碰撞 API 判定为占据的位置保守拒绝保存，不自动挪动坐标。

终止状态分别为 `checkpoint_player_mounted`、`checkpoint_player_grappling`、`checkpoint_location_solid_collision`、`checkpoint_player_moving`；reset 对应前三项的 `reset_` 前缀。现有死亡与门禁拒绝仍保留。此前失败记录的复合错误不能追溯区分碰撞、骑乘和抓钩。

用安装目录自带 Mono.Cecil 读取实际 tModLoader.dll 的 IL，确认 `Main.DoUpdate` 在 `hasFocus == false && netMode == 0` 时设置 `gamePaused = true` 并返回。该分支在 `CanPauseGame()` 之前，关闭 AutoPause 无法解除此失焦暂停。安装版 focus 读取位于 IL_07eb，返回位于 IL_0858；偏移仅用于该安装版诊断，不作补丁匹配依据。

0.4.1 在 `IL_Main.DoUpdate` 中仅扩展该焦点判断：只有有效本地训练角色/世界、有效 marker、`runInBackground: true`、非菜单且单人时才允许继续更新。必须唯一匹配 `hasFocus` 读取及后续条件跳转，否则后台功能保持关闭并写日志。保留真实焦点字段、输入焦点和 `CanPauseGame()` 手动暂停行为；不修改全局配置，不声称同步或加速。

## 配置与诊断

已有训练目录的 `terramaster-training.json` 可加入 `"runInBackground": true`。默认缺失、false 或非布尔 true 均不启用。外层 DoUpdate 每秒按墙钟刷新门禁，暂停时也可撤销开关；世界退出立即清除许可。恢复操作仍在执行前重新核验门禁。

新增只读命令：

```powershell
.\.venv\Scripts\python.exe bridge_client.py runtime
.\.venv\Scripts\python.exe measure_runtime.py --seconds 60 --output runs/v041/runtime.json
```

`runtime` 返回游戏线程生成的独立快照：实例/世界会话、采样时间、focused、paused、menu、autoPause、backgroundHookInstalled、backgroundEnabled、checkpointAvailable、currentPositionBlocker、checkpointBlocker。这些是诊断数据，不是策略输入。世界暂停时外层更新仍可刷新该快照；仍必须校验时间和身份，进程卡死时也可能陈旧。

protocol 仍为 1，正式观测 schema 仍为 2。客户端明确兼容 0.4 和 0.4.1，未知版本继续拒绝。只读运行采样对 0.4.1 增加 runtime 新鲜度和会话核对；新版报告用独立的系统焦点计数。`focusVerified` 仅代表逐样本有有效系统焦点信息，不代表覆盖足够时长；`trainingReady` 仍为 false。

## 重载后的验收

1. 正常保存退出并关闭训练实例；将已构建包安装到训练目录，开启该目录后台开关，启动后核对 ping 为 0.4.1、instanceId 改变，runtime 的 hookInstalled/enabled 为 true。
2. 在安全平地站稳，短基准验证 checkpoint、预检 reset、1/6/15 帧 step 和最终 reset。保留新文件，不覆盖 0.4 历史证据。
3. 前台与后台分别采样，要求 focused 字段确有变化、tick 持续推进且快照新鲜。后台撤销开关应恢复失焦暂停；重新开启应恢复推进。手动暂停时保留 5 秒零帧超时及恢复语义。
4. 使用新诊断定位拒绝位置，确认碰撞起点在 checkpoint 阶段被拒绝；骑乘/抓钩分别返回对应状态。不能用 Python 模拟结果宣称真实游戏碰撞已验收。

上述平地与碰撞检查、后台短时连续性已完成；开关因果对照、手动暂停回归及 30 分钟长稳尚未完成。自然世界刷怪与死亡仍存在，此补丁不提供无敌、完整场景 reset、死亡复活接口或训练管线。
