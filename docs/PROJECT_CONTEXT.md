# 项目上下文

更新：2026-09-09。

用户长期目标是自主探索并最终通关泰拉瑞亚。设计文件：[ARCHITECTURE.md](ARCHITECTURE.md)、[EXECUTION_PLAN.md](EXECUTION_PLAN.md)。它们是目标与计划，不是功能完成清单。

当前工作区 `D:\code\terra-master`，游戏安装 `D:\software\Steam\steamapps\common\tModLoader`，源码参考 `D:\code\tModLoader`。已安装稳定版与源码分支不一致，构建以安装版自带编译器为准。

已完成桥接原型 0.3：TCP 观测、限时左右/跳跃、按动作帧数 step、玩家部分检查点重置；实机证据在 README 和两个 verification JSON 文件。没有模型、标准 Gym 环境、完整场景 reset 或整个世界同步步进。

已采用的设计方向：

- 分层目标规划、世界记忆与独立技能；先移动导航，之后探索采集和战斗，最终串联进度。
- 结构化局部观测起步；不要把全地图内部真值当作自主探索策略的输入。
- Training 与 Campaign 分离；正式通关不允许训练重置、传送或直接改资源。
- 先时间/协议/场景可靠性，再规模化 PPO；同步模式、多开、无界面与加速均须实证。
- 当前硬件有 24 逻辑处理器、约 47.5 GiB RAM 和 RTX 5090 D v2；吞吐和 Python CUDA 兼容性尚未测量。

下一开发切片：先修复 `verify_controls.py` 版本检查（已对齐 0.3）、建立 Git 与运行版本基线、补 doctor/bench，再以 2 天时间盒跑同步推进实验（D1），用其结论重排协议 v2 投入。不要仅因已有五元组接口就开始长时间训练。详细任务级计划见 [EXECUTION_PLAN.md](EXECUTION_PLAN.md)。
