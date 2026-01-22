# 大众车型 DBC 文件映射分析

## 概述

openpilot 根据大众集团车型的平台架构，使用不同的 DBC (Database CAN) 文件来解析 CAN 消息。每个平台有其特定的 CAN 消息格式和信号定义。

## DBC 文件映射关系

### 🔹 MQB 平台车型 (使用 `vw_mqb.dbc`)

**平台特点**：
- **全称**：Modularer Querbaukasten (模块化横置发动机平台)
- **年代**：2012年至今的现代化平台
- **CAN 消息数量**：113个
- **特点**：现代化电子架构，支持更多 ADAS 功能

**支持车型列表**：

| 车型代码 | 车型名称 | 年份 | 平台细分 |
|---------|---------|------|---------|
| `VOLKSWAGEN_ARTEON_MK1` | 大众 Arteon | 2018-23 | MQB-B |
| `VOLKSWAGEN_ATLAS_MK1` | 大众 Atlas | 2018-23 | MQB-A |
| `VOLKSWAGEN_CRAFTER_MK2` | 大众 Crafter | 2017-24 | MQB 商用 |
| `VOLKSWAGEN_GOLF_MK7` | 大众 Golf | 2015-20 | MQB-A |
| `VOLKSWAGEN_JETTA_MK7` | 大众 Jetta | 2019-23 | MQB-A |
| `VOLKSWAGEN_PASSAT_MK8` | 大众 Passat | 2015-22 | MQB-B |
| `VOLKSWAGEN_POLO_MK6` | 大众 Polo | 2018-23 | MQB-A0 |
| `VOLKSWAGEN_TAOS_MK1` | 大众 Taos | 2022-24 | MQB-A |
| `VOLKSWAGEN_TCROSS_MK1` | 大众 T-Cross | 2021 | MQB-A0 |
| `VOLKSWAGEN_TIGUAN_MK2` | 大众 Tiguan | 2018-24 | MQB-A |
| `VOLKSWAGEN_TOURAN_MK2` | 大众 Touran | 2016-23 | MQB-A |
| `VOLKSWAGEN_TRANSPORTER_T61` | 大众 Transporter | 2020+ | MQB 商用 |
| `VOLKSWAGEN_TROC_MK1` | 大众 T-Roc | 2018-23 | MQB-A |
| `AUDI_A3_MK3` | 奥迪 A3 | 2014-19 | MQB-A |
| `AUDI_Q2_MK1` | 奥迪 Q2 | 2018 | MQB-A0 |
| `AUDI_Q3_MK2` | 奥迪 Q3 | 2019-24 | MQB-A |
| `SEAT_ATECA_MK1` | 西雅特 Ateca/Leon | 2016-23 | MQB-A |
| `SKODA_FABIA_MK4` | 斯柯达 Fabia | 2022-23 | MQB-A0 |
| `SKODA_KAMIQ_MK1` | 斯柯达 Kamiq/Scala | 2020-23 | MQB-A0 |
| `SKODA_KAROQ_MK1` | 斯柯达 Karoq | 2019-23 | MQB-A |
| `SKODA_KODIAQ_MK1` | 斯柯达 Kodiaq | 2017-23 | MQB-A |
| `SKODA_OCTAVIA_MK3` | 斯柯达 Octavia | 2015-19 | MQB-A |
| `SKODA_SUPERB_MK3` | 斯柯达 Superb | 2015-22 | MQB-B |

**总计：23个车型**

### 🔸 PQ 平台车型 (使用 `vw_pq.dbc`)

**平台特点**：
- **全称**：Plattform Quer (横置发动机平台)
- **年代**：较老的平台架构
- **CAN 消息数量**：86个
- **特点**：传统电子架构，功能相对简单

**支持车型列表**：

| 车型代码 | 车型名称 | 年份 | 备注 |
|---------|---------|------|------|
| `VOLKSWAGEN_CADDY_MK3` | 大众 Caddy | 2019 | 商用车 |
| `VOLKSWAGEN_JETTA_MK6` | 大众 Jetta | 2015-18 | 老平台 |
| `VOLKSWAGEN_PASSAT_NMS` | 大众 Passat NMS | 2017-22 | 美版/中国版 |
| `VOLKSWAGEN_SHARAN_MK2` | 大众 Sharan | 2018-22 | MPV |

**总计：4个车型**

### 🔺 MLB 平台车型 (使用 `vw_mlb.dbc`)

**平台特点**：
- **全称**：Modularer Längsbaukasten (模块化纵置发动机平台)
- **年代**：豪华车专用平台
- **CAN 消息数量**：144个
- **特点**：最复杂的电子架构，支持高端功能

**支持车型列表**：

| 车型代码 | 车型名称 | 年份 | 备注 |
|---------|---------|------|------|
| `PORSCHE_MACAN_MK1` | 保时捷 Macan | 2017-24 | 豪华 SUV |

**总计：1个车型**

## 中国市场车型映射

### 24款大众速腾分析

**推荐配置**：
```bash
export FINGERPRINT="VOLKSWAGEN_GOLF_MK7"
```

**技术原因**：
1. **平台架构**：速腾基于 MQB-A 平台，与 Golf MK7 相同
2. **CAN 消息格式**：使用相同的 `vw_mqb.dbc` 解析
3. **电子架构**：相似的 ECU 配置和通信协议
4. **实际验证**：openpilot 已自动识别为 `VOLKSWAGEN_GOLF_MK7`

### 其他中国市场车型建议

| 中国车型 | 推荐 FINGERPRINT | 使用 DBC | 平台 |
|---------|-----------------|----------|------|
| **一汽-大众** | | | |
| 速腾 | `VOLKSWAGEN_GOLF_MK7` | `vw_mqb.dbc` | MQB-A |
| 宝来 | `VOLKSWAGEN_GOLF_MK7` | `vw_mqb.dbc` | MQB-A |
| 高尔夫 | `VOLKSWAGEN_GOLF_MK7` | `vw_mqb.dbc` | MQB-A |
| 迈腾 | `VOLKSWAGEN_PASSAT_MK8` | `vw_mqb.dbc` | MQB-B |
| 探岳 | `VOLKSWAGEN_TIGUAN_MK2` | `vw_mqb.dbc` | MQB-A |
| 探影 | `VOLKSWAGEN_TCROSS_MK1` | `vw_mqb.dbc` | MQB-A0 |
| **上汽大众** | | | |
| 朗逸 | `VOLKSWAGEN_GOLF_MK7` | `vw_mqb.dbc` | MQB-A |
| 帕萨特 | `VOLKSWAGEN_PASSAT_MK8` | `vw_mqb.dbc` | MQB-B |
| 途观L | `VOLKSWAGEN_TIGUAN_MK2` | `vw_mqb.dbc` | MQB-A |
| 途岳 | `VOLKSWAGEN_TIGUAN_MK2` | `vw_mqb.dbc` | MQB-A |
| 途安 | `VOLKSWAGEN_TOURAN_MK2` | `vw_mqb.dbc` | MQB-A |

## DBC 文件技术差异

### vw_mqb.dbc 特点

**主要 CAN 消息**：
- `ACC_06` (0x122) - ACC 控制
- `HCA_01` (0x126) - 车道保持辅助
- `LH_EPS_03` (0x09F) - 电动助力转向
- `Gateway_72` (0x3DB) - 网关消息
- `ESP_19` (0x0B2) - ESP 系统
- `Motor_20` (0x121) - 发动机信息

**信号特点**：
- 现代化信号定义
- 支持更多 ADAS 功能
- 精确的物理单位转换
- 完整的错误检测机制

### vw_pq.dbc 特点

**主要 CAN 消息**：
- `GRA_Neu` - 巡航控制（老格式）
- `Lenkhilfe_2` - 转向辅助（老格式）
- `Getriebe_1` - 变速箱信息
- `ESP_21` - ESP 系统（老版本）

**信号特点**：
- 传统信号定义
- 功能相对简单
- 兼容性考虑
- 较少的 ADAS 支持

### vw_mlb.dbc 特点

**主要 CAN 消息**：
- `LS_01` - 豪华版巡航控制
- `Getriebe_03` - 高端变速箱
- 更多豪华功能相关消息

**信号特点**：
- 最复杂的信号定义
- 支持高端功能
- 精密的控制逻辑
- 豪华车专用协议

## 平台识别逻辑

### 代码实现

```python
# 在 values.py 中的平台配置
@dataclass
class VolkswagenMQBPlatformConfig(PlatformConfig):
  dbc_dict: DbcDict = field(default_factory=lambda: {Bus.pt: 'vw_mqb'})

@dataclass  
class VolkswagenPQPlatformConfig(VolkswagenMQBPlatformConfig):
  dbc_dict: DbcDict = field(default_factory=lambda: {Bus.pt: 'vw_pq'})

@dataclass
class VolkswagenMLBPlatformConfig(PlatformConfig):
  dbc_dict: DbcDict = field(default_factory=lambda: {Bus.pt: 'vw_mlb'})
```

### 自动识别流程

1. **VIN 码解析** → 获取 WMI 和底盘代码
2. **固件版本匹配** → 确认 ECU 兼容性  
3. **CAN 指纹识别** → 匹配消息格式
4. **平台配置选择** → 确定 DBC 文件

## 实际应用建议

### 对于 24款速腾用户

```bash
# 推荐配置
export FINGERPRINT="VOLKSWAGEN_GOLF_MK7"

# 验证方法
grep "Using DBC" /data/logs/current/*.log
# 应该看到: Using DBC: vw_mqb.dbc
```

### 调试和验证

```bash
# 查看当前使用的 DBC 文件
python3 -c "
from opendbc.car.volkswagen.values import CAR
car = CAR.VOLKSWAGEN_GOLF_MK7
print(f'DBC文件: {car.config.dbc_dict}')
"

# 检查 CAN 消息解析
candump can0 | grep -E "(122|126|09F)"  # 查看关键消息
```

## 总结

- **MQB 平台**：现代大众车型的主流选择，支持最多功能
- **PQ 平台**：老平台车型，功能相对简单
- **MLB 平台**：豪华车专用，功能最复杂

对于中国市场的大众车型，绝大多数都基于 MQB 平台，因此使用 `vw_mqb.dbc` 进行 CAN 消息解析。24款速腾作为典型的 MQB-A 平台车型，与 Golf MK7 具有高度的技术相似性，使用相同的 DBC 文件是最佳选择。