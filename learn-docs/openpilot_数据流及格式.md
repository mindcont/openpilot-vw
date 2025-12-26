# openpilot 数据流及格式

## 概述

openpilot 是一个开源的自动驾驶系统，采用分布式架构，通过消息传递机制实现各个组件之间的数据交换。本文档详细介绍了 openpilot 的数据流架构、消息格式和存储机制。

## 核心架构

### 1. 消息传递系统 (Messaging System)

openpilot 使用基于 ZeroMQ 的消息传递系统，通过 `cereal` 库实现：

- **发布-订阅模式**: 各进程通过 PubSocket 发布消息，通过 SubSocket 订阅消息
- **消息序列化**: 使用 Cap'n Proto 进行高效的消息序列化
- **队列管理**: 不同服务配置不同的队列大小（SMALL: 250KB, MEDIUM: 2MB, BIG: 10MB）

### 2. 服务配置

在 `cereal/services.py` 中定义了所有服务的配置：

```python
# 服务配置示例
"carState": (True, 100., 10),           # 记录日志, 100Hz频率, 10倍抽取
"modelV2": (True, 20., None, QueueSize.BIG),  # 大队列用于AI模型输出
"can": (True, 100., 2053, QueueSize.BIG),     # CAN总线数据
```

## 数据流架构

### 1. 主要数据流向

```
传感器数据 → 感知模块 → 决策模块 → 控制模块 → 执行器
    ↓           ↓         ↓         ↓         ↓
  camerad → modeld → plannerd → controlsd → card
```

### 2. 核心进程及数据流

#### 感知层 (Perception Layer)
- **camerad**: 摄像头数据采集
  - 输出: `roadCameraState`, `driverCameraState`, `wideRoadCameraState`
  - 格式: FrameData (图像数据 + 元数据)

- **modeld**: AI模型推理
  - 输入: 摄像头图像数据
  - 输出: `modelV2` (车道线、障碍物、路径规划)
  - 频率: 20Hz

#### 决策层 (Planning Layer)
- **plannerd**: 路径规划
  - 输入: `modelV2`, `carState`, `radarState`
  - 输出: `longitudinalPlan` (纵向规划)

- **controlsd**: 控制决策
  - 输入: `longitudinalPlan`, `carState`, `modelV2`
  - 输出: `carControl` (控制指令)

#### 执行层 (Execution Layer)
- **card**: 车辆接口
  - 输入: `carControl`
  - 输出: `carOutput`, `carState`

### 3. 数据采集与传输

#### CAN总线数据
```python
# CAN消息格式
struct CanData {
  address @0 :UInt32;    # CAN ID
  dat     @2 :Data;      # 数据载荷
  src     @3 :UInt8;     # 数据源
}
```

#### 传感器数据
```python
# 传感器事件格式
struct SensorEventData {
  sensor @1 :Int32;      # 传感器类型
  timestamp @3 :Int64;   # 时间戳
  union {
    acceleration @4 :SensorVec;  # 加速度
    gyro @7 :SensorVec;          # 陀螺仪
    magnetic @5 :SensorVec;      # 磁力计
  }
}
```

## 消息格式规范

### 1. 统一事件格式

所有消息都封装在 `Event` 结构中：

```capnp
struct Event {
  logMonoTime @0 :UInt64;  # 单调时间戳
  valid @67 :Bool = true;  # 消息有效性
  
  union {
    # 车辆状态
    carState @22 :Car.CarState;
    carControl @23 :Car.CarControl;
    
    # AI模型输出
    modelV2 @75 :ModelDataV2;
    
    # 传感器数据
    can @5 :List(CanData);
    gyroscope @99 :SensorEventData;
    
    # 系统状态
    deviceState @6 :DeviceState;
    # ... 更多消息类型
  }
}
```

### 2. 关键消息类型

#### 车辆状态 (CarState)
```capnp
struct CarState {
  vEgo @0 :Float32;              # 车速 (m/s)
  steeringAngleDeg @1 :Float32;  # 方向盘角度
  gas @2 :Float32;               # 油门踏板
  brake @3 :Float32;             # 刹车踏板
  cruiseState @4 :CruiseState;   # 巡航状态
  # ... 更多字段
}
```

#### AI模型输出 (ModelV2)
```capnp
struct ModelDataV2 {
  frameId @0 :UInt32;           # 帧ID
  position @4 :XYZTData;        # 预测位置
  velocity @6 :XYZTData;        # 预测速度
  laneLines @8 :List(XYZTData); # 车道线
  leads @11 :List(LeadDataV3);  # 前车信息
  action @26: Action;           # 控制动作
}
```

#### 控制指令 (CarControl)
```capnp
struct CarControl {
  enabled @0 :Bool;             # 系统使能
  latActive @1 :Bool;           # 横向控制激活
  longActive @2 :Bool;          # 纵向控制激活
  actuators @3 :Actuators;      # 执行器指令
  
  struct Actuators {
    accel @0 :Float32;          # 加速度指令
    curvature @1 :Float32;      # 曲率指令
    torque @2 :Float32;         # 转向力矩
  }
}
```

## 数据存储与日志

### 1. 日志系统架构

- **loggerd**: 主日志进程，负责收集和存储所有消息
- **encoderd**: 视频编码进程，处理摄像头数据压缩
- **uploader**: 上传进程，将日志上传到服务器

### 2. 日志格式

#### 分段存储
- 每60秒创建一个新的日志段 (segment)
- 文件命名: `{route_name}--{segment_number}`
- 格式: 
  - `rlog`: 原始日志文件 (所有消息)
  - `qlog`: 压缩日志文件 (抽取后的消息)
  - `fcamera.hevc`: 前置摄像头视频
  - `dcamera.hevc`: 驾驶员监控摄像头视频

#### 压缩与编码
```cpp
// 视频编码配置
struct EncoderInfo {
  const char* publish_name;     # 发布名称
  const char* filename;         # 文件名
  int fps;                      # 帧率
  bool record;                  # 是否记录
  bool include_audio;           # 是否包含音频
}
```

### 3. 数据读取

使用 `LogReader` 类读取日志：

```python
from openpilot.tools.lib.logreader import LogReader

# 读取日志
lr = LogReader("route_name/segment_number")

# 过滤特定消息类型
car_states = list(lr.filter('carState'))

# 获取时间序列数据
ts = lr.time_series
```

## 实时数据处理

### 1. SubMaster/PubMaster 模式

```python
# 订阅多个消息
sm = SubMaster(['carState', 'modelV2', 'longitudinalPlan'])

# 发布消息
pm = PubMaster(['carControl'])

# 更新和处理
while True:
    sm.update(timeout=100)  # 等待新消息
    
    if sm.updated['carState']:
        # 处理车辆状态更新
        process_car_state(sm['carState'])
    
    # 发布控制指令
    cc = create_car_control()
    pm.send('carControl', cc)
```

### 2. 频率控制与同步

- **Ratekeeper**: 控制进程执行频率
- **频率检查**: 监控消息频率是否正常
- **时间同步**: 使用单调时间戳确保时序一致性

```python
# 100Hz控制循环
rk = Ratekeeper(100)
while True:
    # 处理逻辑
    process_control_loop()
    
    # 维持频率
    rk.monitor_time()
```

## 数据质量保证

### 1. 消息验证
- **valid字段**: 每个消息包含有效性标志
- **频率检查**: 监控消息接收频率
- **时间戳验证**: 检查消息时序合理性

### 2. 错误处理
- **超时机制**: 消息接收超时处理
- **降级策略**: 传感器故障时的备用方案
- **安全检查**: 关键参数的边界检查

## 性能优化

### 1. 内存管理
- **零拷贝**: 使用共享内存减少数据拷贝
- **队列大小**: 根据数据类型配置合适的队列大小
- **内存池**: 复用消息对象减少分配开销

### 2. 网络优化
- **消息压缩**: 大数据使用压缩传输
- **批量处理**: 合并小消息减少网络开销
- **优先级**: 关键消息优先传输

## 扩展与定制

### 1. 自定义消息类型

在 `cereal/custom.capnp` 中定义自定义消息：

```capnp
struct CustomReserved0 {
  # 自定义字段
  customData @0 :Data;
  customValue @1 :Float32;
}
```

### 2. 新增服务

1. 在 `services.py` 中添加服务配置
2. 在 `process_config.py` 中添加进程定义
3. 实现消息处理逻辑

## 总结

openpilot 的数据流架构具有以下特点：

- **模块化设计**: 各组件独立运行，通过消息通信
- **高效传输**: 使用 Cap'n Proto 和 ZeroMQ 实现高效消息传递
- **完整记录**: 所有关键数据都被记录用于分析和调试
- **实时性保证**: 通过频率控制和优先级机制保证实时性
- **可扩展性**: 支持自定义消息类型和服务扩展

这种架构使得 openpilot 能够处理复杂的自动驾驶任务，同时保持系统的稳定性和可维护性。