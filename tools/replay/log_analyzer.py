#!/usr/bin/env python3
"""
openpilot 日志数据结构分析器
展示日志文件的内容和数据结构
"""

import json
from openpilot.tools.lib.logreader import LogReader

def analyze_frequency_and_storage(log_file):
    """分析各类数据的频率和存储方式"""
    print("=== 数据频率和存储分析 ===\n")
    
    lr = LogReader(log_file)
    
    # 统计各消息类型的时间戳
    msg_timestamps = {}
    msg_counts = {}
    first_time = None
    last_time = None
    
    print("正在分析消息频率...")
    for msg in lr:
        msg_type = msg.which()
        timestamp = msg.logMonoTime
        
        if first_time is None:
            first_time = timestamp
        last_time = timestamp
        
        if msg_type not in msg_timestamps:
            msg_timestamps[msg_type] = []
            msg_counts[msg_type] = 0
            
        msg_timestamps[msg_type].append(timestamp)
        msg_counts[msg_type] += 1
    
    duration = (last_time - first_time) / 1e9  # 转换为秒
    print(f"\n日志时长: {duration:.2f} 秒")
    
    # 计算各消息类型的频率
    print("\n=== 各消息类型频率分析 ===\n")
    print(f"{'消息类型':<20} {'总数':<8} {'频率(Hz)':<10} {'间隔(ms)':<12} {'存储方式'}")
    print("-" * 70)
    
    for msg_type in sorted(msg_counts.keys()):
        count = msg_counts[msg_type]
        frequency = count / duration if duration > 0 else 0
        interval = 1000 / frequency if frequency > 0 else 0
        
        # 分析存储方式
        storage_type = analyze_storage_pattern(msg_timestamps[msg_type])
        
        print(f"{msg_type:<20} {count:<8} {frequency:<10.1f} {interval:<12.1f} {storage_type}")
    
    # 详细分析几个重要类型的时间分布
    important_types = ['carState', 'carControl', 'controlsState', 'radarState', 'modelV2']
    
    for msg_type in important_types:
        if msg_type in msg_timestamps:
            analyze_timing_pattern(msg_type, msg_timestamps[msg_type])

def analyze_storage_pattern(timestamps):
    """分析存储模式"""
    if len(timestamps) < 2:
        return "单次记录"
    
    # 计算时间间隔
    intervals = []
    for i in range(1, min(len(timestamps), 100)):  # 只分析前100个间隔
        interval = (timestamps[i] - timestamps[i-1]) / 1e6  # 转换为毫秒
        intervals.append(interval)
    
    if not intervals:
        return "无规律"
    
    avg_interval = sum(intervals) / len(intervals)
    
    # 判断规律性
    variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
    std_dev = variance ** 0.5
    
    if std_dev < avg_interval * 0.1:  # 标准差小于平均值的10%
        return f"定时({avg_interval:.1f}ms)"
    elif std_dev < avg_interval * 0.3:
        return f"准定时({avg_interval:.1f}±{std_dev:.1f}ms)"
    else:
        return f"不规律({avg_interval:.1f}±{std_dev:.1f}ms)"

def analyze_timing_pattern(msg_type, timestamps):
    """详细分析时间模式"""
    print(f"\n=== {msg_type} 时间分布详情 ===\n")
    
    if len(timestamps) < 2:
        print("数据不足")
        return
    
    # 计算所有间隔
    intervals = []
    for i in range(1, len(timestamps)):
        interval = (timestamps[i] - timestamps[i-1]) / 1e6  # 毫秒
        intervals.append(interval)
    
    # 统计信息
    avg_interval = sum(intervals) / len(intervals)
    min_interval = min(intervals)
    max_interval = max(intervals)
    
    print(f"消息总数: {len(timestamps)}")
    print(f"平均间隔: {avg_interval:.2f} ms")
    print(f"最小间隔: {min_interval:.2f} ms")
    print(f"最大间隔: {max_interval:.2f} ms")
    print(f"理论频率: {1000/avg_interval:.1f} Hz")
    
    # 间隔分布统计
    interval_ranges = {
        "<5ms": 0, "5-15ms": 0, "15-25ms": 0, 
        "25-50ms": 0, "50-100ms": 0, ">100ms": 0
    }
    
    for interval in intervals:
        if interval < 5:
            interval_ranges["<5ms"] += 1
        elif interval < 15:
            interval_ranges["5-15ms"] += 1
        elif interval < 25:
            interval_ranges["15-25ms"] += 1
        elif interval < 50:
            interval_ranges["25-50ms"] += 1
        elif interval < 100:
            interval_ranges["50-100ms"] += 1
        else:
            interval_ranges[">100ms"] += 1
    
    print("\n间隔分布:")
    for range_name, count in interval_ranges.items():
        percentage = (count / len(intervals)) * 100
        print(f"  {range_name}: {count} ({percentage:.1f}%)")

def explain_storage_mechanism():
    """解释存储机制"""
    print("\n=== openpilot 数据存储机制 ===\n")
    
    explanation = """
    1. 异步存储模式:
       - 各个进程独立产生数据
       - 不同频率的数据混合存储在同一个日志文件中
       - 按时间戳顺序写入，不按消息类型分组
    
    2. 时间戳驱动:
       - 每条消息都有精确的纳秒级时间戳 (logMonoTime)
       - 回放时按时间戳顺序重现事件
       - 支持精确的时间同步
    
    3. 频率特征:
       - carState/carControl: ~100Hz (10ms间隔)
       - radarState/modelV2: ~20Hz (50ms间隔)
       - deviceState: ~2Hz (500ms间隔)
       - gps相关: ~10Hz (100ms间隔)
       - 传感器数据: 25-104Hz (视传感器而定)
    
    4. 存储优化:
       - 使用Cap'n Proto零拷贝序列化
       - bz2/zstd压缩减少存储空间
       - 支持流式读取，无需全部加载到内存
    
    5. 数据完整性:
       - 每个消息独立存储，单个消息损坏不影响其他
       - 支持部分读取和随机访问
       - 时间戳保证数据的时序关系
    
    6. 混合存储示例:
       时间轴: |--carState(10ms)--carControl(10ms)--radarState(50ms)--carState(10ms)--|
       
       实际存储顺序 (按时间戳):
       t=0ms:    carState
       t=10ms:   carControl  
       t=20ms:   carState
       t=30ms:   carControl
       t=40ms:   carState
       t=50ms:   radarState  <- 不同频率的数据插入
       t=60ms:   carControl
       ...
    """
    print(explanation)

def show_sample_record():
    """显示一条完整的示例记录"""
    print("\n=== 典型的 carState 消息记录示例 ===")
    
    sample_record = """
    {
      "logMonoTime": 1690464079123456789,
      "which": "carState",
      "carState": {
        "vEgo": 15.2,                    // 车辆速度 (m/s)
        "aEgo": 0.1,                     // 车辆加速度 (m/s²)
        "steeringAngleDeg": -2.5,        // 转向角度 (度)
        "steeringTorque": 1.2,           // 方向盘力矩 (Nm)
        "brake": 0.0,                    // 刹车踏板位置 (0-1)
        "gas": 0.3,                      // 油门踏板位置 (0-1)
        "gearShifter": "drive",          // 档位
        "handbrakePressed": false,       // 手刹状态
        "leftBlinker": false,            // 左转向灯
        "rightBlinker": false,           // 右转向灯
        "wheelSpeeds": {
          "fl": 15.1,                    // 前左轮速度
          "fr": 15.3,                    // 前右轮速度
          "rl": 15.0,                    // 后左轮速度
          "rr": 15.2                     // 后右轮速度
        },
        "cruiseState": {
          "enabled": true,               // 巡航控制启用
          "speed": 16.7,                 // 巡航设定速度
          "available": true              // 巡航控制可用
        }
      }
    }
    """
    print(sample_record)

def explain_log_format():
    """解释日志格式"""
    print("\n=== openpilot 日志格式说明 ===")
    
    format_info = """
    1. 文件格式:
       - .rlog.bz2: 压缩的二进制日志文件 (主要格式)
       - .qlog.bz2: 压缩的查询优化日志文件
       - .rlog.zst: Zstandard压缩格式
    
    2. 数据结构:
       - 使用 Cap'n Proto 序列化格式
       - 每条记录包含时间戳和消息内容
       - 消息类型由 cereal/log.capnp 定义
    
    3. 时间戳:
       - logMonoTime: 单调时间戳 (纳秒)
       - 用于精确的时间同步
    
    4. 消息类型:
       - carState: 车辆状态信息
       - carControl: 控制指令
       - controlsState: 控制系统状态
       - radarState: 雷达数据
       - modelV2: AI模型输出
       - deviceState: 设备状态
       - 等等...
    
    5. 数据访问:
       - 不能直接解压为文本文件
       - 需要使用 LogReader 类解析
       - 支持按消息类型过滤
    """
    print(format_info)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
        analyze_frequency_and_storage(log_file)
        explain_storage_mechanism()
    else:
        print("用法: python3 log_analyzer.py <日志文件路径>")
        print("\n或者查看示例:")
        show_sample_record()
        explain_log_format()
        explain_storage_mechanism()