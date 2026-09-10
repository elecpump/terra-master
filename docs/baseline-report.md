# M0 首个切片验收

日期：2026-09-10。范围：版本清单、项目 Python 环境、只读诊断和被动性能采样。

## 已实现与证据

- Git 初始化；`.gitignore` 排除运行数据和存档，原型基线提交为 `e97883b`。提交身份已按用户提供的信息配置在本仓库。
- Python 3.11.15 项目 `.venv`，`requirements.lock` 声明无第三方运行依赖。
- [运行清单](../runtime-manifest.json) 采样得到 Terraria 1.4.4.9、tModLoader 2026.07.3.0 stable、安装版 .NET 8.0.0，并记录程序集、模组包和源文件 SHA-256。此次没有修改或重新构建 C#。
- `doctor` 实机通过，运行中的桥接返回 TerraBridge 0.3 / protocol 1；快照新鲜且 tick 推进。[诊断原始证据](../evidence/m0-doctor.json)。
- `bench --seconds 5` 共 21 个样本，实际采样跨度 5.0223395 秒，tick 增加 301，约 59.9322 tick/s；观测请求 p50 0.4004 ms、p95 23.2405 ms，使用高分辨率单调计时。角色坐标维持 (51214, 6422)，life 100，control.active=false。[采样原始证据](../evidence/m0-bench.json)。
- `python -m unittest discover -s tests -v`：6 项通过，覆盖版本拒绝、离线、陈旧快照、时钟偏差、暂停、菜单、世界/帧号不连续、只读命令范围和断线保留样本。

## 未验证与下一入口

这次短测不覆盖 30 分钟前后台稳定性，协议不暴露窗口焦点。tick 推进不证明 NPC/弹幕/时间协同推进。没有同步推进实验结论，也不能用观测请求延迟推导 transition/s。

安装清单用于检测磁盘文件漂移，协议 1 无法回报加载包哈希；源码和安装包对应关系仍未认证。Git 原型基线已完成本地提交，远程发布状态以实际推送结果为准。当前没有隔离训练 profile、训练标记或训练依赖验证，doctor 的 `training_ready=false` 是刻意保留的边界。

下一切片补齐独立训练环境、主动 step/reset 性能采样、暂停 5 秒超时验收和 30 分钟稳定性，然后进入 D1 同步推进实验。M0 整体仍处于进行中。
