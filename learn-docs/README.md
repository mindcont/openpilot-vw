# openpilot-vw 学习文档索引

本项目（24 款大众速腾，MQB 平台，无 ACC，纯视觉车道显示/预测、**不控车**）的
学习与开发文档。按主题分类，标注时效状态。

状态说明：
- ✅ **当前有效** — 与实际采用路线一致、经验证
- 📖 **参考** — 机制/架构说明，长期稳定
- 🔄 **进行中** — 任务清单/待验证事项，完成后汇总或归档
- 🗄️ **已归档** — 过时或被取代，移入 `车型适配/archive/`

---

## 一、车型适配（速腾 / MQB）

实际路线：代理指纹 `VOLKSWAGEN_GOLF_MK7` + `vw_mqb.dbc` + 纯视觉/CAN 读取 + 不控车。

| 文档 | 状态 | 说明 |
|------|------|------|
| [车型适配/大众速腾CAN抓包解析报告.md](车型适配/大众速腾CAN抓包解析报告.md) | ✅ | J533 实车抓包，vw_mqb.dbc 全量解析结论 |
| [车型适配/第二阶段_接入CAN可行性评估.md](车型适配/第二阶段_接入CAN可行性评估.md) | ✅ | 接入 CAN 满足不控车+预测的评估 |
| [车型适配/Orin_NX_部署指南.md](车型适配/Orin_NX_部署指南.md) | ✅ | Jetson Orin NX 双摄像头生产部署 |
| [车型适配/远程调试指南.md](车型适配/远程调试指南.md) | ✅ | 远程调试方法 |
| [Orin_NX_验证任务清单.md](Orin_NX_验证任务清单.md) | 🔄 | Orin NX 断网续接：Bug2注入/UI全屏/软件自动曝光待实机验证清单 |
| [大众车型DBC文件映射分析.md](大众车型DBC文件映射分析.md) | ✅ | MQB/PQ/MLB 平台与 DBC 映射（今日验证结论正确）|
| [openpilot_车型指纹配置指南.md](openpilot_车型指纹配置指南.md) | ✅ | FINGERPRINT 配置（代理指纹路线）|
| [VOLKSWAGEN_GOLF_MK7_CAN解析服务加载流程.md](VOLKSWAGEN_GOLF_MK7_CAN解析服务加载流程.md) | 📖 | 车型识别→DBC 加载→CAN 服务链路 |
| [车型适配/openpilot_车型加载逻辑分析.md](车型适配/openpilot_车型加载逻辑分析.md) | 📖 | 车型加载机制分析 |
| [车型适配/VEHICLE_ADAPTATION_GUIDE.md](车型适配/VEHICLE_ADAPTATION_GUIDE.md) | 📖 | 通用车型适配架构（含控车调参，控车部分不适用本项目）|
| 车型适配/archive/ | 🗄️ | 早期 SAGITAR_MK8 补丁路线等，见该目录 README |

## 二、视频 / 摄像头 / 视觉流水线

| 文档 | 状态 | 说明 |
|------|------|------|
| [视频流说明.md](视频流说明.md) | 📖 | 视频规格、YUV、模型对传感器的依赖 |
| [视频流加载机制分析.md](视频流加载机制分析.md) | 📖 | camerad/VisionIPC 代码级机制、设备映射 |
| [openpilot_摄像头启动配置指南.md](openpilot_摄像头启动配置指南.md) | 📖 | PC/webcam 摄像头启动条件 |
| [VIDEO_REPLAY_SOLUTIONS.md](VIDEO_REPLAY_SOLUTIONS.md) | 📖 | 视频回放与外部注入方案（含原 EXTERNAL_VIDEO_GUIDE）|

## 三、数据流 / 日志 / 记录

| 文档 | 状态 | 说明 |
|------|------|------|
| [openpilot_数据流及格式.md](openpilot_数据流及格式.md) | 📖 | 消息队列、数据格式、IPC |
| [openpilot_complete_data_recording.md](openpilot_complete_data_recording.md) | 📖 | 数据记录流程/完整数据字典 |
| [openpilot_日志系统.md](openpilot_日志系统.md) | 📖 | 日志三层次+数据结构+存储运维（合并自 3 篇）|

## 四、AI 模型 / 仿真

| 文档 | 状态 | 说明 |
|------|------|------|
| [AI_MODELS_ANALYSIS.md](AI_MODELS_ANALYSIS.md) | 📖 | 驾驶模型架构（vision+policy）、TinyGrad |
| [MetaDrive_仿真接口文档.md](MetaDrive_仿真接口文档.md) | 📖 | MetaDrive 仿真集成 |

## 五、工具 / 进程 / 通信

| 文档 | 状态 | 说明 |
|------|------|------|
| [openpilot_进程启动指南.md](openpilot_进程启动指南.md) | 📖 | 启动脚本、进程管理、环境变量 |
| [TOOLS_GUIDE.md](TOOLS_GUIDE.md) | 📖 | Cabana/PlotJuggler/Replay 工具 |
| [can_replay工具详细文档.md](can_replay工具详细文档.md) | 📖 | CAN replay 工具 |
| [ZMQ_MODE_GUIDE.md](ZMQ_MODE_GUIDE.md) | 📖 | ZMQ 网络通信/远程调试 |

## 六、环境 / 部署 / 硬件

| 文档 | 状态 | 说明 |
|------|------|------|
| [环境搭建与容器部署.md](环境搭建与容器部署.md) | 📖 | 开发机环境/编译/ARM64 容器/JetPack/systemd（合并自 2 篇）|
| [硬件改造.md](硬件改造.md) | 📖 | 硬件改造记录 |

---

## 相关代码工具

- `tools/vw/can_analysis/` — CAN 抓包解析工具（DBC 匹配度、信号解析、
  全量扫描、ACC 距离评估、carState 依赖核对）
- `run_laneline_demo.py` — PC 纯视觉车道线预测验证脚本
- `start_openpilot_orinnx.sh` — Orin NX 双摄像头生产启动脚本
