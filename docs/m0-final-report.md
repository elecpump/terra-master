# M0 第三切片：最终包与 GPU 依赖验收

日期：2026-09-10。

## 最终 0.4 包

正常保存退出后重新构建并启动隔离实例，安装版编译打包 0 错误、0 警告。新的 instanceId 为 `d10875cce42e4de786a22f92e10d57a6`，已进入本地训练世界；源码与构建文件记录见 [最终运行清单](../evidence/runtime-final-v04.json)。此轮关闭了前一报告中“最终异常处理包尚未重载”的缺口。

对无效 purpose、破损 JSON、超出 Int32 范围的 schema、缺失 profileId、错误 saveRoot 五类 marker，服务器均拒绝 checkpoint/reset；每例恢复原始 marker 后重新允许，最终字节恢复：[异常门禁证据](../evidence/training-gate-final-v04.json)。

补做的 1/6/15 帧 step 全部完成，但末尾 reset 返回 `reset_location_or_player_blocked`，此轮主动基准明确记录为 failed，未计入成功吞吐：[失败证据](../evidence/benchmark-final-v04.json)。不移除碰撞/玩家状态检查来迁就当前地形。

## 运行和内存

新增 `measure_runtime.py`，只读采样桥接、实例、世界会话、tick 与进程内存；内存查询核对 PID 对应的可执行文件路径并记录进程创建时间，避免把别的进程当作游戏。该工具不执行动作或进程管理。

60.013 秒内采到 59 个样本，实例/世界连续、快照新鲜、tick 持续推进；峰值工作集 910,708,736 字节（约 869 MiB），peak private bytes 1,886,400,512 字节。19 个样本处于死亡状态，单独计数，不能声称训练场景稳定：[运行记录](../evidence/runtime-60s-final-v04.json)。后续 3 秒采样发现陈旧快照和 tick 停滞，正确返回 not_ready：[停滞记录](../evidence/runtime-stall-final-v04.json)。前者是加进程路径校验前的采样，后者同时验证了进程路径校验正常工作。

工具不记录实际前台窗口，所以以上不满足 30 分钟前后台稳定性门槛。自然世界的死亡、受击和 reset 拒绝说明长测前需要解决测试环境可靠性，不能靠更长运行时间掩盖。

## CPU / GPU 依赖

在本项目 `.venv` 安装并锁定：PyTorch 2.8.0+cu128、Gymnasium 1.2.3、Stable-Baselines3 2.7.1、NumPy 2.2.6。完整传递依赖见 [Windows Python 3.11 锁文件](../requirements-training-win-py311.lock)，核心标准库工具仍保留独立的空第三方依赖锁。GPU wheel 从官方源下载，安装前验证 SHA-256 `34c55443aafd31046a7963b63d30bc3b628ee4a704f826796c865fdfd05bb596`。`pip check` 无依赖冲突。

GPU 为 NVIDIA GeForce RTX 5090 D v2，驱动 596.49；实测 CUDA runtime 12.8、compute capability 12.0，安装包包含 sm_120。CPU 和 CUDA 两条 smoke 都通过矩阵乘法/反向传播有限值检查、CartPole 环境 checker、256 步 PPO 更新、模型参数和动作保存加载一致性检查。CUDA 测试的实际 tensor 与 policy 设备均为 `cuda:0`，没有回退 CPU。

- [CPU smoke](../evidence/training-smoke-cpu.json)：同一 CUDA 构建下使用 CPU，256 步，保存加载参数相同。
- [CUDA smoke](../evidence/training-smoke-cuda.json)：256 步，peak allocated CUDA memory 18,716,160 字节，保存加载参数相同。

这只是依赖兼容性测试，不是 Terraria 模型训练，也不是 CPU/GPU 速度对比。SB3 对 GPU 上的小 MLP 给出低利用率提示；后续训练设备选择仍需按实际网络与吞吐测量。复跑方式见 [依赖 smoke 指南](dependency-smoke.md)。

## 验证与下一入口

17 项离线测试通过；新增测试覆盖运行连续性、死亡单独计数、陈旧快照、重启、世界切换、进程身份变化、采样不足及 marker 用例不修改原始对象。

M0 的训练栈兼容 smoke、内存测量与最终异常门禁缺口已关闭；30 分钟前后台稳定性仍未完成。下一切片应处理测试位置/玩家状态可靠性和失焦停滞，再推进长测与 D1 同步实验。M2 完整场景 reset 和死亡 terminated 语义仍未实现，禁止开始 Terraria 长时间训练。
