---
inclusion: always
---

# openpilot-vw 项目理解

## 项目定位

**openpilot-vw** 是基于 [commaai/openpilot](https://github.com/commaai/openpilot) 的个人 fork，目标是支持 **24 款大众速腾（无 ACC）**，仅做车道显示和行驶预测，**不进行车辆控制**。

## 仓库结构

| 层面 | 详情 |
|------|------|
| origin | `git@github.com:mindcont/openpilot-vw.git` |
| upstream | `https://github.com/commaai/openpilot.git` |
| 活跃分支 | `dev-vw`（默认开发分支，origin/HEAD 指向此处） |
| 本地分支 | `dev-vw`、`master` |
| 子模块 | panda、opendbc_repo、msgq_repo、rednose_repo、teleoprtc_repo、tinygrad_repo |

upstream 有大量分支（nightly、release-tici、taco 等），可按需 cherry-pick 或 rebase 同步上游更新。

## 开发历程（提交历史推断）

| 阶段 | 提交编号 | 主要工作 |
|------|---------|---------|
| 基础搭建 | #001–#005 | 代码注释、数据流分析、初始学习文档 |
| 视频/回放 | #004–#008 | 本地 mp4 编码注入消息队列、replay 中文界面（ncursesw 宽字符）、视频流分析 |
| 容器化 | #009–#012 | Docker 发布（含 ARM64/Jetson）、硬件改造文档 |
| 车型适配 | #014–#027 | 车型指纹识别流程、大众 DBC 映射、MQB CAN 解析、适配可行性报告 |
| PC 调试 | #019–#022 | 启动脚本优化、摄像头启用、日志系统完善 |
| 当前 | #028– | 启用摄像头（USE_WEBCAM=1）、保留 pandad 进程、忽略构建产物 |

## 当前运行模式（PC 端调试）

入口：`start_openpilot.sh` → `launch_openpilot.sh` → `system/manager/manager.py`

核心环境变量：

| 变量 | 值 | 作用 |
|------|----|------|
| `USE_WEBCAM` | `1` | 使用 PC 摄像头（启动 webcamerad 进程） |
| `FINGERPRINT` | `VOLKSWAGEN_GOLF_MK7` | 模拟大众 Golf MK7 指纹（MQB 平台） |
| `PASSIVE` | `1` | 被动模式，仅观察不输出控制 |
| `NOBOARD` | `0` | 保留 pandad 进程（即使无 panda 硬件） |
| `LOG_ROOT` | `/data/media/0/realdata/YYYY-MM-DD` | 按日期管理行车数据 |
| `SWAGLOG_DIR` | `/data/logs/YYYY-MM-DD` | 按日期管理系统日志 |

日志策略：按日期存放，自动清理 30 天前数据，同时保持 `current` 软链接兼容。

## 关键自定义文件

| 文件 | 作用 |
|------|------|
| `start_openpilot.sh` | 一键启动脚本：目录权限、虚拟环境、环境变量、日志初始化 |
| `enable_camera.py` | 单独设置 `IsDriverViewEnabled=True` 的辅助脚本 |
| `system/manager/manager.py` | 定制化进程管理器，含中文注释，PC 模式适配 |
| `learn-docs/` | 项目学习文档库（20+ 篇 Markdown） |
| `learn-docs/车型适配/` | 大众速腾适配专项文档（5 篇） |
| `Dockerfile.openpilot-arm64` | ARM64/Jetson 容器构建支持 |
| `data/` | 本地数据目录（已加入 .gitignore） |
| `.codegraph/` | Kiro IDE 缓存（已加入 .gitignore） |

## 技术栈

| 领域 | 工具/框架 |
|------|---------|
| 构建系统 | SCons (`SConstruct`) |
| 包管理 | uv (`pyproject.toml` + `uv.lock`) |
| 消息序列化 | Cap'n Proto（cereal，`.capnp` 文件） |
| 进程间通信 | msgq（本地）、ZMQ（网络/远程调试） |
| AI 推理 | tinygrad（驾驶模型）|
| 视频处理 | VisionIPC，YUV 格式，webcamerad/camerad |
| 文档站点 | MkDocs（readthedocs 主题，`mkdocs.yml`） |
| 目标平台 | PC (Ubuntu 24.04)、comma 3X、Jetson (ARM64) |

## 车型适配进展

目标车型：**2024 款大众速腾**（MQB 平台，无 ACC）

- 使用 `VOLKSWAGEN_GOLF_MK7` 作为代理指纹（MQB 平台同源）
- DBC 文件：`opendbc_repo/opendbc/dbc/vw_mqb_20.dbc`
- CAN 解析服务加载链：`FINGERPRINT` → `CarInterface` → `DBC 加载` → `CAN 服务`
- 当前目标：车道线显示 + 行驶轨迹预测，不介入转向/油门/刹车

## 子模块说明

| 子模块 | 作用 |
|--------|------|
| `panda` | CAN 总线硬件驱动（comma panda 设备） |
| `opendbc_repo` | 车型 DBC 文件库（CAN 信号定义） |
| `msgq_repo` | 高性能进程间消息队列 |
| `rednose_repo` | 卡尔曼滤波器库（定位/传感器融合） |
| `teleoprtc_repo` | WebRTC 远程操控通道 |
| `tinygrad_repo` | 轻量 AI 推理框架 |

`opendbc_repo` 下的 `*_generated.dbc` 为构建产物，会被 `git clean -fd` 清理，不纳入版本控制。

## 开发注意事项

1. **子模块更新**：执行 `git submodule update --remote --merge` 更新到远程最新，或 `git submodule update --init` 恢复到主 repo 记录的版本。
2. **摄像头启动**：webcamerad 进程需要同时满足 `USE_WEBCAM=1` 且 `IsDriverViewEnabled=True` 或 `started=True`。
3. **pandad 行为**：当前即使设置 `NOBOARD=0`，若无实际 panda 设备，pandad 会启动但可能报错，需关注。
4. **虚拟环境**：`.venv/` 已配置，通过 `start_openpilot.sh` 自动激活。
5. **同步上游**：upstream 已添加，需要时 `git fetch upstream` 后 cherry-pick 或 rebase。
