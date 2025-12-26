# openpilot 日志数据结构与存储机制详解

## 概述

openpilot 使用高效的二进制日志系统记录自动驾驶过程中的所有数据，包括传感器数据、控制指令、系统状态等。本文档详细介绍了日志的数据结构、存储机制和访问方法。

## 1. 文件格式

### 1.1 文件类型
- **`.rlog.bz2`**: 压缩的二进制日志文件（主要格式）
- **`.qlog.bz2`**: 压缩的查询优化日志文件
- **`.rlog.zst`**: Zstandard 压缩格式
- **不支持直接解压为文本文件**

### 1.2 序列化格式
- 使用 **Cap'n Proto** 二进制序列化
- 零拷贝、高性能的数据交换格式
- 消息类型由 `cereal/log.capnp` 定义

## 2. 数据结构

### 2.1 基本消息结构
每条日志记录包含以下基本结构：

```json
{
  "logMonoTime": 1690464079123456789,  // 纳秒级时间戳
  "which": "carState",                 // 消息类型
  "carState": { ... }                  // 消息内容
}
```

### 2.2 典型消息示例

#### carState（车辆状态）
```json
{
  "logMonoTime": 1690464079123456789,
  "which": "carState",
  "carState": {
    "vEgo": 15.2,                    // 车辆速度 (m/s)
    "aEgo": 0.1,                     // 车辆加速度 (m/s²)
    "steeringAngleDeg": -2.5,        // 转向角度 (度)
    "steeringTorque": 1.2,           // 方向盘力矩 (Nm)
    "brake": 0.0,                    // 刹车踏板 (0-1)
    "gas": 0.3,                      // 油门踏板 (0-1)
    "gearShifter": "drive",          // 档位
    "handbrakePressed": false,       // 手刹状态
    "leftBlinker": false,            // 左转向灯
    "rightBlinker": false,           // 右转向灯
    "wheelSpeeds": {
      "fl": 15.1, "fr": 15.3,       // 前轮速度
      "rl": 15.0, "rr": 15.2        // 后轮速度
    },
    "cruiseState": {
      "enabled": true,               // 巡航启用
      "speed": 16.7,                 // 设定速度
      "available": true              // 巡航可用
    }
  }
}
```

## 3. 主要消息类型

### 3.1 核心数据流

| 消息类型 | 描述 | 主要字段 |
|---------|------|---------|
| **carState** | 车辆状态 | 速度、加速度、转向角、踏板状态 |
| **carControl** | 控制指令 | 期望加速度、转向角、力矩 |
| **controlsState** | 控制系统状态 | 系统启用状态、控制模式 |
| **radarState** | 雷达数据 | 前车距离、相对速度、加速度 |
| **modelV2** | AI模型输出 | 轨迹预测、车道线检测 |

### 3.2 传感器数据

| 消息类型 | 描述 | 主要字段 |
|---------|------|---------|
| **gyroscope** | 陀螺仪 | XYZ轴角速度 |
| **accelerometer** | 加速度计 | XYZ轴加速度 |
| **gpsLocationExternal** | GPS定位 | 纬度、经度、海拔、速度 |
| **roadCameraState** | 摄像头状态 | 帧ID、时间戳、曝光时间 |

### 3.3 系统监控

| 消息类型 | 描述 | 主要字段 |
|---------|------|---------|
| **deviceState** | 设备状态 | CPU温度、内存使用、电池电量 |
| **liveParameters** | 实时参数 | 转向比、角度偏移、刚度系数 |
| **driverStateV2** | 驾驶员监控 | 注意力评分、面部朝向 |

## 4. 数据频率特征

### 4.1 各类数据的典型频率

| 数据类型 | 频率 | 间隔 | 用途 |
|---------|------|------|------|
| carState | 100Hz | 10ms | 车辆状态实时监控 |
| carControl | 100Hz | 10ms | 控制指令实时执行 |
| controlsState | 100Hz | 10ms | 控制系统状态 |
| radarState | 20Hz | 50ms | 雷达目标跟踪 |
| modelV2 | 20Hz | 50ms | AI模型推理输出 |
| deviceState | 2Hz | 500ms | 设备健康监控 |
| gpsLocation | 10Hz | 100ms | GPS定位更新 |
| gyroscope | 104Hz | ~9.6ms | 陀螺仪传感器 |
| accelerometer | 104Hz | ~9.6ms | 加速度计传感器 |

### 4.2 频率分布特点

- **高频数据（100Hz+）**: 关键控制回路，需要实时响应
- **中频数据（20-50Hz）**: 感知和规划，平衡性能和精度
- **低频数据（1-10Hz）**: 监控和状态，减少存储开销

## 5. 存储机制

### 5.1 异步混合存储模式

openpilot 使用**时间戳驱动的异步存储**，不同频率的数据混合存储：

```
时间轴示例:
t=0ms:    carState (100Hz)
t=10ms:   carControl (100Hz)
t=20ms:   carState (100Hz)
t=30ms:   carControl (100Hz)
t=40ms:   carState (100Hz)
t=50ms:   radarState (20Hz)  ← 不同频率数据插入
t=60ms:   carControl (100Hz)
t=70ms:   carState (100Hz)
t=100ms:  radarState (20Hz)
t=500ms:  deviceState (2Hz)  ← 低频数据
```

### 5.2 存储特点

#### 时间戳驱动
- 每条消息都有精确的纳秒级时间戳 (`logMonoTime`)
- 按时间戳顺序写入，不按消息类型分组
- 回放时严格按时间顺序重现

#### 异步生产
- 各个进程独立产生数据
- 不等待其他数据，立即写入
- 避免了同步等待造成的延迟

#### 混合存储优势
```python
# 实际存储序列 (简化示例)
[
  {t: 1000000, type: "carState", data: {...}},
  {t: 1005000, type: "carControl", data: {...}},
  {t: 1010000, type: "carState", data: {...}},
  {t: 1015000, type: "carControl", data: {...}},
  {t: 1020000, type: "carState", data: {...}},
  {t: 1025000, type: "radarState", data: {...}},  # 不同频率
  {t: 1030000, type: "carControl", data: {...}},
]
```

### 5.3 存储优化

#### 压缩机制
- 使用 bz2/zstd 压缩，通常压缩比 5:1 到 10:1
- Cap'n Proto 零拷贝序列化
- 增量存储，只记录变化的数据

#### 数据完整性
- 每个消息独立存储，单个消息损坏不影响其他
- 支持部分读取和随机访问
- 时间戳保证数据的时序关系

## 6. 数据访问方法

### 6.1 基本读取

```python
from openpilot.tools.lib.logreader import LogReader

# 加载日志文件
lr = LogReader("path/to/file.rlog.bz2")

# 遍历所有消息
for msg in lr:
    timestamp = msg.logMonoTime
    msg_type = msg.which()
    print(f"时间: {timestamp}, 类型: {msg_type}")
```

### 6.2 按类型过滤

```python
# 只读取车辆状态数据
for car_state in lr.filter('carState'):
    speed = car_state.vEgo
    steering = car_state.steeringAngleDeg
    print(f"速度: {speed}, 转向: {steering}")

# 获取第一条特定类型消息
first_control = lr.first('carControl')
```

### 6.3 时间序列分析

```python
# 转换为时间序列数据
time_series = lr.time_series

# 按时间范围过滤
# 支持快进、慢放、跳转
# 保持各数据流的相对时序关系
```

## 7. 工具和分析

### 7.1 日志分析工具

```bash
# 使用内置分析器
python3 tools/replay/log_analyzer.py /path/to/logfile.rlog.bz2

# 显示消息类型统计、频率分析、时间分布
```

### 7.2 可视化工具

- **data_viewer.py**: 图形化数据流查看器
- **plotjuggler**: 专业的时间序列数据可视化
- **cabana**: CAN数据分析工具

### 7.3 回放工具

```bash
# 回放日志数据
tools/replay/replay <route-name>

# 配合UI查看
cd selfdrive/ui && ./ui.py
```

## 8. 应用场景

### 8.1 开发调试
- 算法验证和参数调优
- 问题复现和根因分析
- 性能评估和基准测试

### 8.2 数据分析
- 驾驶行为分析
- 系统性能监控
- 故障诊断和预测

### 8.3 机器学习
- 训练数据收集
- 模型验证和测试
- 数据增强和标注

## 9. 最佳实践

### 9.1 存储管理
- 定期清理旧日志文件
- 使用压缩格式节省空间
- 按需选择记录的数据类型

### 9.2 性能优化
- 使用流式读取处理大文件
- 按消息类型过滤减少处理量
- 利用多进程并行分析

### 9.3 数据质量
- 检查时间戳连续性
- 验证数据完整性
- 监控异常值和缺失数据

## 10. 总结

openpilot 的日志系统采用了先进的异步混合存储机制，能够高效地记录和管理多种不同频率的数据流。通过精确的时间戳同步和优化的存储格式，为自动驾驶系统的开发、调试和分析提供了强大的数据基础。

这种设计的核心优势在于：
- **时间精度**: 纳秒级时间戳保证精确同步
- **存储效率**: 压缩和优化的二进制格式
- **访问灵活**: 支持流式、随机和过滤访问
- **数据完整**: 独立消息存储保证可靠性
- **扩展性**: 支持新的消息类型和数据流

通过理解这些机制，开发者可以更好地利用 openpilot 的日志数据进行系统优化和问题分析。


## 11. 实时日志
在 openpilot 系统中，您列出的这些名称代表了系统运行时的各个**守护进程（Daemons）**。openpilot 采用微服务架构，每个进程负责特定的功能模块，通过消息中间件（Cereal）进行异步通信。

当您在日志或终端中看到这些名称时，通常表示系统正在启动、关闭或监控这些服务的运行状态。

以下是这些进程按照功能分类的详细释义：

### 1. 核心控制与感知层 (Core Driving Stack)
*   **modeld**: 核心 AI 推理引擎。负责运行神经网络，处理摄像头图像并输出车道线、障碍物及驾驶路径。
*   **plannerd**: 路径规划器。根据 `modeld` 的输出，计算未来几秒内的行驶轨迹（横向和纵向）。
*   **controlsd**: 控制循环。负责执行 PID/LQR 算法，将规划的路径转化为具体的转向、加速和制动指令。
*   **card**: 车辆接口。负责将 openpilot 的通用指令翻译为特定车型的 CAN 总线协议。
*   **radard**: 雷达处理进程。解析车辆前向雷达的数据。
*   **torqued**: 转向转矩估计。实时估算转向系统的摩擦力和参数，以优化转向平顺度。

### 2. 硬件与底层通信 (Hardware & Communication)
*   **pandad**: Panda 适配器守护进程。负责与物理 Panda 硬件（或集成在 comma three 内部的 Panda）通信，处理 CAN 总线数据的收发。
*   **hardwared**: 硬件抽象层。监控设备温度、风扇速度、电池状态及电压。
*   **camerad**: 摄像头驱动。负责从图像传感器获取原始帧（Road/Driver/Wide）。
*   **locationd**: 定位服务。融合 GPS、IMU（惯性测量单元）和视觉里程计数据，确定车辆的精确位置。
*   **micd**: 麦克风进程。处理音频输入。

### 3. 数据记录与处理 (Logging & Storage)
*   **loggerd**: 数据记录器。将所有总线数据和传感器数据写入日志文件（.qlog 或 .rlog）。
*   **encoderd**: 视频编码器。将原始摄像头画面压缩为 H.264 或 H.265 格式。
*   **proclogd**: 进程监控记录。记录系统资源占用情况（CPU、内存等）。
*   **logmessaged**: 系统消息日志。收集各进程产生的文本日志信息。
*   **deleter**: 存储管理器。当磁盘空间不足时，负责按照策略删除旧的日志文件。

### 4. 用户交互与状态 (UI & Stats)
*   **ui**: 用户界面。负责屏幕上的画面渲染、警告显示及用户触摸交互。
*   **soundd**: 音频输出。负责播放警报音、提示音及语音播报。
*   **statsd**: 统计服务。收集驾驶里程、使用时长等数据并上传。
*   **feedbackd**: 反馈处理。处理用户提交的错误报告或反馈信息。

### 5. 系统管理 (System Management)
*   **paramsd**: 参数管理。负责读取和持久化存储系统配置参数（如校准值、用户设置）。
*   **calibrationd**: 自动校准进程。计算摄像头相对于路面的俯仰角（Pitch）和偏航角（Yaw）。
*   **selfdrived**: 高级状态机。管理 openpilot 的整体开启/关闭状态及驾驶模式切换。
*   **lagd**: 延迟监控。监控系统各环节的响应延迟，确保实时性。
*   **journald**: 系统日志桥接。对接 Linux 系统的 systemd 日志。

---

### 总结
*   **第一组短列表**：通常出现在系统初始化阶段或低功耗模式（Offroad），此时仅启动必要的硬件监控和 UI 进程。
*   **第二组长列表**：代表系统处于 **Onroad（行车）状态**。这是 openpilot 全功能运行的完整堆栈，涵盖了从视觉感知到车辆控制的所有环节。

如果您在日志中看到某个进程名后跟随 `EXIT` 或 `CRASH`，则表明该特定模块出现了故障，这通常会导致 openpilot 退出自动驾驶模式并发出警报。
