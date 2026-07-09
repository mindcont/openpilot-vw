# openpilot 摄像头启动配置指南

## 概述

openpilot 支持两种摄像头模式：硬件摄像头(camerad)和USB摄像头(webcamerad)。本文档详细说明PC模式下摄像头进程的启动条件和配置方法。

## 摄像头进程类型

### 1. camerad (硬件摄像头)
```python
NativeProcess("camerad", "system/camerad", ["./camerad"], driverview, enabled=not WEBCAM)
```
- **适用场景**: openpilot专用硬件设备
- **启动条件**: `USE_WEBCAM` 未设置 且 满足 `driverview` 条件
- **实现语言**: C++ (Native进程)

### 2. webcamerad (USB摄像头)
```python
PythonProcess("webcamerad", "tools.webcam.camerad", driverview, enabled=WEBCAM)
```
- **适用场景**: PC开发环境，使用USB摄像头
- **启动条件**: `USE_WEBCAM=1` 且 满足 `driverview` 条件
- **实现语言**: Python

## 启动条件详解

### driverview 函数逻辑
```python
def driverview(started: bool, params: Params, CP: car.CarParams) -> bool:
    return started or params.get_bool("IsDriverViewEnabled")
```

**启动条件**:
- `started=True`: 车辆处于上路状态
- `IsDriverViewEnabled=True`: 驾驶员视图模式已启用

### 环境变量控制
```python
WEBCAM = os.getenv("USE_WEBCAM") is not None
```

## PC模式摄像头配置

### 方法1: 启用驾驶员视图模式 (推荐)

**步骤1: 设置参数**
```bash
python3 enable_camera.py
```

**enable_camera.py 脚本内容**:
```python
from openpilot.common.params import Params

params = Params()
params.put_bool("IsDriverViewEnabled", True)
print("✓ 已启用驾驶员视图模式")
```

**步骤2: 启动openpilot**
```bash
export USE_WEBCAM=1
./start_openpilot.sh
```

### 方法2: 模拟车辆上路状态

**环境变量配置**:
```bash
export USE_WEBCAM=1
export FINGERPRINT="VOLKSWAGEN_GOLF_MK7"  # 速腾用代理指纹(MQB平台)
export PASSIVE=0           # 非被动模式
./start_openpilot.sh
```

### 方法3: 修改启动条件 (开发用)

**修改 process_config.py**:
```python
def driverview(started: bool, params: Params, CP: car.CarParams) -> bool:
    # PC模式下总是启用摄像头
    if os.getenv("USE_WEBCAM") and os.getenv("PC"):
        return True
    return started or params.get_bool("IsDriverViewEnabled")
```

## 摄像头设备配置

### 环境变量设置
```bash
# 摄像头设备配置
export USE_WEBCAM=1           # 启用USB摄像头模式
export ROAD_CAM="2"           # 主摄像头设备 /dev/video2
export WIDE_CAM="0"           # 广角摄像头设备 /dev/video0 (可选)
export DRIVER_CAM="4"         # 驾驶员监控摄像头 /dev/video4 (可选)
```

### 设备检测脚本
```python
import cv2

def test_camera_devices():
    """测试可用的摄像头设备"""
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"✓ /dev/video{i}: {frame.shape}")
            else:
                print(f"✗ /dev/video{i}: 无法读取帧")
        else:
            print(f"✗ /dev/video{i}: 设备不存在")
        cap.release()

test_camera_devices()
```

## 启动状态检查

### Manager 启动日志
```
[MANAGER] 📹 摄像头已启用: webcamerad 将启动 (USE_WEBCAM=1, IsDriverViewEnabled=True)
[MANAGER] 🐍 启动进程: webcamerad (Python: tools.webcam.camerad)
```

### 摄像头进程验证
```bash
# 检查进程是否运行
ps aux | grep webcamerad

# 检查摄像头设备占用
lsof /dev/video*

# 查看进程状态
./view_logs.sh -c | grep webcamerad
```

## 故障排除

### 常见问题

**1. 摄像头进程未启动**
```
原因: driverview 条件不满足
解决: python3 enable_camera.py
```

**2. 设备权限问题**
```bash
# 检查设备权限
ls -l /dev/video*

# 修复权限
sudo chmod 666 /dev/video*
```

**3. 设备被占用**
```bash
# 查看占用进程
sudo lsof /dev/video2

# 停止占用进程
sudo pkill -f video
```

**4. 摄像头参数错误**
```python
# 检查摄像头支持的格式
import cv2
cap = cv2.VideoCapture(2)
print("支持的分辨率:")
for width, height in [(640,480), (1280,720), (1920,1080)]:
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    print(f"设置 {width}x{height} -> 实际 {actual_w}x{actual_h}")
```

### 调试命令

**查看摄像头配置**:
```bash
# 查看当前参数
python3 -c "
from openpilot.common.params import Params
p = Params()
print('IsDriverViewEnabled:', p.get_bool('IsDriverViewEnabled'))
print('USE_WEBCAM:', os.getenv('USE_WEBCAM'))
"

# 查看设备信息
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video2 --list-formats-ext
```

**实时监控**:
```bash
# 监控摄像头进程
watch -n 1 'ps aux | grep -E "(camerad|webcamerad)"'

# 监控设备使用
watch -n 1 'lsof /dev/video* 2>/dev/null'
```

## 性能优化

### 摄像头参数调优
```python
# tools/webcam/camera.py 中的配置
self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280.0)   # 分辨率宽度
self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720.0)   # 分辨率高度
self.cap.set(cv2.CAP_PROP_FPS, 25.0)             # 帧率
self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)         # 缓冲区大小
```

### 系统优化
```bash
# USB带宽优化
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="xxxx", ATTR{power/control}="on"' | sudo tee /etc/udev/rules.d/99-usb-camera.rules

# CPU优化
export OMP_NUM_THREADS=1  # 限制OpenMP线程数
```

## 配置模板

### 完整启动配置
```bash
#!/bin/bash
# PC模式摄像头启动配置

# 基础环境
export PC=1
export USE_WEBCAM=1
export PASSIVE=1
export NOBOARD=1

# 摄像头设备
export ROAD_CAM="2"
export DRIVER_CAM="0"

# 启用驾驶员视图
python3 -c "
from openpilot.common.params import Params
Params().put_bool('IsDriverViewEnabled', True)
"

# 启动openpilot
./start_openpilot.sh
```

### 开发调试配置
```bash
# 调试模式配置
export LOGPRINT=debug
export BLOCK="loggerd,encoderd"  # 跳过不必要的进程

# 摄像头调试
export WEBCAM_WIDTH=640
export WEBCAM_HEIGHT=480
export WEBCAM_FPS=15

./start_openpilot.sh
```

## 总结

openpilot 摄像头启动需要满足两个条件：
1. **环境变量**: `USE_WEBCAM=1` (PC模式)
2. **启动条件**: `IsDriverViewEnabled=True` 或 `started=True`

推荐使用 `python3 enable_camera.py` 来启用驾驶员视图模式，这是最简单可靠的方法。配置完成后，重新启动 openpilot 即可看到 webcamerad 进程正常运行。