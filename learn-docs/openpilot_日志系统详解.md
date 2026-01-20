# openpilot 日志系统详解

## 概述

openpilot 使用多层次的日志系统来记录系统运行状态、调试信息和驾驶数据。本文档详细介绍日志的存储位置、格式和用途。

## 日志目录结构

### 默认存储位置

#### PC 模式
```
~/.comma/
├── log/                    # 系统日志目录
├── media/0/realdata/       # 驾驶数据记录
├── params/                 # 参数存储
└── stats/                  # 统计数据
```

#### 设备模式 (AGNOS)
```
/data/
├── log/                    # 系统日志
├── media/0/realdata/       # 驾驶数据
├── params/                 # 参数存储
└── stats/                  # 统计数据
```

## 日志类型详解

### 1. 系统日志 (swaglog)

**位置**: `~/.comma/log/` 或 `/data/log/`

**文件格式**: `swaglog.xxxxxxxxxx` (10位数字编号)

**内容**: 
- DEBUG: 详细调试信息
- INFO: 一般信息记录
- WARNING: 警告信息
- ERROR: 错误信息

**配置**:
```bash
export LOGPRINT=info    # 控制台输出级别
export LOGPRINT=debug   # 显示所有日志
export LOGPRINT=warning # 只显示警告和错误
```

**轮转机制**:
- 每60秒或256KB自动轮转
- 保留最新2500个文件
- 自动压缩和清理旧文件

### 2. 驾驶数据记录

**位置**: `~/.comma/media/0/realdata/`

**目录命名**: `{segment_id}--{dongle_id}--{segment_num}`
- `segment_id`: 8位十六进制时间戳
- `dongle_id`: 10位十六进制设备ID
- `segment_num`: 段号 (每段约1分钟)

**数据文件**:
```
00000000--a7bd96702d--0/
├── rlog.bz2          # 压缩的消息日志 (所有cereal消息)
├── qlog.bz2          # 压缩的CAN消息日志
├── dcamera.hevc      # 驾驶员监控摄像头视频
├── ecamera.hevc      # 前置摄像头视频 
├── fcamera.hevc      # 鱼眼摄像头视频
└── qcamera.ts        # 其他摄像头数据
```

### 3. 参数存储

**位置**: `~/.comma/params/`

**类型**:
- **持久化参数**: 车辆配置、用户设置
- **缓存参数**: 车辆参数缓存、临时状态
- **运行时参数**: 进程间通信数据

**重要参数文件**:
- `CarParams`: 当前车辆配置
- `CarParamsCache`: 车辆参数缓存
- `DongleId`: 设备唯一标识
- `Version`: openpilot版本信息

### 4. 统计数据

**位置**: `~/.comma/stats/`

**内容**:
- CPU、内存使用率
- 网络流量统计
- 进程运行状态
- 错误发生频率

### 5. 启动日志

**位置**: `~/.comma/media/0/realdata/boot/`

**内容**:
- 系统启动日志
- 进程启动顺序
- 初始化错误信息
- 崩溃转储文件

## 日志配置

### 环境变量控制

```bash
# 日志级别控制
export LOGPRINT=info        # 控制台输出级别

# 日志路径自定义
export LOG_ROOT=/data/logs  # 自定义数据日志根目录

# 禁用特定日志
export DISABLE_LOGGING=1    # 禁用数据记录
```

### 进程配置

**文件**: `system/manager/process_config.py`

```python
# 日志相关进程
PythonProcess("logmessaged", "system.logmessaged", always_run),     # 日志消息处理
NativeProcess("loggerd", "system/loggerd", ["./loggerd"], logging), # 数据记录
PythonProcess("deleter", "system.loggerd.deleter", always_run),     # 日志清理
```

## 日志查看工具

### 1. 实时日志查看
```bash
# 查看最新系统日志
tail -f ~/.comma/log/swaglog.*

# 查看特定级别日志
grep "ERROR" ~/.comma/log/swaglog.*
```

### 2. 数据回放工具
```bash
# 使用 replay 回放驾驶数据
cd openpilot/tools/replay
python replay.py ~/.comma/media/0/realdata/00000000--a7bd96702d--0
```

### 3. CAN 数据分析
```bash
# 使用 cabana 分析CAN消息
cd openpilot/tools/cabana  
python cabana.py ~/.comma/media/0/realdata/00000000--a7bd96702d--0
```

### 4. 日志分析工具
```bash
# 使用 PlotJuggler 可视化数据
cd openpilot/tools/plotjuggler
python plotjuggler.py ~/.comma/media/0/realdata/00000000--a7bd96702d--0
```

## 日志管理

### 自动清理机制

**deleter 进程**负责自动清理：
- 磁盘空间不足时删除最旧的数据
- 保持最少可用空间
- 优先删除视频文件，保留日志文件

### 手动清理
```bash
# 清理旧的驾驶数据 (保留最新10个段)
cd ~/.comma/media/0/realdata
ls -t | tail -n +11 | xargs rm -rf

# 清理系统日志 (保留最新100个文件)
cd ~/.comma/log
ls -t swaglog.* | tail -n +101 | xargs rm -f
```

### 备份重要日志
```bash
# 备份特定时间段的数据
cp -r ~/.comma/media/0/realdata/00000000--a7bd96702d--0 /backup/

# 压缩备份
tar -czf backup_$(date +%Y%m%d).tar.gz ~/.comma/media/0/realdata/
```

## 故障排除

### 常见问题

1. **日志目录不存在**
   ```bash
   mkdir -p ~/.comma/log
   mkdir -p ~/.comma/media/0/realdata
   ```

2. **权限问题**
   ```bash
   chmod 755 ~/.comma
   chown -R $USER:$USER ~/.comma
   ```

3. **磁盘空间不足**
   - 检查 deleter 进程是否运行
   - 手动清理旧数据
   - 调整存储路径到更大的磁盘

4. **日志级别过低**
   ```bash
   export LOGPRINT=debug  # 显示更多日志
   ```

### 调试命令

```bash
# 检查日志进程状态
ps aux | grep -E "(logmessaged|loggerd|deleter)"

# 检查磁盘使用情况
df -h ~/.comma

# 查看最新错误日志
grep -i error ~/.comma/log/swaglog.* | tail -20

# 监控日志文件变化
watch -n 1 'ls -la ~/.comma/log/'
```

## 性能优化

### 减少日志开销

1. **调整日志级别**
   ```bash
   export LOGPRINT=warning  # 只记录警告和错误
   ```

2. **禁用不必要的记录**
   ```bash
   export DISABLE_LOGGING=1  # 完全禁用数据记录
   ```

3. **使用SSD存储**
   - 将日志目录移动到SSD
   - 使用符号链接重定向

### 网络日志传输

```bash
# 通过rsync同步日志到远程服务器
rsync -av ~/.comma/log/ user@server:/backup/logs/

# 实时传输日志
tail -f ~/.comma/log/swaglog.* | nc server 1234
```

## 总结

openpilot 的日志系统提供了完整的数据记录和调试能力：

- **系统日志**: 用于调试和故障排除
- **驾驶数据**: 用于回放和分析
- **参数存储**: 保持系统配置
- **统计数据**: 监控系统性能

合理配置和管理日志系统对于 openpilot 的稳定运行和问题诊断至关重要。