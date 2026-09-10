# 项目上下文

更新：2026-09-10。

用户长期目标是自主探索并最终通关泰拉瑞亚。设计文件：[ARCHITECTURE.md](ARCHITECTURE.md)、[EXECUTION_PLAN.md](EXECUTION_PLAN.md)。它们是目标与计划，不是功能完成清单。

当前工作区 `D:\code\terra-master`，游戏安装 `D:\software\Steam\steamapps\common\tModLoader`，源码参考 `D:\code\tModLoader`。已安装稳定版与源码分支不一致，构建以安装版自带编译器为准。

已完成桥接原型 0.3：TCP 观测、限时左右/跳跃、按动作帧数 step、玩家部分检查点重置；实机证据在 README 和两个 verification JSON 文件。没有模型、标准 Gym 环境、完整场景 reset 或整个世界同步步进。

已采用的设计方向：

- 分层目标规划、世界记忆与独立技能；先移动导航，之后探索采集和战斗，最终串联进度。
- 结构化局部观测起步；不要把全地图内部真值当作自主探索策略的输入。
- Training 与 Campaign 分离；正式通关不允许训练重置、传送或直接改资源。
- 先时间/协议/场景可靠性，再规模化 PPO；同步模式、多开、无界面与加速均须实证。
- 当前硬件有 24 逻辑处理器、约 47.5 GiB RAM 和 RTX 5090 D v2；吞吐和 Python CUDA 兼容性尚未测量。

M0 首个切片已实现：Git 初始化与忽略规则、Python 3.11.15 专用虚拟环境和标准库依赖锁、安装版运行清单及哈希、只读 doctor/bench。2026-09-10 实机短测 59.93 tick/s，6 项离线测试通过，见 [baseline-report.md](baseline-report.md)。Git 原型基线已提交为 `e97883b`；训练依赖 smoke、隔离 profile、30 分钟稳定性和暂停超时验收仍未完成。只读诊断通过不代表训练就绪。

下一开发切片：补齐 M0 的隔离测试环境和主动 step/reset 吞吐、暂停验收，再以 2 天时间盒跑同步推进实验（D1），用其结论重排协议 v2 投入。不要仅因已有五元组接口就开始长时间训练。详细任务级计划见 [EXECUTION_PLAN.md](EXECUTION_PLAN.md)。
