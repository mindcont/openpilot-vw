# VOLKSWAGEN_GOLF_MK7 配置下 CAN 解析服务加载流程分析

## 概述

当配置 `export FINGERPRINT="VOLKSWAGEN_GOLF_MK7"` 时，openpilot 会按照特定的调用链路加载对应的 CAN 解析服务。本文档详细分析从启动到 DBC 文件加载的完整函数调用过程。

## 🚀 完整调用流程图

```
启动脚本
    ↓
launch_openpilot.sh
    ↓
system/manager/manager.py::main()
    ↓
manager_init()
    ↓
manager_thread()
    ↓
ensure_running() → 启动 card 进程
    ↓
selfdrive/car/card.py::main()
    ↓
Car.__init__()
    ↓
get_car() [核心车型识别]
    ↓
fingerprint() [指纹识别]
    ↓
CarInterface.get_params() [加载车型配置]
    ↓
DBC[CP.carFingerprint][Bus.pt] → 'vw_mqb'
    ↓
CANDefine(vw_mqb.dbc) [加载DBC文件]
    ↓
CAN 解析服务就绪
```

## 📋 详细调用过程分析

### 1. 系统启动阶段

#### 1.1 启动脚本执行
```bash
# start_openpilot.sh
export FINGERPRINT="VOLKSWAGEN_GOLF_MK7"
./launch_openpilot.sh
```

**关键环境变量设置**：
- `FINGERPRINT="VOLKSWAGEN_GOLF_MK7"` - 强制指定车型
- `SKIP_FW_QUERY=1` - 跳过固件查询
- `NOBOARD=1` - PC 模式

#### 1.2 Manager 启动
```python
# system/manager/manager.py::main()
def main() -> None:
    manager_init()      # 系统初始化
    manager_thread()    # 主监控循环
```

**manager_init() 关键步骤**：
```python
def manager_init() -> None:
    # 1. 参数系统初始化
    params = Params()
    params.clear_all(ParamKeyFlag.CLEAR_ON_MANAGER_START)
    
    # 2. 预导入所有进程模块
    for p in managed_processes.values():
        p.prepare()  # 预加载 car 相关模块
```

### 2. 进程管理阶段

#### 2.1 进程启动条件判断
```python
# system/manager/process_config.py
def only_onroad(started: bool, params: Params, CP: car.CarParams) -> bool:
    """仅在车辆上路时运行 - card 进程的启动条件"""
    return started

# managed_processes 中的 card 进程定义
PythonProcess("card", "selfdrive.car.card", only_onroad)
```

#### 2.2 进程启动执行
```python
# system/manager/manager.py::manager_thread()
def manager_thread() -> None:
    # 监控循环中启动进程
    ensure_running(managed_processes.values(), started, 
                  params=params, CP=sm['carParams'], not_run=ignore)
```

### 3. Card 进程启动阶段

#### 3.1 Card 主函数
```python
# selfdrive/car/card.py::main()
def main():
    config_realtime_process(4, Priority.CTRL_HIGH)  # 设置实时优先级
    car = Car()                                     # 创建 Car 实例
    car.card_thread()                              # 启动主循环
```

#### 3.2 Car 实例初始化
```python
# selfdrive/car/card.py::Car.__init__()
def __init__(self, CI=None, RI=None) -> None:
    # 1. 消息通信初始化
    self.can_sock = messaging.sub_sock('can', timeout=20)
    self.sm = messaging.SubMaster(['pandaStates', 'carControl', 'onroadEvents'])
    self.pm = messaging.PubMaster(['sendcan', 'carState', 'carParams', 'carOutput', 'liveTracks'])
    
    # 2. CAN 通信回调设置
    self.can_callbacks = can_comm_callbacks(self.can_sock, self.pm.sock['sendcan'])
    
    # 3. 等待 CAN 消息
    print("Waiting for CAN messages...")
    while True:
        can = messaging.recv_one_retry(self.can_sock)
        if len(can.can) > 0:
            break
    
    # 4. 获取系统参数
    alpha_long_allowed = self.params.get_bool("AlphaLongitudinalEnabled")
    is_release = self.params.get_bool("IsReleaseBranch")
    num_pandas = len(messaging.recv_one_retry(self.sm.sock['pandaStates']).pandaStates)
    
    # 5. 🎯 核心调用：车型识别和加载
    self.CI = get_car(*self.can_callbacks, obd_callback(self.params), 
                     alpha_long_allowed, is_release, num_pandas, cached_params)
```

### 4. 车型识别阶段 (核心)

#### 4.1 get_car() 函数
```python
# opendbc/car/car_helpers.py::get_car()
def get_car(can_recv, can_send, set_obd_multiplexing, alpha_long_allowed,
            is_release, num_pandas=1, cached_params=None):
    
    # 🔍 指纹识别阶段
    candidate, fingerprints, vin, car_fw, source, exact_match = fingerprint(
        can_recv, can_send, set_obd_multiplexing, num_pandas, cached_params)
    
    # 如果识别失败，使用 MOCK
    if candidate is None:
        candidate = "MOCK"
    
    # 🏭 获取车型接口
    CarInterface = interfaces[candidate]  # interfaces['VOLKSWAGEN_GOLF_MK7']
    
    # 📋 获取车型参数
    CP = CarInterface.get_params(candidate, fingerprints, car_fw, 
                                alpha_long_allowed, is_release, docs=False)
    
    # 🚗 创建车型接口实例
    return interfaces[CP.carFingerprint](CP)
```

#### 4.2 fingerprint() 函数详解
```python
# opendbc/car/car_helpers.py::fingerprint()
def fingerprint(can_recv, can_send, set_obd_multiplexing, num_pandas, cached_params):
    # 🎯 关键：检查 FINGERPRINT 环境变量
    fixed_fingerprint = os.environ.get('FINGERPRINT', "")  # "VOLKSWAGEN_GOLF_MK7"
    skip_fw_query = os.environ.get('SKIP_FW_QUERY', False)  # True
    
    start_time = time.monotonic()
    
    # 由于 SKIP_FW_QUERY=1，跳过固件查询
    if not skip_fw_query:
        # ... 固件查询逻辑 (跳过)
    else:
        vin_rx_addr, vin_rx_bus, vin = -1, -1, VIN_UNKNOWN
        exact_fw_match, fw_candidates, car_fw = True, set(), []
        cached = False
    
    # 关闭 OBD 多路复用
    set_obd_multiplexing(False)
    
    # CAN 指纹识别 (可能被跳过)
    can_recv()  # 清空 CAN 缓冲区
    car_fingerprint, finger = can_fingerprint(can_recv)
    
    exact_match = True
    source = CarParams.FingerprintSource.can
    
    # 🎯 关键：使用环境变量强制指定车型
    if fixed_fingerprint:  # "VOLKSWAGEN_GOLF_MK7"
        car_fingerprint = fixed_fingerprint
        source = CarParams.FingerprintSource.fixed
    
    # 记录识别结果
    carlog.error({
        "event": "fingerprinted", 
        "car_fingerprint": str(car_fingerprint),  # "VOLKSWAGEN_GOLF_MK7"
        "source": source,  # "fixed"
        "fuzzy": not exact_match,
        # ... 其他信息
    })
    
    return car_fingerprint, finger, vin, car_fw, source, exact_match
```

### 5. 车型配置加载阶段

#### 5.1 接口映射查找
```python
# opendbc/car/car_helpers.py
# 全局变量：接口映射表
interface_names = _get_interface_names()  # 获取所有品牌和车型
interfaces = load_interfaces(interface_names)  # 加载所有接口

# interfaces['VOLKSWAGEN_GOLF_MK7'] = 
#   opendbc.car.volkswagen.interface.CarInterface
```

#### 5.2 大众车型接口获取参数
```python
# opendbc/car/volkswagen/interface.py::CarInterface.get_params()
@staticmethod
def _get_params(ret: structs.CarParams, candidate: CAR, fingerprint, 
               car_fw, alpha_long, is_release, docs) -> structs.CarParams:
    
    ret.brand = "volkswagen"
    ret.radarUnavailable = True
    
    # 🔍 检查平台标志
    if ret.flags & VolkswagenFlags.PQ:
        # PQ 平台配置 (vw_pq.dbc)
        safety_configs = [get_safety_config(structs.CarParams.SafetyModel.volkswagenPq)]
        # ... PQ 平台特定配置
    elif ret.flags & VolkswagenFlags.MLB:
        # MLB 平台配置 (vw_mlb.dbc)  
        safety_configs = [get_safety_config(structs.CarParams.SafetyModel.volkswagenMlb)]
        # ... MLB 平台特定配置
    else:
        # 🎯 MQB 平台配置 (vw_mqb.dbc) - VOLKSWAGEN_GOLF_MK7 走这里
        safety_configs = [get_safety_config(structs.CarParams.SafetyModel.volkswagen)]
        ret.enableBsm = 0x30F in fingerprint[0]  # SWA_01
        
        # 变速箱类型检测
        if 0xAD in fingerprint[0] or docs:  # Getriebe_11
            ret.transmissionType = TransmissionType.automatic
        elif 0x187 in fingerprint[0]:  # Motor_EV_01
            ret.transmissionType = TransmissionType.direct
        else:
            ret.transmissionType = TransmissionType.manual
        
        # 网络位置检测
        if any(msg in fingerprint[1] for msg in (0x40, 0x86, 0xB2, 0xFD)):
            ret.networkLocation = NetworkLocation.gateway
        else:
            ret.networkLocation = NetworkLocation.fwdCamera
    
    # ... 其他配置
    return ret
```

### 6. DBC 文件加载阶段

#### 6.1 平台配置到 DBC 映射
```python
# opendbc/car/volkswagen/values.py
# VOLKSWAGEN_GOLF_MK7 的配置
VOLKSWAGEN_GOLF_MK7 = VolkswagenMQBPlatformConfig(
    # ... 车型文档和规格
    chassis_codes={"5G", "AU", "BA", "BE"},
    wmis={WMI.VOLKSWAGEN_MEXICO_CAR, WMI.VOLKSWAGEN_EUROPE_CAR},
)

# MQB 平台配置类
@dataclass
class VolkswagenMQBPlatformConfig(PlatformConfig):
    # 🎯 关键：DBC 文件映射
    dbc_dict: DbcDict = field(default_factory=lambda: {Bus.pt: 'vw_mqb'})
```

#### 6.2 DBC 映射表生成
```python
# opendbc/car/volkswagen/values.py 文件末尾
DBC = CAR.create_dbc_map()

# 生成的映射表结构：
# DBC = {
#     'VOLKSWAGEN_GOLF_MK7': {
#         Bus.pt: 'vw_mqb'  # 主要总线使用 vw_mqb.dbc
#     },
#     # ... 其他车型
# }
```

#### 6.3 CAN 解析器初始化
```python
# opendbc/car/volkswagen/values.py::CarControllerParams.__init__()
def __init__(self, CP):
    # 🎯 关键：加载 DBC 文件并创建 CAN 解析器
    can_define = CANDefine(DBC[CP.carFingerprint][Bus.pt])
    # DBC['VOLKSWAGEN_GOLF_MK7'][Bus.pt] = 'vw_mqb'
    # 实际调用：CANDefine('vw_mqb')
    
    # 根据平台标志配置不同的消息和信号
    if CP.flags & VolkswagenFlags.PQ:
        # PQ 平台配置
        self.hca_status_values = can_define.dv["Lenkhilfe_2"]["LH2_Sta_HCA"]
        # ... PQ 特定配置
    else:
        # 🎯 MQB 平台配置 - VOLKSWAGEN_GOLF_MK7 使用
        self.hca_status_values = can_define.dv["LH_EPS_03"]["EPS_HCA_Status"]
        
        if CP.flags & VolkswagenFlags.MLB:
            # MLB 特定配置
            self.shifter_values = can_define.dv["Getriebe_03"]["GE_Waehlhebel"]
        else:
            # 🎯 标准 MQB 配置
            if CP.transmissionType == TransmissionType.automatic:
                self.shifter_values = can_define.dv["Gateway_73"]["GE_Fahrstufe"]
            elif CP.transmissionType == TransmissionType.direct:
                self.shifter_values = can_define.dv["Motor_EV_01"]["MO_Waehlpos"]
```

### 7. CAN 消息解析服务就绪

#### 7.1 关键 CAN 消息定义 (vw_mqb.dbc)
```dbc
# 来自 vw_mqb.dbc 的关键消息
BO_ 290 ACC_06: 8 XXX                    # ACC 控制
BO_ 294 HCA_01: 8 XXX                    # 车道保持辅助  
BO_ 159 LH_EPS_03: 8 XXX                 # 电动助力转向
BO_ 987 Gateway_72: 8 XXX                # 网关消息
BO_ 178 ESP_19: 8 XXX                    # ESP 系统
BO_ 289 Motor_20: 8 XXX                  # 发动机信息
```

#### 7.2 CAN 解析器使用
```python
# 在 carstate.py 和 carcontroller.py 中使用
# opendbc/car/volkswagen/carstate.py
def update(self, cp, cp_cam, *_):
    # 使用 vw_mqb.dbc 解析 CAN 消息
    ret.vEgo = cp.vl["Motor_20"]["MO_Geschw_Ist"] * CV.KPH_TO_MS
    ret.steeringAngleDeg = cp.vl["LH_EPS_03"]["EPS_Lenkwinkel"]
    ret.steeringTorque = cp.vl["LH_EPS_03"]["EPS_Lenkmoment"]
    # ... 更多信号解析
```

## 🔧 关键函数调用链总结

### 主调用链
```python
1. manager.py::main()
   └── manager_init()
   └── manager_thread()
       └── ensure_running() → 启动 card 进程

2. card.py::main()
   └── Car.__init__()
       └── get_car()                    # 🎯 核心入口

3. car_helpers.py::get_car()
   └── fingerprint()                   # 车型识别
   └── interfaces[candidate]           # 获取接口类
   └── CarInterface.get_params()       # 获取车型参数
   └── interfaces[CP.carFingerprint](CP)  # 创建接口实例

4. volkswagen/interface.py::CarInterface.get_params()
   └── _get_params()                   # 配置车型参数
       └── 检查平台标志 (MQB/PQ/MLB)
       └── 设置 DBC 映射

5. volkswagen/values.py
   └── VolkswagenMQBPlatformConfig
       └── dbc_dict: {Bus.pt: 'vw_mqb'}  # 🎯 DBC 文件指定
   └── CarControllerParams.__init__()
       └── CANDefine('vw_mqb')          # 🎯 加载 DBC 文件
```

### 环境变量影响点
```python
# 关键环境变量及其影响点
FINGERPRINT="VOLKSWAGEN_GOLF_MK7"
├── car_helpers.py::fingerprint()
│   └── fixed_fingerprint = os.environ.get('FINGERPRINT', "")
│   └── if fixed_fingerprint: car_fingerprint = fixed_fingerprint
│
SKIP_FW_QUERY=1  
├── car_helpers.py::fingerprint()
│   └── skip_fw_query = os.environ.get('SKIP_FW_QUERY', False)
│   └── 跳过固件版本查询，加快启动速度
│
NOBOARD=1
└── process_config.py::manager_thread()
    └── ignore.append("pandad")  # 忽略硬件进程
```

## 🎯 总结

当配置 `FINGERPRINT="VOLKSWAGEN_GOLF_MK7"` 时：

1. **启动阶段**：Manager 启动并管理所有进程
2. **进程启动**：Card 进程在车辆上路时启动
3. **车型识别**：通过环境变量强制指定为 `VOLKSWAGEN_GOLF_MK7`
4. **配置加载**：加载 MQB 平台配置，映射到 `vw_mqb.dbc`
5. **DBC 加载**：`CANDefine('vw_mqb')` 加载 DBC 文件
6. **服务就绪**：CAN 解析服务使用 vw_mqb.dbc 解析所有 CAN 消息

整个流程确保了 24款速腾能够使用与 Golf MK7 相同的 CAN 消息解析逻辑，实现完整的车辆状态监控和控制功能。