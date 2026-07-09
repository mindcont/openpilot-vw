# Replay 视频回放与外部注入方案

> 本文合并自「VIDEO_REPLAY_SOLUTIONS」与「EXTERNAL_VIDEO_GUIDE」，介绍在 replay
> 中用自定义视频替代内置视频流的两种方案，及外部注入的使用指南。

## 落地状态（重要）

- 本文的两个方案（`--local-video` / `--video-external`）是**早期对 replay 注入
  自定义视频的探索**，涉及修改 replay C++ 核心。
- **本项目实际跑通车道线预测走的是另一条更简单的路**：由 `tools/webcam/camerad.py`
  (webcamerad) 直接读取 mp4 文件当作摄像头输入，无需改 replay。见
  `run_laneline_demo.py` 与《Orin_NX_部署指南.md》。
- 因此下文作为 **replay 注入方案的技术参考** 保留；日常验证请优先用 webcamerad 路线。

## 方案对比与选型

| | 方案一 `--local-video` | 方案二 `--video-external` |
|--|----------------------|--------------------------|
| 思路 | replay 内部读本地 mp4 替换视频帧 | replay 禁用视频，外部脚本注入 |
| 优势 | 实现简单、时间同步易控、无需额外进程 | 模块化、支持任意格式、可实时切换、易调试 |
| 劣势 | 需改 replay 核心、格式支持有限 | 需多进程协调、时间同步较复杂 |

若要在 replay 框架内做，推荐**方案二**（不破坏原架构、易扩展）。

---

## 方案一：本地 MP4 视频流 + Demo 传感器数据

在 replay 内部用 `LocalVideoReader` 读取 mp4，按时间戳替换内置视频帧。

要点改动：
- `main.cc`：`ReplayConfig` 增加 `local_video_path` / `use_local_video`，新增
  `--local-video` 参数。
- `replay.h`：新增 `REPLAY_FLAG_LOCAL_VIDEO`，构造函数增加 `local_video_path`。
- 新建 `tools/replay/local_video_reader.h`：基于 libav* 解码 mp4，提供
  `getFrame(timestamp_ns, rgb_buf)`。
- `replay.cc`：`publishFrame()` 在 `REPLAY_FLAG_LOCAL_VIDEO` 时调用
  `publishLocalVideoFrame()`，解码后转 YUV 推送到 camera_server。

```bash
# 本地 mp4 + demo 传感器数据
./replay --demo --local-video /path/to/video.mp4
```

> 状态：提议实现，本项目未落地采用。

---

## 方案二：禁用视频流 + 外部视频注入

`--video-external` 让 replay 禁用内置视频、等待外部脚本注入，实现视频与传感器
数据分离：视频用自定义 mp4，传感器数据来自原始路由。

### 核心改动
- `main.cc`：`ReplayConfig` 增加 `external_video`，新增 `--video-external` 参数，
  启用时设 `REPLAY_FLAG_NO_VIPC`。
- `replay.cc`：`publishFrame()` 检测到外部视频标志时跳过内置视频帧发布；新增
  `injectExternalFrame()` 接口。
- 新建 `tools/replay/video_injector.py`：用 OpenCV 读 mp4，转 YUV，通过
  `messaging.PubMaster` 按帧率注入 `roadCameraState`。

### 使用方法（三终端）
```bash
# 终端1: 启动 replay（demo 传感器数据，禁用内置视频）
./replay --demo --video-external
# 或指定路由： ./replay "route_name" --video-external

# 终端2: 注入外部视频
python3 tools/replay/video_injector.py /path/to/video.mp4

# 终端3: 启动 UI 查看
cd selfdrive/ui && ./ui.py

# 终端4（可选）: 数据分析
tools/plotjuggler/juggle.py --stream
```

### 工作原理
1. 数据分离：replay 只处理 CAN/GPS/IMU 等传感器数据
2. 视频禁用：内置视频流完全关闭
3. 外部注入：video_injector.py 经消息队列注入视频帧
4. 时间同步：外部脚本负责视频帧时间戳对齐

### 注意事项
- 时间戳同步：外部脚本需正确处理帧时间戳
- 帧率匹配：视频帧率应与原始数据一致（通常 20Hz）
- 分辨率：符合系统要求
- 启动顺序：先启动 replay，再启动注入脚本

### 故障排查
| 现象 | 排查 |
|------|------|
| UI 黑屏 | 确认 video_injector.py 运行中、视频路径正确、消息队列连接正常 |
| 数据不同步 | 检查视频帧率、时间戳计算、注入脚本延迟参数 |

> 状态：早期探索方案。实际项目改用 webcamerad 直接读 mp4（见落地状态说明）。
