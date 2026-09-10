# 后台运行与输入修复：0.4.3

日期：2026-09-10。当前已加载 0.4.3；编译打包 0 错误、0 警告，26 项离线测试通过。当前实例 `0a1d23a1460e4de59a20b8b2ab811fb7`，构建和安装版清单见 [runtime-build-v043.json](../evidence/runtime-build-v043.json)。

## 本轮定位与修改

0.4.1 的手动暂停回归已通过：[暂停零帧超时](../evidence/paused-timeout-v041.json)、[恢复后旧结果不变及新 6 帧 step](../evidence/timeout-recovery-v041.json)。背景开关开启不妨碍手动暂停。

FNA IsActive 会与 Windows 前台状态不一致。0.4.2 为有效训练世界使用 Windows 前台进程判断运行焦点，查询不可用时回退引擎焦点；不改变普通存档的失焦行为。后台开启仍绕过失焦返回，关闭则遵循真实焦点。runtime 增加 osFocused，保留 focused 作为引擎值。原版输入焦点字段不被伪造。

[0.4.2 后台开关对照](../evidence/background-gate-v042.json) 已通过：关闭时世界 tick 停止，开启后继续，marker 原始字节恢复。但 [0.4.2 主动基准](../evidence/benchmark-v042.json) 的首个 step 为 0 帧超时，不能据 tick 推进宣称后台动作可用。

安装版 `Player.Update` 在 ResetControls 后检查 Main.hasFocus，失焦时跳过包含 PlayerLoader.SetControls 的输入分支。0.4.3 在该分支前补充桥接输入，仅当 Main.hasFocus=false、后台许可有效且为本地玩家时调用 ApplyControls；前台仍使用原有 ModPlayer.SetControls，不重复计数，不启用后台物理键盘输入。两个 IL 钩子均须唯一匹配且安装成功，才允许后台运行。

## 验证入口与结果

```powershell
.\.venv\Scripts\python.exe verify_background.py --profile profiles/training-m0/terramaster-training.json --output runs/v043/background.json
```

此脚本要求 0.4.3、有效且已开启后台的训练 marker、非菜单/非手动暂停，以及客户端和服务端两次 Windows 焦点查询均为 false。关闭和开启后台开关各取两次快照，核验暂停标记和 tick；异常时也恢复 marker。不会操作角色或编辑存档。三个离线测试覆盖正常对照、断线恢复 marker、前台拒绝修改；总计 26 项测试通过。

0.4.3 前台 1/6/15 帧 idle 及前后 reset 已通过，见 [前台基准](../evidence/benchmark-focused-v043.json)。两个钩子均报告已安装。

后续 0.4.3 后台补验已通过：[后台开关对照](../evidence/background-gate-v043.json) 验证关闭后暂停、开启后推进，marker 原始字节恢复。[后台移动与恢复](../evidence/background-movement-v043.json) 验证右移 1/6/15 帧分别精确执行对应帧数且 x 增大，初始试恢复及每次动作后的 reset 均恢复位置、生命、魔力、朝向和零速度。各操作前后记录引擎 focused=false、服务端 osFocused=false，客户端 Windows 查询也确认失焦。该结果关闭 0.4.2 所暴露的后台 step 零帧超时缺口；不代表 30 分钟长稳、所有动作或无死亡训练场景已经验收。

此次重启使用安装版 `-skipselect TM-Training-M0:TM-Training-M0` 自动选择此前已确认的训练角色和世界，进入后再次核验训练门禁。该参数在名称不匹配时会回退列表首项，因此不可未经核验推广到其他 profile；普通启动脚本仍保留人工选择。

30 分钟前后台长稳及消除自然世界死亡干扰仍未完成，没有启动 Terraria 训练。
