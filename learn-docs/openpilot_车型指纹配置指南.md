# openpilot 车型指纹配置指南

## 概述

openpilot 使用 `FINGERPRINT` 环境变量来强制指定车型配置，绕过自动识别过程。这对于测试、调试或处理识别问题的车型特别有用。

## FINGERPRINT 环境变量

### 作用机制

1. **自动识别优先级**：
   - CAN 消息指纹识别
   - 固件版本匹配  
   - VIN 码解析
   - **FINGERPRINT 环境变量（最高优先级）**

2. **定义位置**：
   ```bash
   # 在 car_helpers.py 中的实现
   fixed_fingerprint = os.environ.get('FINGERPRINT', "")
   if fixed_fingerprint:
       car_fingerprint = fixed_fingerprint
       source = CarParams.FingerprintSource.fixed
   ```

## 大众集团车型支持列表

### 大众品牌 (Volkswagen)

| 车型代码 | 车型名称 | 年份范围 | 备注 |
|---------|---------|---------|------|
| `VOLKSWAGEN_ARTEON_MK1` | Arteon | 2018-23 | 包括 R 和 eHybrid 版本 |
| `VOLKSWAGEN_ATLAS_MK1` | Atlas | 2018-23 | 包括 Cross Sport |
| `VOLKSWAGEN_CADDY_MK3` | Caddy | 2019 | 商用车 |
| `VOLKSWAGEN_CRAFTER_MK2` | Crafter | 2017-24 | 大型商用车 |
| `VOLKSWAGEN_GOLF_MK7` | Golf | 2015-20 | 包括 e-Golf, GTI, R |
| `VOLKSWAGEN_JETTA_MK6` | Jetta | 2015-18 | PQ 平台 |
| `VOLKSWAGEN_JETTA_MK7` | Jetta | 2019-23 | MQB 平台 |
| `VOLKSWAGEN_PASSAT_MK8` | Passat | 2015-22 | 欧版 MQB |
| `VOLKSWAGEN_PASSAT_NMS` | Passat NMS | 2017-22 | 美版 PQ |
| `VOLKSWAGEN_POLO_MK6` | Polo | 2018-23 | MQB-A0 |
| `VOLKSWAGEN_SHARAN_MK2` | Sharan | 2018-22 | MPV |
| `VOLKSWAGEN_TAOS_MK1` | Taos | 2022-24 | 小型 SUV |
| `VOLKSWAGEN_TCROSS_MK1` | T-Cross | 2021 | 小型 SUV |
| `VOLKSWAGEN_TIGUAN_MK2` | Tiguan | 2018-24 | 中型 SUV |
| `VOLKSWAGEN_TOURAN_MK2` | Touran | 2016-23 | MPV |
| `VOLKSWAGEN_TRANSPORTER_T61` | Transporter T6.1 | 2020+ | 商用车 |
| `VOLKSWAGEN_TROC_MK1` | T-Roc | 2018-23 | 紧凑 SUV |

### 奥迪品牌 (Audi)

| 车型代码 | 车型名称 | 年份范围 | 备注 |
|---------|---------|---------|------|
| `AUDI_A3_MK3` | A3 | 2014-19 | 包括 S3, RS3 |
| `AUDI_Q2_MK1` | Q2 | 2018 | 小型 SUV |
| `AUDI_Q3_MK2` | Q3 | 2019-24 | 紧凑 SUV |

### 保时捷品牌 (Porsche)

| 车型代码 | 车型名称 | 年份范围 | 备注 |
|---------|---------|---------|------|
| `PORSCHE_MACAN_MK1` | Macan | 2017-24 | MLB 平台 |

### 西雅特品牌 (SEAT)

| 车型代码 | 车型名称 | 年份范围 | 备注 |
|---------|---------|---------|------|
| `SEAT_ATECA_MK1` | Ateca/Leon | 2016-23 | MQB 平台 |

### 斯柯达品牌 (Škoda)

| 车型代码 | 车型名称 | 年份范围 | 备注 |
|---------|---------|---------|------|
| `SKODA_FABIA_MK4` | Fabia | 2022-23 | MQB-A0 |
| `SKODA_KAMIQ_MK1` | Kamiq/Scala | 2020-23 | MQB-A0 |
| `SKODA_KAROQ_MK1` | Karoq | 2019-23 | MQB |
| `SKODA_KODIAQ_MK1` | Kodiaq | 2017-23 | MQB |
| `SKODA_OCTAVIA_MK3` | Octavia | 2015-19 | MQB |
| `SKODA_SUPERB_MK3` | Superb | 2015-22 | MQB |

## 使用方法

### 1. 临时设置（单次使用）

```bash
# 设置环境变量
export FINGERPRINT="VOLKSWAGEN_GOLF_MK7"

# 启动 openpilot
./launch_openpilot.sh
```

### 2. 脚本中设置（推荐）

在启动脚本中添加：

```bash
# 在 start_openpilot.sh 中修改
setup_environment() {
    # 其他环境变量...
    
    # 车型指纹设置
    export FINGERPRINT="VOLKSWAGEN_GOLF_MK7"  # 替换为你的车型
    
    # 其他配置...
}
```

### 3. 永久设置

在 `~/.bashrc` 或 `~/.profile` 中添加：

```bash
export FINGERPRINT="VOLKSWAGEN_GOLF_MK7"
```

## 针对中国市场车型的建议

### 24款大众速腾

根据平台架构和 CAN 消息分析，推荐使用：

```bash
export FINGERPRINT="VOLKSWAGEN_GOLF_MK7"
```

**原因**：
- 同为 MQB 平台
- CAN 消息格式相似
- openpilot 已自动识别为此车型

### 其他中国市场大众车型

| 中国车型 | 推荐 FINGERPRINT | 说明 |
|---------|-----------------|------|
| 速腾 | `VOLKSWAGEN_GOLF_MK7` | MQB 平台，消息格式相似 |
| 宝来 | `VOLKSWAGEN_GOLF_MK7` | MQB 平台 |
| 朗逸 | `VOLKSWAGEN_GOLF_MK7` | MQB 平台 |
| 帕萨特 | `VOLKSWAGEN_PASSAT_MK8` | MQB-B 平台 |
| 迈腾 | `VOLKSWAGEN_PASSAT_MK8` | MQB-B 平台 |
| 途观L | `VOLKSWAGEN_TIGUAN_MK2` | MQB 平台 |
| 途岳 | `VOLKSWAGEN_TIGUAN_MK2` | MQB 平台 |

## 技术实现细节

### 车型识别流程

1. **固件查询** (`get_fw_versions_ordered`)
2. **VIN 码获取** (`get_vin`)
3. **CAN 指纹识别** (`can_fingerprint`)
4. **环境变量覆盖** (`FINGERPRINT`)

### 关键文件位置

```
opendbc_repo/opendbc/car/volkswagen/
├── values.py          # 车型定义和配置
├── fingerprints.py    # CAN 消息指纹数据
├── interface.py       # 车型接口实现
├── carstate.py        # 车辆状态解析
└── carcontroller.py   # 车辆控制逻辑
```

### 平台架构说明

- **PQ 平台**：老平台（Jetta MK6, Passat NMS）
- **MQB 平台**：新平台（Golf MK7, Tiguan MK2）
- **MLB 平台**：豪华平台（Porsche Macan）

## 调试和故障排除

### 查看当前识别结果

```bash
# 查看日志中的车型识别信息
grep "fingerprinted" /data/logs/current/*.log
```

### 常见问题

1. **车型识别失败**
   - 设置 `FINGERPRINT` 强制指定
   - 检查 CAN 消息是否正常

2. **功能不完整**
   - 确认选择的车型平台匹配
   - 检查 CAN 消息兼容性

3. **启动失败**
   - 验证 `FINGERPRINT` 值是否正确
   - 检查环境变量是否生效

### 验证设置

```bash
# 检查环境变量
echo $FINGERPRINT

# 查看支持的车型列表
python3 -c "
from opendbc.car.volkswagen.values import CAR
for car in CAR: print(car.name)
"
```

## 注意事项

1. **安全警告**：强制指定车型可能导致功能异常，仅用于测试
2. **兼容性**：选择相同平台的车型以确保最佳兼容性
3. **更新**：openpilot 更新后可能需要重新验证车型配置
4. **法律责任**：使用者需承担相关法律责任

## 相关文档

- [安装及编译.md](安装及编译.md) - 环境搭建
- [openpilot_进程启动指南.md](openpilot_进程启动指南.md) - 启动配置
- [openpilot_数据流及格式.md](openpilot_数据流及格式.md) - 数据流分析