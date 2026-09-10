# M0 第二切片验收报告

日期：2026-09-10。范围：独立存档、桥接 0.4 训练门禁、主动基准、暂停与恢复。

## 实现

`training_profile.py` 新建项目内 profile 和训练 marker；`start_training.ps1` 调用安装版 launcher，使用已核对的 `-tmlsavedirectory` 参数。新角色与世界位于 `profiles/training-m0/Players`、`Worlds`，均由游戏正常创建，没有复制或编辑普通存档。launcher 记录不授予脚本对其他进程的管理权限。

0.4 增加训练 marker、角色/世界名称、本地存档路径与云端标记检查；checkpoint/reset 的游戏线程执行路径再次验证门禁，失效即清除检查点。普通移动仍可用于 Campaign。协议保持 1，观测 schema 为 2，增加 instanceId/worldSession 检测，但不宣称已完成协议 v2 的幂等或会话隔离。

## 编译、加载与实测

- 安装版 Terraria 1.4.4.9 / tModLoader 2026.07.3.0 / .NET 8.0.0；0.4 编译和打包均 0 错误、0 警告。隔离实例 ping 确认加载 0.4，doctor 通过：[诊断记录](../evidence/doctor-v04.json)。
- 30 个 idle transition，1/6/15 帧各 10 次，合计 220 个执行帧。含每次预检、轮询和末尾 reset，共 5.090833 秒，吞吐 5.892945 transition/s。混合 step 延迟 p50 116.28 ms / p95 280.25 ms，reset 30.81 ms：[完整基准](../evidence/benchmark-steps-v04.json)。这不是固定 6 帧动作的训练吞吐，不据此直接预估百万样本。

| 请求帧数 | 样本数 | step p50 (ms) | step p95 (ms) |
|---|---:|---:|---:|
| 1 | 10 | 30.96 | 48.23 |
| 6 | 10 | 116.28 | 133.12 |
| 15 | 10 | 268.72 | 282.43 |

- 右移、跳跃、到期释放、stop 通过：[控制证据](../evidence/control-verification-v04.json)。1/6/15 帧移动、三次玩家检查点恢复与结果缓存不可变通过：[step 证据](../evidence/step-verification-v04.json)。
- 临时撤销训练 marker 后服务器拒绝 checkpoint/reset；finally 恢复原始 marker 后训练状态恢复：[门禁证据](../evidence/training-gate-v04.json)。没有在用户普通世界发起破坏性测试，云存档和路径重定向分支尚未实机测试。
- 开启自动暂停：一秒内 tick 不变，idle 1 帧约 5 秒后 timeout、执行 0 帧，整个期间 tick 不变：[暂停证据](../evidence/paused-timeout-v04.json)。恢复后旧结果仍为相同 timeout，新 6 帧 idle 成功：[恢复证据](../evidence/timeout-recovery-v04.json)。
- `python -m unittest discover -s tests -v`：14 项通过，包含错误 profile、普通状态、外部持续控制、陈旧快照、死亡、实例重启、世界会话切换、断线不重试或全局取消、帧数与吞吐、暂停零帧、目录不覆盖。

## 构建产物边界

本次实机使用的包见 [运行清单](../runtime-manifest.json)。随后补充了损坏 marker 数字转换抛出 FormatException 时的拒绝处理，使用独立编译目录构建通过，未覆盖加载中包；该包哈希见 [最终编译清单](../evidence/runtime-build-v04.json)。两个包均为 0.4，但哈希不同，源码/包对应关系不能仅靠版本号推断。最终异常分支仅有编译证据，下一次正常保存退出后应构建到 training-m0 并重载验证，不能把本次 smoke 描述为最终包所有分支均已验证。

## 仍未完成

尚未进行 30 分钟前后台稳定性、游戏内存采样、Gymnasium/SB3/PyTorch smoke 和 D1 同步推进实验。独立自然世界仍会刷怪：恢复后观测到角色生命从 100 降到 66，说明仅有目录隔离不足以训练。死亡仍是操作异常，reset 仅恢复部分玩家状态，M2 受控场景和合法死亡终止 transition 仍是训练前门槛。

本轮桌面鼠标操作可用，但游戏未可靠响应注入的 Escape 和名称输入；用户协助了保存退出、存档命名及暂停/恢复。不能宣称完全无人值守。
