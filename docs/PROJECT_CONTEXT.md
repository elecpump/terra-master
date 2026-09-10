# 项目上下文

更新：2026-09-10。

用户长期目标是自主探索并最终通关泰拉瑞亚。设计文件：[ARCHITECTURE.md](ARCHITECTURE.md)、[EXECUTION_PLAN.md](EXECUTION_PLAN.md)。它们是目标与计划，不是功能完成清单。

当前工作区 `D:\code\terra-master`，游戏安装 `D:\software\Steam\steamapps\common\tModLoader`，源码参考 `D:\code\tModLoader`。已安装稳定版与源码分支不一致，构建以安装版自带编译器为准。

已完成桥接原型 0.4（保留 0.3 历史证据）：TCP 观测、限时左右/跳跃、按动作帧数 step、玩家部分检查点重置；新增隔离训练存档门禁和主动基准；实机证据在 README 和 evidence/。没有 Terraria 模型、标准 Gym 环境、完整场景 reset 或整个世界同步步进。

已采用的设计方向：

- 分层目标规划、世界记忆与独立技能；先移动导航，之后探索采集和战斗，最终串联进度。
- 结构化局部观测起步；不要把全地图内部真值当作自主探索策略的输入。
- Training 与 Campaign 分离；正式通关不允许训练重置、传送或直接改资源。
- 先时间/协议/场景可靠性，再规模化 PPO；同步模式、多开、无界面与加速均须实证。
- 当前硬件有 24 逻辑处理器、约 47.5 GiB RAM 和 RTX 5090 D v2；实测混合帧吞吐 5.89 transition/s；PyTorch 2.8.0+cu128 在该 GPU 的矩阵反向传播与短 PPO smoke 已通过，不代表游戏 tick 加速。

M0 首个切片已实现：Git 初始化与忽略规则、Python 3.11.15 专用虚拟环境和标准库依赖锁、安装版运行清单及哈希、只读 doctor/bench。2026-09-10 实机短测 59.93 tick/s，6 项离线测试通过，见 [baseline-report.md](baseline-report.md)。Git 原型基线已提交为 `e97883b`；训练依赖 smoke、隔离 profile、30 分钟稳定性和暂停超时验收仍未完成。只读诊断通过不代表训练就绪。

M0 第二切片已完成隔离目录和训练门禁、混合帧主动基准（5.89 transition/s）、控制与 reset 回归、暂停零帧超时及恢复验收；14 项离线测试通过，见 [m0-active-report.md](m0-active-report.md)。当时损坏 marker 数字异常分支只完成独立构建；后续第三切片已重载并通过异常门禁验收。

M0 第三切片完成最终包五类 marker 异常验收、只读内存采样、Windows Python 3.11 GPU 依赖锁以及 CPU/CUDA 256 步 CartPole smoke；17 项离线测试通过。60 秒采样中有 19 个死亡样本，补做主动基准的 reset 被拒绝，后续采样发现停滞，均保留失败证据，见 [m0-final-report.md](m0-final-report.md)。

后续客户端修复：主动基准在采样前立即试恢复检查点，拒绝不可恢复或恢复不一致的起点；初始预检和两次 reset 纳入预算/总计时，报告 schema 2。20 项离线测试通过；当前实机死亡预检拒绝，未提交动作。服务端 checkpoint/reset 判断差异仍待修复，不能将客户端提前失败视为完整解决。

用户保持游戏前台后，同一实例 tick 恢复推进、角色正常复活；平地位置 (33566, 3574) 的三次 1/6/15 帧 idle 及前后两次 reset 通过，证据为 `evidence/benchmark-foreground-v04.json`。旧位置的 reset 拒绝原因仍未定位；没有独立焦点测量或前后台长稳结论。

0.4.1 已实现服务端共用恢复校验、分类拒绝原因、有效训练 marker 显式后台开关和外层更新的 runtime 诊断；安装版编译打包通过，22 项 Python 测试通过。用户授权强制关闭后已重载 0.4.1，新实例 aeebe8a4aa5c41878aa0803281a6a47f，平地短基准通过。失焦暂停路径已定位，但用户切回后 FNA 焦点字段仍为 true，开关对照两边均继续更新，不能判后台分支通过；碰撞拒绝也未复现。详见 [修复说明](runtime-fixes-v041.md)。

后续实测：碰撞位置已被 checkpoint_location_solid_collision 拒绝，后续 reset 无可用检查点；Windows 前台进程独立确认游戏在后台连续运行 10 秒、11 样本均推进。FNA IsActive 全为 true，监测改用系统焦点，保留引擎差异计数，23 项测试通过。背景补丁的因果对照仍未完成，不能把后台运行现象归因于补丁；采样含死亡，尚未训练就绪。

本轮补验：0.4.1 手动暂停零帧超时及恢复通过；0.4.2 改用系统焦点，后台开关对照通过，但后台 step 0 帧超时，定位为原版失焦跳过 SetControls。0.4.3 已补充后台桥接输入并重载，两个钩子安装成功，前台短 step/reset 通过，26 项离线测试通过。后台主动验收仍待完成。见 [本轮修复记录](runtime-fixes-v043.md)。

0.4.3 后台补验通过：后台开关控制暂停/推进，marker 原字节恢复；真实失焦下右移 1/6/15 帧均精确执行且产生位移，初始及每步后的 reset 通过。证据在 evidence/background-gate-v043.json 与 evidence/background-movement-v043.json；已关闭后台 step 零帧超时缺口。

下一入口：完成 M0 的 30 分钟前后台稳定性，处理自然世界死亡对测试的干扰，然后以 2 天时间盒跑同步推进实验（D1）。不要仅因已有五元组接口就开始长时间训练。详细任务级计划见 [EXECUTION_PLAN.md](EXECUTION_PLAN.md)。
