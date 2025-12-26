# OpenPilot Tools 工具集使用指南

## 概述
OpenPilot 提供了丰富的工具集，用于开发、调试、分析和测试自动驾驶系统。本文档详细介绍各类工具的功能、使用方法和应用场景。

## 1. 数据分析与可视化工具

### 1.1 Cabana - CAN 数据分析工具

#### 功能
- 查看和分析原始 CAN 数据
- 创建和编辑 DBC 文件（CAN 字典）
- 实时 CAN 消息监控
- 与 opendbc 项目集成

#### 使用方法
```bash
# 演示模式
./cabana --demo

# 加载特定路线
./cabana "a2a0ccea32023010|2023-07-27--13-01-19"

# 多摄像头模式
./cabana "route_name" --dcam --ecam

# 从设备实时流式传输
./cabana --zmq <device_ip>

# 从 Panda 读取
./cabana --panda
```

#### 应用场景
- **车辆移植**: 分析新车型的 CAN 信号
- **故障诊断**: 实时监控 CAN 总线异常
- **DBC 开发**: 创建和维护 CAN 数据库文件
- **信号逆向**: 分析未知 CAN 信号含义

### 1.2 PlotJuggler - 时序数据可视化

#### 功能
- 可视化 openpilot 日志中的时序数据
- 支持实时数据流
- 预定义布局模板
- 多种数据源支持

#### 使用方法
```bash
# 安装
./juggle.py --install

# 分析路线数据
./juggle.py "route_name"

# 实时流模式
./juggle.py --stream

# 使用预定义布局
./juggle.py --demo --layout=layouts/tuning.xml

# 包含 CAN 数据
./juggle.py "route_name" --can
```

#### 应用场景
- **性能调优**: 分析控制系统性能
- **故障分析**: 可视化系统异常行为
- **实时监控**: 监控车辆实时状态
- **算法验证**: 验证控制算法效果

### 1.3 Replay - 驾驶数据回放工具

#### 功能
- 模拟完整的驾驶会话
- 支持本地和远程路线
- 消息过滤和控制
- 多种输出模式

#### 使用方法
```bash
# 认证
python3 tools/lib/auth.py

# 回放远程路线
./replay "route_name"

# 演示模式
./replay --demo

# 本地路线回放
./replay "route_name" --data_dir="/path/to/route"

# ZMQ 模式
ZMQ=1 ./replay "route_name"

# 配合 UI 使用
./replay "route_name" &
cd selfdrive/ui && ./ui.py
```

#### 应用场景
- **算法测试**: 在历史数据上测试新算法
- **系统调试**: 重现和分析问题场景
- **性能评估**: 评估系统在不同场景下的表现
- **开发验证**: 验证代码修改的影响

## 2. 开发与调试工具

### 2.1 Joystick - 手动控制工具

#### 功能
- 使用手柄或键盘控制车辆
- 网络远程控制
- 实时状态显示
- 调试模式支持

#### 使用方法
```bash
# 键盘控制（在设备上）
./joystick_control.py --keyboard

# 手柄控制（设备上）
./joystick_control.py

# 网络控制（笔记本）
# 1. 在设备上设置参数
echo -n "1" > /data/params/d/JoystickDebugMode

# 2. 启动桥接
cereal/messaging/bridge {LAPTOP_IP} testJoystick

# 3. 在笔记本上运行
export ZMQ=1
./joystick_control.py
```

#### 应用场景
- **控制调试**: 手动测试控制系统响应
- **安全测试**: 在受控环境下测试系统
- **算法验证**: 验证控制算法的准确性
- **故障排查**: 排查控制系统问题

### 2.2 Car Porting - 车辆移植工具

#### 功能
- 自动指纹识别
- 车辆接口测试
- CAN 信号分析
- Jupyter 笔记本示例

#### 使用方法
```bash
# 自动指纹识别
python3 auto_fingerprint.py 'route_name' 'PLATFORM'

# 车辆接口测试
pytest selfdrive/car/tests/test_car_interfaces.py -k brand_name

# 车辆模型测试
python3 test_car_model.py 'route_name'

# Jupyter 笔记本
jupyter notebook
```

#### 应用场景
- **新车移植**: 为新车型创建支持
- **信号分析**: 分析车辆 CAN 信号
- **接口验证**: 验证车辆接口正确性
- **故障诊断**: 诊断移植过程中的问题

## 3. 仿真与测试工具

### 3.1 Simulator - 仿真环境

#### 功能
- MetaDrive 仿真器集成
- 虚拟驾驶环境
- 控制接口测试
- 多种场景支持

#### 使用方法
```bash
# 启动 openpilot
./launch_openpilot.sh

# 启动仿真器桥接
./run_bridge.py

# 高质量模式
./run_bridge.py --high_quality

# 双摄像头模式
./run_bridge.py --dual_camera
```

#### 控制说明
- `1`: 巡航恢复/加速
- `2`: 巡航设置/减速  
- `3`: 巡航取消
- `r`: 重置仿真
- `i`: 切换点火
- `q`: 退出
- `wasd`: 手动控制

#### 应用场景
- **算法开发**: 在安全环境中开发算法
- **场景测试**: 测试各种驾驶场景
- **性能评估**: 评估系统性能
- **教育培训**: 学习和演示系统功能

### 3.2 Webcam - PC 摄像头测试

#### 功能
- 使用 PC 摄像头运行 openpilot
- 硬件连接测试
- 校准和调试
- 开发环境搭建

#### 使用方法
```bash
# 基本运行
USE_WEBCAM=1 system/manager/manager.py

# 指定摄像头
USE_WEBCAM=1 ROAD_CAM=1 system/manager/manager.py

# 多摄像头
USE_WEBCAM=1 ROAD_CAM=0 DRIVER_CAM=1 WIDE_CAM=2 system/manager/manager.py
```

#### 硬件要求
- Ubuntu 24.04 或 macOS
- GPU（推荐）
- USB 摄像头（720p+，78° FOV）
- Car harness 和 panda
- USB-A 连接线

#### 应用场景
- **开发测试**: 在 PC 上开发和测试
- **算法验证**: 验证视觉算法
- **硬件调试**: 测试硬件连接
- **教育演示**: 演示系统功能

## 4. 专用工具

### 4.1 Body Teleop - 远程操控

#### 功能
- 网页界面远程控制
- 实时视频流
- 控制状态监控
- WebRTC 通信

#### 使用方法
```bash
# 启动 Web 服务
python3 web.py

# 访问 Web 界面
# 打开浏览器访问显示的地址
```

#### 应用场景
- **远程操控**: 远程控制 comma body
- **监控调试**: 远程监控设备状态
- **演示展示**: 远程演示系统功能

### 4.2 Longitudinal Maneuvers - 纵向机动分析

#### 功能
- 纵向控制性能分析
- 机动行为检测
- 性能报告生成
- 数据可视化

#### 使用方法
```bash
# 启动机动检测
python3 maneuversd.py

# 生成分析报告
python3 generate_report.py
```

#### 应用场景
- **性能分析**: 分析纵向控制性能
- **行为研究**: 研究驾驶行为模式
- **系统优化**: 优化纵向控制算法

### 4.3 Profiling - 性能分析工具

#### 功能
- 系统性能监控
- CPU/GPU 使用分析
- 内存使用监控
- 性能瓶颈识别

#### 工具集
- **clpeak**: OpenCL 性能测试
- **perfetto**: 系统跟踪分析
- **py-spy**: Python 性能分析
- **snapdragon**: 高通平台分析

#### 使用方法
```bash
# OpenCL 性能测试
cd profiling/clpeak && ./build.sh

# 系统跟踪
cd profiling/perfetto && ./record.sh

# Python 性能分析
cd profiling/py-spy && ./profile.sh

# 中断监控
./watch-irqs.sh
```

#### 应用场景
- **性能优化**: 识别和优化性能瓶颈
- **资源监控**: 监控系统资源使用
- **问题诊断**: 诊断性能问题
- **基准测试**: 建立性能基准

## 5. 辅助脚本工具

### 5.1 Scripts - 实用脚本集

#### 功能集合
- **adb_ssh.sh**: ADB SSH 连接
- **extract_audio.py**: 音频提取
- **fetch_image_from_route.py**: 路线图像获取
- **setup_ssh_keys.py**: SSH 密钥设置
- **ssh.py**: SSH 连接工具

#### 使用示例
```bash
# SSH 连接设置
./setup_ssh_keys.py

# 从路线提取图像
python3 fetch_image_from_route.py "route_name"

# 音频提取
python3 extract_audio.py input.mp4 output.wav
```

### 5.2 Lib - 通用库

#### 核心模块
- **api.py**: API 接口
- **auth.py**: 认证管理
- **logreader.py**: 日志读取
- **route.py**: 路线管理
- **cache.py**: 缓存管理

#### 应用场景
- **工具开发**: 为其他工具提供基础功能
- **数据处理**: 处理 openpilot 数据
- **API 访问**: 访问 comma.ai 服务

## 6. 工具使用最佳实践

### 6.1 开发流程
1. **环境搭建**: 使用 setup.sh 配置开发环境
2. **数据获取**: 使用 auth.py 认证并获取数据
3. **数据分析**: 使用 Cabana 和 PlotJuggler 分析
4. **算法开发**: 使用 Simulator 和 Webcam 开发
5. **测试验证**: 使用 Replay 和 Joystick 测试
6. **性能优化**: 使用 Profiling 工具优化

### 6.2 故障排查流程
1. **日志分析**: 使用 PlotJuggler 查看系统日志
2. **CAN 分析**: 使用 Cabana 分析 CAN 数据
3. **场景重现**: 使用 Replay 重现问题场景
4. **手动测试**: 使用 Joystick 手动测试
5. **性能分析**: 使用 Profiling 分析性能问题

### 6.3 车辆移植流程
1. **数据收集**: 收集目标车辆的 CAN 数据
2. **信号分析**: 使用 Cabana 分析 CAN 信号
3. **接口开发**: 开发车辆接口代码
4. **测试验证**: 使用 car_porting 工具测试
5. **集成测试**: 使用 Simulator 进行集成测试

## 7. 系统要求

### 7.1 基本要求
- **操作系统**: Ubuntu 24.04 或 macOS
- **Python**: 3.8+
- **内存**: 8GB+ RAM
- **存储**: 50GB+ 可用空间

### 7.2 推荐配置
- **CPU**: 多核处理器
- **GPU**: 支持 OpenCL 的 GPU
- **网络**: 稳定的网络连接
- **硬件**: Panda 和相关硬件

## 8. 常见问题解决

### 8.1 环境问题
```bash
# 重新设置环境
./tools/op.sh setup

# 激活虚拟环境
source .venv/bin/activate

# 重新构建
scons -u -j$(nproc)
```

### 8.2 权限问题
```bash
# 设置设备权限
sudo usermod -a -G dialout $USER

# 重新登录或重启
```

### 8.3 网络问题
```bash
# 检查网络连接
ping connect.comma.ai

# 重新认证
python3 tools/lib/auth.py
```

## 总结

OpenPilot 工具集提供了完整的开发、测试和分析环境，涵盖了从数据收集到算法部署的整个流程。合理使用这些工具可以大大提高开发效率，降低开发难度，确保系统的可靠性和安全性。

每个工具都有其特定的应用场景和优势，开发者应根据具体需求选择合适的工具组合，形成高效的工作流程。