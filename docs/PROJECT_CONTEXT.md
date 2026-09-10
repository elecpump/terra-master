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

下一开发切片：先处理测试位置/玩家状态可靠性与失焦停滞，补齐 M0 的 30 分钟前后台稳定性，再以 2 天时间盒跑同步推进实验（D1），用其结论重排协议 v2 投入。不要仅因已有五元组接口就开始长时间训练。详细任务级计划见 [EXECUTION_PLAN.md](EXECUTION_PLAN.md)。
