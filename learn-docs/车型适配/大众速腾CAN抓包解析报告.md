# 大众速腾 CAN 抓包解析报告

> 用 `vw_mqb.dbc` 对 24 款大众速腾的实车 CAN 抓包数据做全量解析，
> 评估车道预测所需关键信号的可获取性，以及 ACC 前车雷达距离情况。

## 一、数据来源

| 项 | 内容 |
|----|------|
| 抓取方式 | openpilot「红熊」+ panda（J533 网关接入）|
| 车辆状态 | 静止、点火 ON（发动机未启动）|
| 时长 | 约 220 秒 |
| 数据量 | 约 111 万帧 CAN |
| 格式 | CSV：`time,addr,bus,data`（cabana 导出）|
| 总线 | bus 0 / bus 1 / bus 2 |
| DBC 候选 | `vw_mqb.dbc` / `vw_mqb_2010.dbc` / `vw_mqbevo.dbc` |

## 二、DBC 选择：vw_mqb.dbc

对三个 DBC 做地址匹配度分析（标准帧交集）：

| DBC | bus 0 | bus 1 | bus 2 |
|-----|-------|-------|-------|
| **vw_mqb.dbc** | **68%** | **61%** | **68%** |
| vw_mqb_2010.dbc | 40% | 50% | 40% |
| vw_mqbevo.dbc | 加载失败* | | |

`vw_mqb.dbc` 匹配度最高，确定为解析基础。这与 `大众车型DBC文件映射分析.md`
中「24 款速腾使用 vw_mqb.dbc」的结论一致，实测得到验证。

> \* vw_mqbevo.dbc 含扩展帧相机报文（`0x12dd54xx`），cantools 加载报错；
> 而 CSV 里确实出现这些扩展帧，提示该车可能属 MQB Evo 平台，但动力总成
> 报文仍与标准 MQB 兼容，`vw_mqb.dbc` 已足够解析全部关键信号。

## 三、全量三总线解析

| 总线 | 标准帧种类 | 可解析 | 扩展帧种类 | 说明 |
|------|-----------|--------|-----------|------|
| bus 0 | 88 | 60 | 21 | 动力总成 CAN（车速/转向/发动机）|
| bus 1 | 111 | 68 | 28 | 更全（含更多网关/舒适报文）|
| bus 2 | 88 | 60 | 21 | bus 0 的镜像转发（J533 网关）|

bus 0 与 bus 2 地址完全相同，是网关镜像。openpilot 读车速/方向盘用 bus 0 即可。

## 四、车道预测关键信号：全部可获取 ✅

所有报文的 CHECKSUM/COUNTER 均正常滚动，证明字节序、位定义解析正确。

| 信号 | 来源 | 实测值（静止点火）| 用途 |
|------|------|------|------|
| 车速 | `ESP_21.ESP_v_Signal` | 0 km/h（静止）| ★模型输入 |
| 四轮转速 | `ESP_19.ESP_*_Radgeschw_02` | 全 0 | 车速交叉校验 |
| 方向盘角度 | `LWI_01.LWI_Lenkradwinkel` | 8.9° | ★模型输入 |
| EPS 计算转角 | `LH_EPS_03.EPS_Berechneter_LW` | 8.7°（与上一致）| 交叉校验 |
| 转向力矩 | `LH_EPS_03.EPS_Lenkmoment` | 14~16 | |
| 横摆角速度 | `ESP_02.ESP_Gierrate` | 可获取 | 定位/校准 |
| 档位 | `Getriebe_11.GE_Fahrstufe` | P（驻车）| 状态判断 |
| 油门 | `Motor_20.MO_Fahrpedalrohwert_01` | 0 | 状态判断 |
| 刹车 | `ESP_05.ESP_Fahrer_bremst` / `ESP_Bremsdruck` | 0 / 0 | 状态判断 |
| 发动机运转 | `Motor_14.MO_Motor_laeuft` | 0（钥匙 ON 位）| |

**结论**：车道显示 + 轨迹预测所需的车速、方向盘角度，均可从 `vw_mqb.dbc`
可靠解析。纯视觉车道预测的 CAN 侧输入已完全打通。

## 五、ACC 前车雷达距离：硬件在位，功能未启用 ⚠️

### 车辆配置背景

该车为**中配车型**：物理上**装有前雷达传感器**，但 **ACC 功能未编码启用**。
CAN 抓包数据完全印证了这一点。

### CAN 证据

ACC/前雷达报文在总线上**活跃广播**（说明相关 ECU/传感器在位）：

| 报文 | 帧数（bus 0）|
|------|------|
| ACC_06 | 11012 |
| ACC_10 | 11012 |
| TSK_06 | 11016 |
| GRA_ACC_01 | 7344 |
| ACC_02 / ACC_04 | 3670 |
| TSK_08（前雷达）| 2203 |

但解析出的信号内容全部是「未编码 / 无数据 / 未激活」状态：

| 信号 | 解析结果 | 含义 |
|------|---------|------|
| `ACC_06.ACC_Typ` | **`ACC_nicht_codiert`** | **ACC 未编码** |
| `ACC_06.ACC_Status_ACC` | `reversibler_Fehler` | ACC 系统故障态（功能未启用）|
| `ACC_02.ACC_Relevantes_Objekt` | `Symbol_nicht_beleuchtet` | 无前车目标显示 |
| `ACC_02.ACC_Abstandsindex` | `graue_Fahrbahn` | 无有效距离 |
| `ACC_04.ACC_Abstand_Abstandswarner` | 0 | 距离等级空 |
| `ACC_04.ACC_Zeitluecke_Abstandswarner` | 0 s | 时距空 |
| `ACC_10.PCF_Time_to_collision` | TTC > 最大值 | 无碰撞目标 |
| `TSK_08.TSK_aktives_System` | `keine_Funktion_aktiv` | 无功能激活 |
| `GRA_ACC_01.GRA_Hauptschalter` | 0 | 巡航主开关关 |
| `ACC_07`（含米数停车距离）| 报文未出现 | 无此数据 |

### 结论

1. **当前无法获取有效的前车雷达距离**。传感器硬件在位、报文框架在总线广播，
   但因 ACC 未编码启用，所有距离/目标/TTC 信号均为空值。这与车辆静止无关，
   即便前方有目标也读不到。

2. **`vw_mqb.dbc` 本身不含「原始雷达距离（米）」信号**。MQB 前雷达的原始距离
   由 Frontradar 通过专有报文/扩展帧（数据中的 `0x12dd54xx`）发送，DBC 不解析。
   DBC 仅提供仪表显示用的距离指数 / 距离等级 / TTC，非米数。

3. **对本项目目标无影响**。目标是「车道显示 + 轨迹预测，不控车」，仅需车速 +
   方向盘，已全部可获取。前车距离（跟车/AEB 用）本不在范围内。

### 若将来需要前车距离

- **硬件路线**：为前雷达做 ACC 编码（需诊断设备，改动较大）。
- **视觉路线（推荐）**：openpilot 驾驶模型 `modelV2` 能从摄像头预测 **lead car
  距离**（`leadsV3`），与已跑通的车道线预测同源、无需雷达，基本零成本。

## 六、复现方法

解析脚本位于 `tools/vw/can_analysis/`：

```bash
cd /home/wio/openpilot
source .venv/bin/activate

# DBC 匹配度分析（选 DBC）
python3 tools/vw/can_analysis/analyze_match.py <csv> <dbc1> [dbc2 ...]

# 关键信号解析（车速/方向盘/档位等）
python3 tools/vw/can_analysis/decode_can.py <csv> <dbc>

# 全量三总线解析统计
python3 tools/vw/can_analysis/full_scan.py <csv> <dbc>

# ACC 前车雷达距离专项评估
python3 tools/vw/can_analysis/acc_radar.py <csv> <dbc>
```

依赖：`cantools`（`pip install cantools`）。
