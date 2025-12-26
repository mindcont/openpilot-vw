# 方案一：本地MP4视频流 + Demo传感器数据

## 技术实现

### 1. 修改 main.cc 添加新参数

```cpp
// 在 ReplayConfig 结构体中添加
struct ReplayConfig {
  // ... 现有字段 ...
  std::string local_video_path;  // 本地MP4文件路径
  bool use_local_video = false;  // 是否使用本地视频
};

// 在 cli_options 中添加
const struct option cli_options[] = {
  // ... 现有选项 ...
  {"local-video", required_argument, nullptr, 0},  // 本地视频文件
  {nullptr, 0, nullptr, 0},
};

// 在解析逻辑中添加
case 0: {
  std::string name = cli_options[option_index].name;
  if (name == "local-video") {
    config.local_video_path = optarg;
    config.use_local_video = true;
  }
  // ... 其他选项 ...
  break;
}
```

### 2. 修改 replay.h 添加本地视频支持

```cpp
enum REPLAY_FLAGS {
  // ... 现有标志 ...
  REPLAY_FLAG_LOCAL_VIDEO = 0x1000,  // 使用本地视频
};

class Replay {
public:
  // 添加构造函数参数
  Replay(const std::string &route, std::vector<std::string> allow, 
         std::vector<std::string> block, SubMaster *sm = nullptr,
         uint32_t flags = REPLAY_FLAG_NONE, const std::string &data_dir = "",
         bool auto_source = false, const std::string &local_video_path = "");

private:
  std::string local_video_path_;  // 本地视频文件路径
  std::unique_ptr<LocalVideoReader> local_video_reader_;  // 本地视频读取器
};
```

### 3. 创建 LocalVideoReader 类

```cpp
// tools/replay/local_video_reader.h
#pragma once
#include <string>
#include <memory>
extern "C" {
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libswscale/swscale.h>
}

class LocalVideoReader {
public:
  LocalVideoReader(const std::string &video_path);
  ~LocalVideoReader();
  
  bool load();
  bool getFrame(uint64_t timestamp_ns, uint8_t *rgb_buf);
  int getWidth() const { return width_; }
  int getHeight() const { return height_; }
  double getDuration() const { return duration_; }
  
private:
  std::string video_path_;
  AVFormatContext *format_ctx_ = nullptr;
  AVCodecContext *codec_ctx_ = nullptr;
  SwsContext *sws_ctx_ = nullptr;
  int video_stream_idx_ = -1;
  int width_, height_;
  double duration_;
  double fps_;
};
```

### 4. 修改 replay.cc 实现混合数据源

```cpp
// 在 Replay 构造函数中
Replay::Replay(const std::string &route, ..., const std::string &local_video_path)
    : local_video_path_(local_video_path) {
  
  if (!local_video_path_.empty()) {
    flags_ |= REPLAY_FLAG_LOCAL_VIDEO;
    local_video_reader_ = std::make_unique<LocalVideoReader>(local_video_path_);
  }
}

// 修改 publishFrame 方法
void Replay::publishFrame(const Event *e) {
  if (flags_ & REPLAY_FLAG_LOCAL_VIDEO) {
    // 使用本地视频帧
    publishLocalVideoFrame(e->mono_time);
  } else {
    // 使用原有逻辑
    camera_server_->pushFrame(e->which, e);
  }
}

void Replay::publishLocalVideoFrame(uint64_t timestamp) {
  if (!local_video_reader_) return;
  
  // 分配帧缓冲区
  int width = local_video_reader_->getWidth();
  int height = local_video_reader_->getHeight();
  std::vector<uint8_t> rgb_buf(width * height * 3);
  
  // 获取对应时间戳的帧
  if (local_video_reader_->getFrame(timestamp, rgb_buf.data())) {
    // 转换为YUV并发送到camera_server
    camera_server_->pushLocalFrame(rgb_buf.data(), width, height, timestamp);
  }
}
```

## 使用方法

```bash
# 使用本地MP4视频 + Demo传感器数据
./replay --demo --local-video /path/to/video.mp4

# 禁用原始视频流，只使用本地视频
./replay --demo --local-video /path/to/video.mp4 --no-vipc
```

---

# 方案二：禁用视频流 + 外部视频注入

## 技术实现

### 1. 添加 --video-external 参数

```cpp
// 在 ReplayConfig 中添加
struct ReplayConfig {
  // ... 现有字段 ...
  bool external_video = false;  // 使用外部视频流
};

// 添加命令行选项
{"video-external", no_argument, nullptr, 0},  // 外部视频模式

// 新增标志位
enum REPLAY_FLAGS {
  // ... 现有标志 ...
  REPLAY_FLAG_EXTERNAL_VIDEO = 0x2000,  // 外部视频模式
};
```

### 2. 修改视频流处理逻辑

```cpp
void Replay::publishFrame(const Event *e) {
  if (flags_ & REPLAY_FLAG_EXTERNAL_VIDEO) {
    // 跳过视频帧发布，等待外部注入
    return;
  }
  
  if (!(flags_ & REPLAY_FLAG_NO_VIPC)) {
    camera_server_->pushFrame(e->which, e);
  }
}

// 添加外部视频接口
void Replay::injectExternalFrame(const uint8_t *data, int width, int height, 
                                uint64_t timestamp, CameraType camera_type) {
  if (flags_ & REPLAY_FLAG_EXTERNAL_VIDEO && camera_server_) {
    camera_server_->pushExternalFrame(data, width, height, timestamp, camera_type);
  }
}
```

### 3. 创建外部视频注入脚本

```python
#!/usr/bin/env python3
# tools/replay/video_injector.py

import cv2
import time
import zmq
import numpy as np
from cereal import messaging

class VideoInjector:
    def __init__(self, video_path, camera_type='roadCameraState'):
        self.video_path = video_path
        self.camera_type = camera_type
        self.pm = messaging.PubMaster([camera_type])
        
    def inject_video(self):
        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = 1.0 / fps
        
        start_time = time.time()
        frame_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            # 转换为YUV格式
            yuv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
            
            # 创建消息
            msg = messaging.new_message(self.camera_type)
            msg.roadCameraState.frameId = frame_count
            msg.roadCameraState.timestampSof = int(time.time() * 1e9)
            
            # 发送帧数据
            self.pm.send(self.camera_type, msg)
            
            # 控制帧率
            expected_time = start_time + frame_count * frame_interval
            current_time = time.time()
            if current_time < expected_time:
                time.sleep(expected_time - current_time)
                
            frame_count += 1
            
        cap.release()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python3 video_injector.py <video_path>")
        sys.exit(1)
        
    injector = VideoInjector(sys.argv[1])
    injector.inject_video()
```

## 使用方法

```bash
# 终端1: 启动replay（禁用视频流）
./replay --demo --video-external

# 终端2: 注入外部视频
python3 tools/replay/video_injector.py /path/to/video.mp4

# 终端3: 启动UI观看
cd selfdrive/ui && ./ui.py
```

---

# 可行性分析

## 方案一优势
- ✅ 实现简单，修改量小
- ✅ 视频和数据时间同步容易控制
- ✅ 不需要额外进程

## 方案一劣势  
- ❌ 需要修改核心replay代码
- ❌ 视频格式支持有限

## 方案二优势
- ✅ 模块化设计，replay核心不变
- ✅ 支持任意视频格式
- ✅ 可以实时切换视频源
- ✅ 便于调试和开发

## 方案二劣势
- ❌ 需要多进程协调
- ❌ 时间同步复杂

## 推荐方案

**建议采用方案二**，理由：
1. 更灵活，不破坏原有架构
2. 便于扩展和维护
3. 支持实时视频流注入
4. 适合开发和测试场景

## 快速实现步骤

1. 添加 `--video-external` 参数
2. 修改 `publishFrame` 跳过视频发布
3. 创建 `video_injector.py` 脚本
4. 测试验证功能

这样可以实现你需要的功能：replay播放传感器数据，外部脚本提供视频流。