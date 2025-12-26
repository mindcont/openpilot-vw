# openpilot 完整数据记录与存储系统

## 概述

openpilot 系统记录的数据远不止日志文件，它是一个完整的数据采集和存储系统，包含多种数据类型和存储方式。本文档详细列举所有记录的数据类型。

## 1. 数据记录类型分类

### 1.1 实时消息数据 (rlog/qlog)

#### 🚗 车辆状态数据 (100Hz)
- **carState**: 车辆基础状态
  - 速度、加速度、转向角
  - 踏板位置、档位、手刹
  - 车轮速度、巡航状态
- **carControl**: 控制指令
  - 期望加速度、转向角、力矩
- **carOutput**: 车辆输出状态
- **carParams**: 车辆参数配置

#### 🎯 感知与规划数据 (20Hz)
- **radarState**: 雷达目标检测
  - 前车距离、相对速度、加速度
- **liveTracks**: 实时目标跟踪
- **modelV2**: AI模型输出
  - 轨迹预测、车道线检测
  - 目标识别、路径规划
- **drivingModelData**: 驾驶模型数据
- **longitudinalPlan**: 纵向规划
- **driverAssistance**: 驾驶辅助功能

#### 🎛️ 控制系统数据 (100Hz)
- **controlsState**: 控制系统状态
  - 系统启用/激活状态
  - 控制模式、警报状态
- **selfdriveState**: 自动驾驶状态
- **pandaStates**: Panda设备状态
- **peripheralState**: 外设状态

#### 📡 传感器数据 (25-104Hz)
- **gyroscope**: 陀螺仪 (104Hz)
  - XYZ轴角速度
- **accelerometer**: 加速度计 (104Hz)
  - XYZ轴加速度
- **magnetometer**: 磁力计 (25Hz)
- **lightSensor**: 光线传感器 (100Hz)
- **temperatureSensor**: 温度传感器 (2Hz)

#### 🛰️ 定位数据 (1-10Hz)
- **gpsLocationExternal**: 外部GPS (10Hz)
- **gpsLocation**: 内部GPS (1Hz)
- **gpsNMEA**: GPS NMEA数据 (9Hz)
- **ubloxGnss**: u-blox GNSS (10Hz)
- **qcomGnss**: 高通GNSS (2Hz)
- **gnssMeasurements**: GNSS测量 (10Hz)
- **ubloxRaw**: u-blox原始数据 (20Hz)

#### 📷 摄像头状态数据 (20Hz)
- **roadCameraState**: 道路摄像头状态
- **driverCameraState**: 驾驶员摄像头状态
- **wideRoadCameraState**: 广角摄像头状态

#### 👤 驾驶员监控数据 (20Hz)
- **driverStateV2**: 驾驶员状态V2
  - 注意力评分、面部朝向
  - 眼睛睁开度、头部姿态
- **driverMonitoringState**: 驾驶员监控状态

#### 🔧 系统监控数据 (0.1-20Hz)
- **deviceState**: 设备状态 (2Hz)
  - CPU温度、内存使用率
  - 存储空间、电池电量
- **procLog**: 进程日志 (0.5Hz)
- **managerState**: 管理器状态 (2Hz)
- **uploaderState**: 上传器状态
- **clocks**: 时钟同步 (0.1Hz)

#### 🎚️ 实时参数数据 (4-20Hz)
- **liveParameters**: 实时参数 (20Hz)
  - 转向比、角度偏移、刚度系数
- **liveCalibration**: 实时标定 (4Hz)
  - 俯仰角、偏航角、横滚角
- **liveTorqueParameters**: 实时力矩参数 (4Hz)
- **liveDelay**: 实时延迟 (4Hz)
- **livePose**: 实时姿态 (20Hz)
- **cameraOdometry**: 摄像头里程计 (20Hz)

#### 🚌 CAN总线数据 (100Hz)
- **can**: CAN总线消息
- **sendcan**: 发送CAN数据

#### 🎵 音频数据 (10-20Hz)
- **soundPressure**: 声压 (10Hz)
- **rawAudioData**: 原始音频数据 (20Hz)
- **audioFeedback**: 音频反馈

#### 🗺️ 导航数据
- **navInstruction**: 导航指令 (1Hz)
- **navRoute**: 导航路线
- **navThumbnail**: 导航缩略图

#### 🎮 交互数据
- **touch**: 触摸事件 (20Hz)
- **userBookmark**: 用户书签
- **bookmarkButton**: 书签按钮
- **onroadEvents**: 道路事件 (1Hz)

#### 🐛 调试数据
- **uiDebug**: UI调试信息
- **alertDebug**: 警报调试 (20Hz)
- **testJoystick**: 测试手柄
- **logMessage**: 日志消息
- **errorLogMessage**: 错误日志消息
- **androidLog**: Android日志

### 1.2 视频数据 (20FPS)

#### 📹 编码视频文件
- **roadEncodeData**: 道路摄像头视频 (.hevc)
- **driverEncodeData**: 驾驶员摄像头视频 (.hevc)
- **wideRoadEncodeData**: 广角摄像头视频 (.hevc)
- **qRoadEncodeData**: 高质量道路视频

#### 🎞️ 视频索引
- **roadEncodeIdx**: 道路视频索引
- **driverEncodeIdx**: 驾驶员视频索引
- **wideRoadEncodeIdx**: 广角视频索引
- **qRoadEncodeIdx**: 高质量视频索引

#### 📸 缩略图数据
- **thumbnail**: 缩略图 (1/60Hz)

### 1.3 直播流数据

#### 📺 实时流媒体
- **livestreamRoadEncodeData**: 道路直播流
- **livestreamDriverEncodeData**: 驾驶员直播流
- **livestreamWideRoadEncodeData**: 广角直播流
- **livestreamRoadEncodeIdx**: 道路直播索引
- **livestreamDriverEncodeIdx**: 驾驶员直播索引
- **livestreamWideRoadEncodeIdx**: 广角直播索引

### 1.4 自定义数据
- **customReservedRawData0-2**: 自定义原始数据

## 2. 数据存储方式

### 2.1 文件存储结构

```
/data/media/0/realdata/
├── {dongle_id}|{timestamp}--{segment}/
│   ├── rlog.bz2              # 主日志文件
│   ├── qlog.bz2              # 查询优化日志
│   ├── fcamera.hevc          # 前置摄像头视频
│   ├── dcamera.hevc          # 驾驶员摄像头视频
│   ├── ecamera.hevc          # 广角摄像头视频
│   ├── qcamera.ts            # 高质量摄像头
│   └── bootlog.bz2           # 启动日志
```

### 2.2 存储配置

#### 📊 存储参数
- **段长度**: 60秒/段
- **摄像头帧率**: 20FPS
- **视频编码**: H.265/HEVC
- **日志压缩**: bz2/zstd

#### 💾 队列大小配置
- **BIG (10MB)**: 视频数据、大型AI输出
- **MEDIUM (2MB)**: 高频CAN数据、直播流
- **SMALL (250KB)**: 大多数服务

### 2.3 数据抽取策略

不同数据类型有不同的抽取率，用于减少存储空间：

| 数据类型 | 原始频率 | 抽取率 | 实际存储频率 |
|---------|---------|--------|-------------|
| gyroscope | 104Hz | 104 | ~1Hz |
| accelerometer | 104Hz | 104 | ~1Hz |
| carState | 100Hz | 10 | ~10Hz |
| controlsState | 100Hz | 10 | ~10Hz |
| radarState | 20Hz | 5 | ~4Hz |
| modelV2 | 20Hz | None | 20Hz |

## 3. 数据流向和处理

### 3.1 数据采集流程

```
传感器/CAN → 进程 → 消息队列 → loggerd → 存储
                ↓
            实时处理 → 控制决策 → 执行器
```

### 3.2 存储管理

#### 🗂️ 自动管理
- 自动分段存储 (60秒/段)
- 磁盘空间监控
- 自动删除旧数据
- 上传到云端服务器

#### 📈 存储统计
- 实时监控存储使用率
- 统计目录文件限制: 10000个
- 统计刷新时间: 60秒

## 4. 数据用途分类

### 4.1 实时控制数据
- 车辆状态、控制指令
- 传感器数据、CAN消息
- 用于实时决策和控制

### 4.2 感知分析数据
- 摄像头图像、雷达数据
- AI模型输出、目标跟踪
- 用于环境理解和路径规划

### 4.3 监控诊断数据
- 设备状态、系统日志
- 性能指标、错误信息
- 用于系统监控和故障诊断

### 4.4 用户交互数据
- 触摸事件、用户设置
- 导航信息、音频反馈
- 用于用户体验优化

### 4.5 开发调试数据
- 调试信息、测试数据
- 性能分析、算法验证
- 用于系统开发和优化

## 5. 数据访问接口

### 5.1 实时访问
```python
import cereal.messaging as messaging

# 订阅实时数据
sm = messaging.SubMaster(['carState', 'controlsState'])
while True:
    sm.update()
    if sm.updated['carState']:
        speed = sm['carState'].vEgo
```

### 5.2 历史数据访问
```python
from openpilot.tools.lib.logreader import LogReader

# 读取历史日志
lr = LogReader("path/to/rlog.bz2")
for msg in lr.filter('carState'):
    print(f"Speed: {msg.vEgo}")
```

### 5.3 视频数据访问
```python
from openpilot.tools.lib.framereader import FrameReader

# 读取视频帧
fr = FrameReader("path/to/fcamera.hevc")
for frame in fr:
    # 处理视频帧
    pass
```

## 6. 总结

openpilot 的数据记录系统是一个完整的多模态数据采集平台，包含：

- **80+ 种消息类型**: 覆盖车辆、感知、控制、监控等各个方面
- **多种存储格式**: 二进制日志、视频文件、直播流
- **分层存储策略**: 不同重要性数据采用不同存储策略
- **实时+历史**: 既支持实时处理，也支持历史回放分析
- **完整工具链**: 从数据采集到分析可视化的完整支持

这个系统为自动驾驶的开发、测试、部署和维护提供了全面的数据支撑。