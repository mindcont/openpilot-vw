# openpilot 日志系统

> 本文合并自「日志层次说明」「日志数据结构」「日志系统详解」三篇，涵盖日志的
> 层次划分、数据结构、存储位置与运维。
>
> **路径约定**：openpilot 原生 PC 模式默认写入 `~/.comma/`，设备（AGNOS）写入
> `/data/`。**本项目（openpilot-vw）启动脚本统一使用 `/data`**：
> `SWAGLOG_DIR=/data/logs/YYYY-MM-DD`、`LOG_ROOT=/data/media/0/realdata/YYYY-MM-DD`。
> 下文以项目实际的 `/data` 路径为准。

## 一、日志的三个层次

| 层次 | 位置 | 内容 |
|------|------|------|
| ① 控制台输出 (stdout/stderr) | 终端 | 进程启动信息、实时状态、print()、含 ANSI 颜色，不自动落盘 |
| ② swaglog 系统日志 | `/data/logs/swaglog.*` | `cloudlog.info/debug/warning/error`，结构化日志 |
| ③ 数据记录日志 | `/data/media/0/realdata/*/rlog.bz2` | 所有 cereal 消息、CAN、传感器、系统状态 |

控制台示例：
```
manager start
🟢pandad 🟢ui 🟢logmessaged 🔴modeld
```

swaglog 级别控制：
```bash
export LOGPRINT=debug    # 控制台也显示这些日志
export LOGPRINT=info     # 只显示 info 及以上
export LOGPRINT=warning  # 只显示警告和错误
```

### 捕获控制台日志的方法

```bash
# 方法1: tee 同时输出到终端和文件
./op 2>&1 | tee /data/logs/console.log

# 方法2: 重定向到文件
./op > /data/logs/console.log 2>&1

# 方法3: script 记录整个会话
script -c "./op" /data/logs/session.log

# 方法4: 启动脚本自动记录（本项目 start_openpilot.sh 已采用）
exec ./launch_openpilot.sh 2>&1 | tee "$SWAGLOG_DIR/console_$(date +%Y%m%d_%H%M%S).log"
```

## 二、数据日志文件格式

- `.rlog.bz2`：压缩二进制日志（主格式，所有 cereal 消息）
- `.qlog.bz2`：查询优化日志（抽样，用于快速预览/上传）
- `.rlog.zst`：Zstandard 压缩格式
- 序列化：**Cap'n Proto**（零拷贝、高性能），消息类型由 `cereal/log.capnp` 定义
- 不支持直接解压为文本

### 基本消息结构
```json
{
  "logMonoTime": 1690464079123456789,  // 纳秒级时间戳
  "which": "carState",                 // 消息类型
  "carState": { ... }                  // 消息内容
}
```

### carState 示例
```json
{
  "which": "carState",
  "carState": {
    "vEgo": 15.2,                 // 车辆速度 (m/s)
    "aEgo": 0.1,                  // 加速度 (m/s²)
    "steeringAngleDeg": -2.5,     // 转向角 (度)
    "steeringTorque": 1.2,        // 方向盘力矩 (Nm)
    "brake": 0.0, "gas": 0.3,     // 踏板 (0-1)
    "gearShifter": "drive",       // 档位
    "wheelSpeeds": {"fl": 15.1, "fr": 15.3, "rl": 15.0, "rr": 15.2},
    "cruiseState": {"enabled": true, "speed": 16.7, "available": true}
  }
}
```

## 三、主要消息类型与频率

| 消息类型 | 描述 | 频率 | 间隔 |
|---------|------|------|------|
| carState | 车辆状态（速度/转向/踏板）| 100Hz | 10ms |
| carControl | 控制指令 | 100Hz | 10ms |
| controlsState | 控制系统状态 | 100Hz | 10ms |
| modelV2 | AI 模型输出（轨迹/车道线）| 20Hz | 50ms |
| radarState | 雷达目标（前车距离/相对速度）| 20Hz | 50ms |
| gpsLocationExternal | GPS 定位 | 10Hz | 100ms |
| gyroscope / accelerometer | IMU 传感器 | 104Hz | ~9.6ms |
| deviceState | 设备状态（温度/内存/电量）| 2Hz | 500ms |
| roadCameraState | 摄像头帧状态 | 20Hz | 50ms |
| liveParameters | 实时参数（转向比/偏移）| — | — |
| driverStateV2 | 驾驶员监控 | — | — |

频率分层：高频（100Hz+）为控制回路；中频（20-50Hz）为感知规划；低频（1-10Hz）为监控。

## 四、异步混合存储机制

各进程独立产生数据，按**纳秒级时间戳** `logMonoTime` 顺序写入（不按类型分组），
回放时严格按时间重现：
```
t=0ms:   carState (100Hz)
t=10ms:  carControl (100Hz)
t=50ms:  radarState (20Hz)   ← 不同频率插入
t=500ms: deviceState (2Hz)   ← 低频
```
特点：异步生产不等待、bz2/zstd 压缩比约 5:1~10:1、每条消息独立存储（单条损坏不影响其他）、支持随机访问。

## 五、存储位置与目录结构

```
/data/                          # 本项目路径（原生 PC 为 ~/.comma/）
├── logs/                       # swaglog 系统日志（本项目按日期分目录）
├── media/0/realdata/           # 驾驶数据记录
├── params/                     # 参数存储
└── stats/                      # 统计数据
```

### swaglog 系统日志
- 文件名：`swaglog.xxxxxxxxxx`（10 位编号）
- 级别：DEBUG / INFO / WARNING / ERROR
- 轮转：每 60 秒或 256KB 轮转，保留最新约 2500 个，自动压缩清理

### 驾驶数据段
目录命名：`{segment_id}--{dongle_id}--{segment_num}`（每段约 1 分钟）
```
00000000--a7bd96702d--0/
├── rlog.bz2       # 所有 cereal 消息
├── qlog.bz2       # 抽样日志
├── fcamera.hevc   # 前视摄像头视频
├── ecamera.hevc   # 广角摄像头视频
├── dcamera.hevc   # 驾驶员监控视频
└── qcamera.ts     # 预览视频流
```

### 参数与统计
- `params/`：`CarParams`（当前车辆配置）、`CarParamsCache`、`DongleId`、`Version` 等
- `stats/`：CPU/内存/网络/进程状态/错误频率
- 启动日志：`media/0/realdata/boot/`

### 相关配置
```bash
export LOGPRINT=info            # 控制台输出级别
export LOG_ROOT=/data/media/0/realdata   # 数据日志根目录
export SWAGLOG_DIR=/data/logs   # swaglog 目录
export DISABLE_LOGGING=1        # 禁用数据记录
```
进程配置见 `system/manager/process_config.py`：`logmessaged`（日志消息）、
`loggerd`（数据记录）、`deleter`（清理）。

## 六、数据访问（LogReader）

```python
from openpilot.tools.lib.logreader import LogReader

lr = LogReader("path/to/file.rlog.bz2")

# 遍历所有消息
for msg in lr:
    print(msg.logMonoTime, msg.which())

# 按类型过滤
for cs in lr.filter('carState'):
    print(cs.vEgo, cs.steeringAngleDeg)

first_control = lr.first('carControl')
```

## 七、查看与分析工具

```bash
# 回放驾驶数据
tools/replay/replay <route-name>

# CAN 数据分析（cabana）
python3 -m openpilot.tools.cabana.main

# 时间序列可视化（PlotJuggler）
tools/plotjuggler/juggle.py <route>
```
（CAN 抓包离线解析工具见 `tools/vw/can_analysis/`。）

## 八、日志管理

### 自动清理
`deleter` 进程在磁盘不足时按策略删除最旧数据（优先删视频，保留日志）。
本项目 `start_openpilot.sh` 另有按日期清理 30 天前日志的逻辑。

### 手动清理
```bash
# 保留最新 10 个数据段
cd /data/media/0/realdata && ls -t | tail -n +11 | xargs rm -rf

# 保留最新 100 个 swaglog
cd /data/logs && ls -t swaglog.* | tail -n +101 | xargs rm -f
```

### 备份
```bash
tar -czf backup_$(date +%Y%m%d).tar.gz /data/media/0/realdata/
```

## 九、故障排除

| 问题 | 处理 |
|------|------|
| 日志目录不存在 | `mkdir -p /data/logs /data/media/0/realdata` |
| 权限问题 | `sudo chown -R $USER:$USER /data` |
| 磁盘空间不足 | 检查 deleter 是否运行、手动清理、迁移到大盘 |
| 看不到日志 | `export LOGPRINT=debug` |

```bash
# 检查日志进程
ps aux | grep -E "(logmessaged|loggerd|deleter)"
# 磁盘使用
df -h /data
# 最新错误
grep -i error /data/logs/swaglog.* | tail -20
```

## 附录：守护进程职责速览

> 详细的启动条件、时序与依赖见《openpilot_进程启动指南.md》。日志/终端里出现的
> 进程名对应如下功能模块（openpilot 微服务架构，经 cereal 异步通信）：

- **核心驾驶栈**：`modeld`（AI 推理，输出车道线/路径）、`plannerd`（轨迹规划）、
  `controlsd`（控制循环，PID/LQR）、`card`（车辆接口，指令↔CAN）、`radard`（雷达）、
  `torqued`（转向转矩估计）
- **硬件与通信**：`pandad`（Panda/CAN 收发）、`hardwared`（温度/风扇/电压）、
  `camerad`（摄像头驱动）、`locationd`（GPS+IMU+视觉里程计定位）、`micd`（麦克风）
- **数据记录**：`loggerd`（写日志）、`encoderd`（H.264/265 视频编码）、
  `proclogd`（资源占用）、`logmessaged`（文本日志汇总）、`deleter`（存储清理）
- **UI 与统计**：`ui`（界面渲染）、`soundd`（音频）、`statsd`（里程/时长统计）、
  `feedbackd`（反馈）
- **系统管理**：`paramsd`（参数持久化）、`calibrationd`（摄像头俯仰/偏航自动校准）、
  `selfdrived`（状态机）、`lagd`（延迟监控）、`journald`（systemd 日志桥接）

短进程列表通常是 Offroad（低功耗）阶段，长列表是 Onroad（全功能行车）阶段。
进程名后跟 `EXIT`/`CRASH` 表示该模块故障。
