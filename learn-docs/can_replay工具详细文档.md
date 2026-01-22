# can_replay.py 工具详细文档

## 📋 概述

`can_replay.py` 是openpilot的硬件级CAN消息重放工具，通过panda jungle硬件将记录的CAN数据重放到真实的CAN总线上，为开发和测试提供真实的车辆环境模拟。

## 🎯 核心功能

### 1. 硬件级CAN重放
- 从rlog文件提取CAN消息
- 通过panda jungle硬件发送到真实CAN总线
- 支持多设备同时连接

### 2. 车辆状态模拟
- 模拟点火状态 (`set_ignition`)
- 模拟电源状态 (`set_panda_power`)
- 支持电源/点火循环控制

### 3. 实时消息发送
- 按原始时序重放CAN消息
- 支持多CAN总线 (0,1,2,3)
- 自动处理发送缓冲区溢出

## 🔧 技术架构

### 核心组件

```python
# 1. 消息加载器
def load_route(route_or_segment_name):
    lr = LogReader(route_or_segment_name)
    CP = lr.first("carParams")
    mbytes = [m.as_builder().to_bytes() for m in lr if m.which() == 'can']
    return [m[1] for m in can_capnp_to_list(mbytes)]

# 2. 发送线程
def send_thread(j: PandaJungle, flock):
    # 初始化jungle
    j.reset()
    for i in [0, 1, 2, 3, 0xFFFF]:
        j.can_clear(i)
        j.set_can_speed_kbps(i, 500)
    
    # 循环发送消息
    while True:
        send = CAN_MSGS[rk.frame % len(CAN_MSGS)]
        j.can_send_many(send)

# 3. 设备管理器
def connect():
    # 自动发现和管理panda jungle设备
    for s in PandaJungle.list():
        if s not in serials:
            serials[s] = threading.Thread(target=send_thread, args=(PandaJungle(s), flashing_lock))
```

### 数据流程

```
rlog文件 → LogReader → CAN消息提取 → panda jungle → 真实CAN总线 → comma设备
```

## 💡 使用方法

### 基本用法

```bash
# 使用默认演示路由
python tools/replay/can_replay.py

# 指定完整路由
python tools/replay/can_replay.py "77611a1fac303767/2020-03-24--09-50-38"

# 指定特定段落
python tools/replay/can_replay.py "77611a1fac303767/2020-03-24--09-50-38/2"

# 指定段落范围
python tools/replay/can_replay.py "77611a1fac303767/2020-03-24--09-50-38/2:4"
```

### 高级配置

```bash
# 刷新jungle固件
FLASH=1 python tools/replay/can_replay.py

# 电源循环控制 (30秒开启，5秒关闭)
PWR_ON=30 PWR_OFF=5 python tools/replay/can_replay.py

# 点火循环控制 (60秒开启，10秒关闭)
IGN_ON=60 IGN_OFF=10 python tools/replay/can_replay.py

# 同时控制电源和点火
PWR_ON=30 PWR_OFF=5 IGN_ON=60 IGN_OFF=10 python tools/replay/can_replay.py
```

## 🔌 硬件要求

### 必需硬件

1. **panda jungle**
   - 6端口CAN集线器
   - USB连接到PC
   - 支持多设备同时连接

2. **comma设备或panda**
   - 通过OBD-C线缆连接到jungle
   - 接收重放的CAN消息

3. **连接线缆**
   - USB-A到USB-C (PC到jungle)
   - OBD-C线缆 (jungle到设备)

### 硬件连接图

```
PC (USB) ←→ panda jungle ←→ comma设备/panda (OBD-C)
                ↓
            CAN总线重放
```

## ⚙️ 环境变量配置

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `FLASH` | bool | 0 | 是否刷新jungle固件 |
| `PWR_ON` | int | 0 | 电源开启时间(秒) |
| `PWR_OFF` | int | 0 | 电源关闭时间(秒) |
| `IGN_ON` | int | 0 | 点火开启时间(秒) |
| `IGN_OFF` | int | 0 | 点火关闭时间(秒) |
| `FILEREADER_CACHE` | bool | 1 | 启用文件读取缓存 |

### 配置示例

```bash
# 完整配置示例
export FLASH=1          # 刷新固件
export PWR_ON=30        # 电源开30秒
export PWR_OFF=5        # 电源关5秒
export IGN_ON=60        # 点火开60秒
export IGN_OFF=10       # 点火关10秒

python tools/replay/can_replay.py "your_route_name"
```

## 🎪 应用场景

### 1. 新车型适配测试

```bash
# 重放大众速腾的CAN数据
python tools/replay/can_replay.py "sagitar_route_name"

# 验证车型识别和参数配置
# comma设备会接收到真实的CAN消息并尝试识别车型
```

### 2. 功能验证测试

```bash
# 重放特定驾驶场景
python tools/replay/can_replay.py "route_with_lane_change"

# 测试openpilot在该场景下的行为
```

### 3. 开发环境搭建

```bash
# 为开发者提供稳定的测试环境
PWR_ON=3600 IGN_ON=3600 python tools/replay/can_replay.py "stable_route"

# 长时间稳定运行，支持持续开发
```

### 4. 回归测试

```bash
# 自动化测试脚本
#!/bin/bash
for route in route1 route2 route3; do
    echo "Testing $route"
    timeout 300 python tools/replay/can_replay.py "$route"
    # 检查测试结果
done
```

## 🔍 技术细节

### CAN消息处理

```python
# 消息过滤 - 只发送总线0-2的消息
send = list(filter(lambda x: x[-1] <= 2, send))

# 消息格式: [address, data, bus]
# address: CAN消息ID
# data: 消息数据 (最多8字节)
# bus: CAN总线编号 (0,1,2,3)
```

### 时序控制

```python
# 使用Ratekeeper保持准确时序
rk = Ratekeeper(1 / DT_CTRL, print_delay_threshold=None)  # 100Hz

# 循环发送，保持原始时序
send = CAN_MSGS[rk.frame % len(CAN_MSGS)]
```

### 错误处理

```python
try:
    j.can_send_many(send)
except usb1.USBErrorTimeout:
    # 发送缓冲区满是正常情况，继续执行
    pass
```

## 🛠️ 故障排除

### 常见问题

1. **找不到panda jungle**
   ```bash
   # 检查USB连接
   lsusb | grep -i panda
   
   # 检查权限
   sudo chmod 666 /dev/bus/usb/*/*
   ```

2. **CAN消息发送失败**
   ```bash
   # 检查CAN总线速率
   # 确保设置为500kbps (标准汽车CAN速率)
   ```

3. **设备无响应**
   ```bash
   # 重置jungle
   FLASH=1 python tools/replay/can_replay.py
   ```

### 调试技巧

```bash
# 启用详细日志
export PYTHONPATH=/home/wio/openpilot
python -u tools/replay/can_replay.py route_name 2>&1 | tee debug.log

# 监控CAN消息
# 在另一个终端运行
python -c "
from panda import PandaJungle
j = PandaJungle()
while True:
    msgs = j.can_recv()
    if msgs:
        print(f'Received {len(msgs)} messages')
"
```

## 📊 性能优化

### 消息缓存

```python
# 预加载所有CAN消息到内存
CAN_MSGS = load_route(route_name)  # 一次性加载

# 避免实时读取文件，提高发送性能
```

### 多线程处理

```python
# 每个jungle设备使用独立线程
for s in PandaJungle.list():
    thread = threading.Thread(target=send_thread, args=(PandaJungle(s), lock))
    thread.start()
```

### USB优化

```python
# 处理USB超时，避免阻塞
try:
    j.can_send_many(send)
except usb1.USBErrorTimeout:
    pass  # 继续执行，不中断发送循环
```

## 🔒 安全注意事项

### 硬件安全

1. **电源管理**
   - 避免长时间高功率运行
   - 使用电源循环保护设备

2. **CAN总线保护**
   - 确保消息不会干扰真实车辆
   - 在隔离环境中测试

### 软件安全

```python
# 消息验证
send = list(filter(lambda x: x[-1] <= 2, send))  # 只发送有效总线

# 设备保护
j.set_can_loopback(False)  # 避免消息回环
```

## 📈 扩展功能

### 自定义消息注入

```python
# 修改can_replay.py添加自定义消息
custom_msg = [0x123, b'\x01\x02\x03\x04', 0]  # [ID, data, bus]
send.append(custom_msg)
```

### 实时消息修改

```python
# 动态修改消息内容
for msg in send:
    if msg[0] == 0x123:  # 特定消息ID
        msg[1] = modify_data(msg[1])  # 修改数据
```

### 多路由混合

```python
# 加载多个路由的消息
routes = ["route1", "route2", "route3"]
all_msgs = []
for route in routes:
    all_msgs.extend(load_route(route))

CAN_MSGS = all_msgs
```

## 📝 最佳实践

### 开发建议

1. **渐进式测试**
   ```bash
   # 先测试短段落
   python tools/replay/can_replay.py "route/0"
   
   # 再测试完整路由
   python tools/replay/can_replay.py "route"
   ```

2. **环境隔离**
   - 使用专用的测试环境
   - 避免与生产环境混合

3. **数据备份**
   - 备份重要的测试路由
   - 记录测试配置和结果

### 性能建议

1. **硬件配置**
   - 使用USB 3.0接口
   - 确保充足的电源供应

2. **软件配置**
   - 关闭不必要的后台程序
   - 使用SSD存储rlog文件

## 🔗 相关工具

### 配套工具

1. **replay.py** - 软件级消息重放
2. **cabana.py** - CAN消息分析
3. **plotjuggler** - 数据可视化

### 工具对比

| 工具 | 类型 | 用途 | 硬件需求 |
|------|------|------|----------|
| can_replay.py | 硬件重放 | 真实CAN环境 | panda jungle |
| replay.py | 软件重放 | 消息模拟 | 无 |
| cabana.py | 分析工具 | 数据分析 | 无 |

## 📚 参考资源

- [panda jungle文档](https://github.com/commaai/panda_jungle)
- [openpilot replay文档](https://github.com/commaai/openpilot/tree/master/tools/replay)
- [CAN总线协议](https://en.wikipedia.org/wiki/CAN_bus)

## 🎉 总结

`can_replay.py` 是openpilot生态系统中的重要工具，提供了硬件级的CAN消息重放能力。通过panda jungle硬件，它能够创建真实的车辆环境，为开发、测试和调试提供强大支持。

**主要优势:**
- 硬件级真实性
- 多设备支持
- 灵活的配置选项
- 稳定的性能表现

**适用场景:**
- 新车型适配开发
- 功能验证测试
- 回归测试自动化
- 开发环境搭建

正确使用这个工具可以大大提高openpilot开发和测试的效率，为车型适配和功能开发提供可靠的基础。