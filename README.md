<div align="center" style="text-align: center;">

<h1>openpilot-vw</h1>

<p>
  <b>openpilot is an operating system for robotics.</b>
  <br>
本分支用来支持我自己的汽车，一辆24款大众速腾汽车，没有acc ,仅用来做相关的车道显示和预测，不进行控制。
</p>

</div>





## 学习笔记

| 文档名称 | 功能作用 | 主要内容 |
|---------|---------|----------|
| [安装及编译.md](learn-docs/安装及编译.md) | 环境搭建指南 | Ubuntu 24.04 环境配置、依赖安装、编译流程 |
| [视频流说明.md](learn-docs/视频流说明.md) | 视频处理机制 | 摄像头数据流、YUV 格式、VisionIPC 通信 |
| [AI_MODELS_ANALYSIS.md](learn-docs/AI_MODELS_ANALYSIS.md) | AI 模型分析 | 驾驶模型架构、输入输出格式、TinyGrad 框架 |
| [EXTERNAL_VIDEO_GUIDE.md](learn-docs/EXTERNAL_VIDEO_GUIDE.md) | 外部视频注入 | Replay 外部视频模式使用方法和技术实现 |
| [MetaDrive_仿真接口文档.md](learn-docs/MetaDrive_仿真接口文档.md) | 仿真环境接口 | MetaDrive 仿真器集成、API 接口说明 |
| [openpilot_数据流及格式.md](learn-docs/openpilot_数据流及格式.md) | 数据流架构 | 消息队列、数据格式、进程间通信机制 |
| [openpilot_complete_data_recording.md](learn-docs/openpilot_complete_data_recording.md) | 数据记录系统 | 完整数据记录流程、存储格式、回放机制 |
| [openpilot_log_structure.md](learn-docs/openpilot_log_structure.md) | 日志结构分析 | 日志文件格式、数据解析、结构说明 |
| [TOOLS_GUIDE.md](learn-docs/TOOLS_GUIDE.md) | 工具集使用指南 | Cabana、PlotJuggler、Replay 等工具详解 |
| [VIDEO_REPLAY_SOLUTIONS.md](learn-docs/VIDEO_REPLAY_SOLUTIONS.md) | 视频回放方案 | 本地视频流、外部视频注入技术方案 |
| [ZMQ_MODE_GUIDE.md](learn-docs/ZMQ_MODE_GUIDE.md) | ZMQ 模式详解 | ZeroMQ 网络通信、远程调试、分布式开发 |
| [openpilot_进程启动指南.md](learn-docs/openpilot_进程启动指南.md) | 进程启动管理 | 启动脚本、进程管理器、环境变量配置 |
| [openpilot_日志系统详解.md](learn-docs/openpilot_日志系统详解.md) | 日志系统管理 | 日志存储、格式分析、查看工具、故障排除 |
| [视频流加载机制分析.md](learn-docs/视频流加载机制分析.md) | 视频流处理机制 | 摄像头设备映射、VisionIPC通信、图像格式转换 |
| [openpilot_摄像头启动配置指南.md](learn-docs/openpilot_摄像头启动配置指南.md) | 摄像头启动配置 | PC模式摄像头启动条件、设备配置、故障排除 |



















To start developing openpilot
------

openpilot is developed by [comma](https://comma.ai/) and by users like you. We welcome both pull requests and issues on [GitHub](http://github.com/commaai/openpilot).

* Join the [community Discord](https://discord.comma.ai)
* Check out [the contributing docs](docs/CONTRIBUTING.md)
* Check out the [openpilot tools](tools/)
* Code documentation lives at https://docs.comma.ai
* Information about running openpilot lives on the [community wiki](https://github.com/commaai/openpilot/wiki)

Want to get paid to work on openpilot? [comma is hiring](https://comma.ai/jobs#open-positions) and offers lots of [bounties](https://comma.ai/bounties) for external contributors.
