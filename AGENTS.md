# TerraMaster Agent Instructions

## 目标与文档入口

本项目长期目标是让智能体在泰拉瑞亚中自主探索、采集、制作、战斗并最终通关。采用目标规划、世界记忆与可组合技能的分层架构。

开始非平凡任务时先读取：

1. [PROJECT_CONTEXT.md](doc/PROJECT_CONTEXT.md)：目标、已确认决策和当前切片。
2. [README.md](README.md)：已实现能力、运行命令与实机证据。
3. 根据任务读取 [ARCHITECTURE.md](doc/ARCHITECTURE.md) 和 [EXECUTION_PLAN.md](doc/EXECUTION_PLAN.md) 的相关章节。

架构和计划中的目标能力不等于已经实现。以当前代码、运行版本和实测结果核对事实。用户当前明确指令优先；范围变化时同步更新相关项目文档，不把旧计划当作拒绝新需求的理由。

## CodeGraph

<!-- CODEGRAPH_START -->
In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
<!-- CODEGRAPH_END -->

没有索引时优先使用 `rg` / `rg --files` 定位代码。不要自行建立索引。对参考源码仓库单独检查其索引和指令。

## 工作区与版本

- 项目工作区：`D:\code\terra-master`。
- tModLoader 安装默认位置：`D:\software\Steam\steamapps\common\tModLoader`。
- 参考源码：`D:\code\tModLoader`，不是本项目，也不是默认构建依赖。
- 2026-09-09 已验证环境：Terraria 1.4.4.9、tModLoader 2026.07.3.0、.NET 8。此处为历史基线，涉及运行时变更前重新核对。
- 参考源码曾使用 .NET 10，领先已安装稳定版。API、Hook 和构建以实际安装版本为准；不要擅自切换或修改参考仓库分支。
- 使用项目自己的 Python 虚拟环境与依赖锁（建立后）；不要向无关项目的环境安装依赖。

## 实现约定

- 每次交付一个可验证的纵向功能切片；保留可工作的原型入口，按阶段迁移，不提前创建大量空模块。
- C# 游戏对象只能在游戏线程访问和修改。网络线程校验请求、提交操作并读取不可变结果，不直接操作 Player、NPC、世界或存档。
- 网络等待不能阻塞游戏线程。输入必须具有有界帧数或截止时间；取消、卸载、退出世界和连接恢复需要明确处理。
- 协议、模组版本、观测/动作 schema、场景、奖励与模型版本分别管理。接口变更同步客户端、验证脚本和文档；版本不兼容应明确报错。
- step 结果是完成帧或终止帧的快照，不能用稍后的 observe 冒充。区分请求帧数、执行帧数、世界经过帧数、请求空档与墙钟耗时。
- 精确动作帧数不等于整个世界同步推进。同步、无界面、多实例、加速和确定性都须有对应实测证据才能宣称支持。
- 使用显式的请求、会话与回合边界；重试不能重复执行动作，旧请求不能取消或污染新回合。
- 区分任务成功/死亡、有效回合时间截断和基础设施故障；不能用死亡惩罚掩盖断线或 reset 失败。
- 观测明确单位、dtype、shape、可见性和 unknown 掩码。诊断用全局状态不得泄漏到正式探索策略输入。

## 游戏与存档

- Training 与 Campaign 分离。训练可使用明确声明的场景重置；正式通关只能使用正常游戏行动，不得调用训练传送、回血、发物品或改进度能力。
- 场景生成、破坏性地图编辑、完整重置和压力测试使用带训练标记的专用角色与世界。不要把用户普通存档默认为可重建训练场。
- 重置必须列明范围并核验结果；恢复坐标/生命不等于恢复完整玩家、地图、实体或随机数状态。
- 模组被游戏锁住时，不强杀进程或绕过锁覆盖文件；说明需正常保存退出或卸载模组，让用户完成必要界面操作后继续。
- 仅自动管理本任务启动、登记并核对过身份的进程。不得用宽泛进程名批量结束游戏或 dotnet。
- 日志读取优先选明确的 `client.log` 和相关行；不要批量输出可能包含环境变量或凭据的启动日志。

## 构建与验证

在项目根目录构建：

```powershell
.\build_bridge.ps1
# 可覆盖安装路径：
.\build_bridge.ps1 -TmlInstallPath '实际安装目录'
```

现有 Python 入口：

```powershell
python bridge_client.py ping
python bridge_client.py observe
python verify_controls.py
python verify_steps.py
```

- `verify_controls.py` 和 `verify_steps.py` 会实际操作角色；后者还会恢复检查点。运行前核对脚本版本要求与测试世界状态，不把它们当作只读检查。
- 当前控制验证脚本曾限定 0.2、step 验证脚本限定 0.3；迁移时按实际协议更新检查，不简单删除版本校验。
- 按变更选择验证：协议做解析/幂等/取消测试，C# 改动做安装版编译和实机 smoke，场景改动做 reset/死亡验收，模型改动做固定测试集评估。
- “编译成功”“打包成功”“游戏加载成功”“实机行为正确”分别记录；不能以第一项替代其余项。
- 纯文档变更核对链接、命令和事实即可，不为此启动游戏或训练。
- 验证输出记录版本和状态，保留小型可追溯证据。大日志、存档、模型及运行数据放入隔离目录并按版本管理规则排除。
- 检查通过后不无依据扩大或重复测试；发现新风险才补充验证。

## 训练与评估

- 先完成环境、回合重置和基线，再进行长时间训练。PPO 是首个候选基线，不是必须用于全部层级的唯一算法。
- 每次正式实验保存配置、种子、版本、归一化状态和模型清单；分离训练/验证/测试场景。
- 同时报告成功率、死亡率、游戏时长、墙钟耗时和样本吞吐，不只看 reward 或挑选最佳一次演示。
- 采样耗时用实际 transition/s 估算；不要仅凭显卡性能承诺训练速度、多开数量或通关日期。
- 长时间或大规模试验先写明样本、时间和资源预算，在用户已授权范围内执行。

## 协作与收尾

- 默认用中文沟通；进度更新说明已确认事实、剩余不确定性和下一步。
- 已授权且必要的可逆工作直接完成，不反复请求确认。需要用户操作时解释具体原因，例如游戏锁住模组或缺少可用界面控制工具。
- 不默认创建额外任务、代理、自动化或外部 issue；用户明确要求或适用指令要求时再使用。
- 本次完成内容更新 README 的能力/验证部分；阶段或架构改变再更新 PROJECT_CONTEXT、ARCHITECTURE、EXECUTION_PLAN，保持“计划”和“实测”分开。
- 最终报告具体改动、已运行验证、仍未验证的限制，并链接项目文件。
