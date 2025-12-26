# MetaDrive 仿真接口文档

## 概述

MetaDrive 是 openpilot 使用的3D驾驶仿真环境，通过桥接模式与 openpilot 系统集成。本文档详细说明了 MetaDrive 仿真接口的架构、数据流和调用机制。

## 架构设计

### 1. 多进程架构

```
主进程 (SimulatorBridge)
├── MetaDrive进程 (metadrive_process)
├── 模拟车辆线程 (simulated_car_thread) - 100Hz
└── 模拟传感器线程 (simulated_camera_thread) - 20Hz
```

### 2. 核心组件

#### MetaDriveBridge (桥接器)
- **继承**: `SimulatorBridge`
- **功能**: 配置和启动仿真环境
- **频率**: 100Hz 主循环

#### MetaDriveWorld (世界管理器)
- **继承**: `World`
- **功能**: 管理仿真世界状态和进程通信
- **特性**: 多进程间数据同步

#### MetaDrive进程 (独立进程)
- **功能**: 运行实际的3D仿真环境
- **引擎**: 基于 Panda3D 的 MetaDriveEnv
- **频率**: 100Hz 物理仿真，20Hz 图像渲染

## 数据流架构

### 1. 进程间通信 (IPC)

```python
# 管道通信
controls_send/recv     # 控制指令传输
simulation_state_send/recv  # 仿真状态传输
vehicle_state_send/recv     # 车辆状态传输

# 共享内存
camera_array          # 道路摄像头图像 (W×H×3)
wide_camera_array     # 广角摄像头图像 (W×H×3)

# 事件同步
exit_event           # 退出事件
op_engaged          # openpilot激活事件
image_lock          # 图像访问锁
```

### 2. 数据结构

#### 车辆状态 (metadrive_vehicle_state)
```python
@dataclass
class VehicleState:
    velocity: Vec3        # 速度向量 (x, y, z)
    position: Tuple       # 位置坐标 (x, y)
    bearing: float        # 航向角 (度)
    steering_angle: float # 转向角 (度)
```

#### 仿真状态 (metadrive_simulation_state)
```python
@dataclass
class SimulationState:
    running: bool         # 仿真运行状态
    done: bool           # 是否完成
    done_info: dict      # 完成信息 (碰撞、超时等)
```

#### 控制指令
```python
# 发送到MetaDrive的控制数组
controls = [
    steer_angle,    # 转向角 (-1 到 1)
    throttle_brake  # 油门/刹车 (-1 到 1)
]
```

## 仿真环境配置

### 1. 地图生成

```python
def create_map(track_size=60):
    """创建封闭赛道地图"""
    return {
        'type': MapGenerateMethod.PG_MAP_FILE,
        'lane_num': 2,           # 车道数量
        'lane_width': 4.5,       # 车道宽度(米)
        'config': [
            None,                # 起始点
            straight_block(60),  # 直道段
            curve_block(120, 90), # 弯道段
            # ... 更多路段
        ]
    }
```

### 2. 传感器配置

```python
sensors = {
    "rgb_road": (RGBCameraRoad, W, H),  # 道路摄像头
    "rgb_wide": (RGBCameraWide, W, H)   # 广角摄像头 (可选)
}

# 摄像头参数
RGBCameraRoad: FOV=40°, Near=0.1m
RGBCameraWide: FOV=120°, Near=0.1m
```

### 3. 物理参数

```python
config = {
    'physics_world_step_size': TICKS_PER_FRAME/100,  # 物理步长
    'decision_repeat': 1,                            # 决策重复次数
    'traffic_density': 0.0,                          # 交通密度
    'vehicle_config': {
        'enable_reverse': False,                     # 禁用倒车
        'max_speed_km_h': 1000,                     # 最大速度
        'image_source': "rgb_road"                   # 主图像源
    }
}
```

## 接口调用流程

### 1. 初始化序列

```python
# 1. 创建桥接器
bridge = MetaDriveBridge(dual_camera=True, high_quality=False)

# 2. 生成仿真世界
world = bridge.spawn_world(queue)

# 3. 启动MetaDrive进程
metadrive_process.start()

# 4. 等待初始化完成
vehicle_state = vehicle_state_recv.recv()  # 阻塞等待首个状态
```

### 2. 运行时循环 (100Hz)

```python
while running:
    # 读取openpilot控制指令
    if controls_recv.poll():
        steer_angle, throttle, brake = controls_recv.recv()
    
    # 应用控制到仿真车辆
    metadrive_controls = convert_controls(steer_angle, throttle, brake)
    env.step(metadrive_controls)
    
    # 发送车辆状态给openpilot
    vehicle_state = get_vehicle_state()
    vehicle_state_send.send(vehicle_state)
    
    # 更新摄像头图像 (20Hz)
    if frame % 5 == 0:
        update_camera_images()
```

### 3. 图像处理流程

```python
def get_cam_as_rgb(cam_name):
    """获取摄像头RGB图像"""
    cam = env.engine.sensors[cam_name]
    
    # 设置摄像头位置 (模拟comma 3X位置)
    cam.get_cam().setPos(C3_POSITION)  # (0, 0, 1.22m)
    cam.get_cam().setHpr(C3_HPR)       # (0, 0, 0)
    
    # 渲染并获取图像
    img = cam.perceive(to_float=False)
    
    # GPU到CPU转换 (如果使用CUDA)
    if hasattr(img, 'get'):
        img = img.get()  # CuPy -> NumPy
    
    return img

# 图像数据流
MetaDrive渲染 → GPU纹理 → CPU内存 → 共享内存 → openpilot
```

## 控制接口

### 1. 手动控制命令

通过队列发送字符串命令：

```python
# 转向控制
"steer_{angle}"      # angle: -1.0 到 1.0

# 油门/刹车控制  
"throttle_{value}"   # value: 0.0 到 1.0
"brake_{value}"      # value: 0.0 到 1.0

# 巡航控制
"cruise_up"          # 加速/恢复
"cruise_down"        # 减速/设定
"cruise_cancel"      # 取消
"cruise_main"        # 主开关

# 转向灯
"blinker_left"       # 左转向灯
"blinker_right"      # 右转向灯

# 系统控制
"ignition"           # 切换点火状态
"reset"              # 重置仿真
"quit"               # 退出仿真
```

### 2. openpilot自动控制

```python
# 从openpilot获取控制指令
if simulator_state.is_engaged:
    # 纵向控制
    throttle = clip(carControl.actuators.accel / 1.6, 0.0, 1.0)
    brake = clip(-carControl.actuators.accel / 4.0, 0.0, 1.0)
    
    # 横向控制
    steer_angle = carControl.actuators.steeringAngleDeg
    
    # 转换为MetaDrive格式
    steer_metadrive = steer_angle / (MAX_STEERING * steer_ratio)
    throttle_brake = throttle if throttle > 0 else -brake
```

## 传感器数据接口

### 1. 摄像头数据

```python
# 图像规格
WIDTH = 1928   # 像素宽度
HEIGHT = 1208  # 像素高度
CHANNELS = 3   # RGB通道

# 数据格式
image_data = np.uint8[HEIGHT, WIDTH, CHANNELS]

# 访问方式
with image_lock:
    road_image = shared_camera_array.reshape((H, W, 3))
    wide_image = shared_wide_array.reshape((H, W, 3))
```

### 2. 车辆传感器

```python
# GPS数据
state.gps.from_xy(vehicle.position)

# IMU数据  
state.velocity = vehicle.velocity      # 速度向量
state.bearing = vehicle.heading_theta  # 航向角
state.steering_angle = vehicle.steering # 转向角

# 状态标志
state.valid = True                     # 数据有效性
state.ignition = True                  # 点火状态
state.is_engaged = openpilot.active    # 系统激活状态
```

## 性能优化

### 1. 渲染优化

```python
config = {
    'use_render': False,              # 禁用可视化渲染
    'preload_models': False,          # 不预加载模型
    'show_logo': False,               # 不显示logo
    'anisotropic_filtering': False,   # 禁用各向异性过滤
    'image_on_cuda': True,            # 启用CUDA图像处理
}
```

### 2. 物理仿真优化

```python
# 物理步长设置
physics_step = TICKS_PER_FRAME / 100  # 5/100 = 0.05s

# 频率控制
TICKS_PER_FRAME = 5    # 每5个tick更新一次图像
simulation_hz = 100    # 仿真频率
camera_hz = 20         # 摄像头频率
```

### 3. 内存管理

```python
# 共享内存数组
camera_array = Array(ctypes.c_uint8, W*H*3)
wide_camera_array = Array(ctypes.c_uint8, W*H*3)

# 零拷贝图像访问
road_image = np.frombuffer(camera_array.get_obj(), dtype=np.uint8)
```

## 测试和调试

### 1. 测试模式

```python
# 启用测试模式
test_run = True
test_duration = 60.0  # 测试时长(秒)

# 失败条件检测
- out_of_lane: 车辆偏离车道
- timeout: 超过测试时长
- vehicle_not_moving: 车辆长时间不移动
- crash: 碰撞检测
```

### 2. 状态监控

```python
# 实时状态输出
print(f"""
State:
Ignition: {simulator_state.ignition}
Engaged: {simulator_state.is_engaged}
Position: {vehicle.position}
Speed: {vehicle.velocity}
""")
```

## 集成示例

### 1. 基本使用

```python
from openpilot.tools.sim.bridge.metadrive import MetaDriveBridge

# 创建桥接器
bridge = MetaDriveBridge(
    dual_camera=True,      # 启用双摄像头
    high_quality=False,    # 低质量模式(性能优先)
    test_duration=60.0,    # 测试时长
    test_run=False         # 非测试模式
)

# 启动仿真
process = bridge.run(queue)
```

### 2. 自定义地图

```python
def create_custom_map():
    return {
        'type': MapGenerateMethod.PG_MAP_FILE,
        'config': [
            None,
            straight_block(100),    # 100米直道
            curve_block(50, 45),    # 45度弯道
            straight_block(200),    # 200米直道
        ]
    }
```

## 故障处理

### 1. 常见问题

- **CUDA内存不足**: 设置 `image_on_cuda=False`
- **进程通信超时**: 检查管道连接状态
- **图像渲染失败**: 验证显卡驱动和OpenGL支持

### 2. 调试工具

```python
# 启用调试输出
config['use_render'] = True        # 显示3D窗口
config['show_logo'] = True         # 显示MetaDrive logo

# 性能监控
rk = Ratekeeper(100)
print(f"Frame rate: {rk.frame_rate}")
```

## 扩展开发

### 1. 自定义传感器

```python
class CustomCamera(CopyRamRGBCamera):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lens = self.get_lens()
        lens.setFov(60)        # 自定义视场角
        lens.setNear(0.05)     # 自定义近裁剪面
```

### 2. 自定义车辆行为

```python
def custom_vehicle_config():
    return {
        'max_speed_km_h': 120,     # 最大速度
        'max_steering': 40,        # 最大转向角
        'wheel_friction': 0.8,     # 轮胎摩擦系数
    }
```

## 总结

MetaDrive 仿真接口通过以下机制实现与 openpilot 的集成：

1. **多进程架构**: 隔离仿真环境，避免阻塞主系统
2. **高效通信**: 使用管道和共享内存实现低延迟数据传输
3. **实时同步**: 通过频率控制器保证时序一致性
4. **模块化设计**: 支持自定义地图、传感器和车辆配置
5. **性能优化**: GPU加速渲染和零拷贝内存访问

这种设计使得 openpilot 能够在虚拟环境中进行安全的测试和开发，同时保持与真实硬件相似的数据接口和控制逻辑。