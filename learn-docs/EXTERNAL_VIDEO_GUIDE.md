# Replay 外部视频模式使用指南

## 功能说明

新增的 `--video-external` 参数允许 replay 工具禁用内置视频流，等待外部脚本注入视频数据。这样可以实现：
- 使用自定义 MP4 视频文件
- 保持传感器数据来自原始路由
- 分离视频和数据处理流程

## 使用方法

### 1. 启动 Replay（外部视频模式）
```bash
# 使用 demo 路由的传感器数据，禁用内置视频
./replay --demo --video-external

# 或者使用特定路由
./replay "route_name" --video-external
```

### 2. 运行外部视频注入脚本
```bash
# 在另一个终端运行（假设已有 video_injector.py）
python3 tools/replay/video_injector.py /path/to/your/video.mp4
```

### 3. 启动 UI 查看效果
```bash
# 在第三个终端启动 UI
cd selfdrive/ui && ./ui.py
```

## 技术实现

### 修改内容

1. **main.cc**:
   - 添加 `external_video` 配置字段
   - 新增 `--video-external` 命令行参数
   - 当启用外部视频时自动设置 `REPLAY_FLAG_NO_VIPC`

2. **replay.cc**:
   - 修改 `publishFrame()` 方法
   - 当检测到 `REPLAY_FLAG_NO_VIPC` 时跳过内置视频帧发布

### 工作原理

1. **数据分离**: replay 只处理传感器数据（CAN、GPS、IMU等）
2. **视频禁用**: 内置视频流被完全禁用
3. **外部注入**: video_injector.py 通过消息队列注入视频帧
4. **时间同步**: 外部脚本需要处理视频帧的时间戳同步

## 优势

- **模块化**: 视频和数据处理完全分离
- **灵活性**: 支持任意视频格式和来源
- **调试友好**: 可以独立测试视频和数据流
- **扩展性**: 未来可支持实时摄像头输入

## 注意事项

1. **时间同步**: 外部视频脚本需要正确处理时间戳
2. **帧率匹配**: 视频帧率应与原始数据匹配（通常20Hz）
3. **分辨率**: 确保视频分辨率符合系统要求
4. **启动顺序**: 建议先启动 replay，再启动视频注入脚本

## 故障排查

### 问题：UI 显示黑屏
- 检查 video_injector.py 是否正常运行
- 确认视频文件路径正确
- 验证消息队列连接状态

### 问题：数据不同步
- 检查视频帧率设置
- 确认时间戳计算正确
- 调整视频注入脚本的延迟参数

## 示例命令

```bash
# 完整的使用流程
# 终端1: 启动 replay
./replay --demo --video-external

# 终端2: 注入视频（需要 video_injector.py）
python3 tools/replay/video_injector.py demo_video.mp4

# 终端3: 启动 UI
cd selfdrive/ui && ./ui.py

# 终端4: 可选，启动数据分析工具
tools/plotjuggler/juggle.py --stream
```

这个功能为开发者提供了更大的灵活性，可以在保持真实传感器数据的同时使用自定义视频内容进行测试和开发。