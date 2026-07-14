# VW CAN 抓包解析工具

用 DBC 文件解析大众车型的 CAN 抓包数据（cabana 导出的 CSV），
评估关键信号可获取性。用于车型适配前的信号验证。

分析报告见：`learn-docs/车型适配/大众速腾CAN抓包解析报告.md`

## 依赖

```bash
pip install cantools
```

## CSV 格式

cabana 导出格式，表头：`time,addr,bus,data`
- `addr`：十六进制 CAN ID（如 `0x101`）
- `bus`：总线号（0/1/2）
- `data`：十六进制数据（如 `0x1000010524000000`）

## 脚本

| 脚本 | 作用 | 用法 |
|------|------|------|
| `analyze_match.py` | 比较多个 DBC 与数据的地址匹配度，选 DBC | `analyze_match.py <csv> <dbc1> [dbc2 ...]` |
| `decode_can.py` | 解析核心车辆信号（车速/方向盘/档位等）| `decode_can.py <csv> <dbc> [bus]`；加 `--series <消息>.<信号>` 打印完整时间序列（动态验证用，见下）|
| `full_scan.py` | 全量三总线覆盖统计 + 关键信号评估 | `full_scan.py <csv> <dbc>` |
| `acc_radar.py` | ACC 前车雷达距离信号专项评估 | `acc_radar.py <csv> <dbc>` |
| `check_carstate_deps.py` | 核对 carstate.py 依赖消息是否齐全 | `check_carstate_deps.py <csv> <dbc>` |
| `check_lateral_deps.py` | 核查横向控制前提(HCA/EPS/网络位置) | `check_lateral_deps.py <csv> <dbc>` |

## 示例

```bash
cd /home/wio/openpilot
source .venv/bin/activate

CSV=~/cabana_live_stream/"Panda_ 3e001d001051313338343730.csv"
DBC=~/cabana_live_stream/vw_mqb.dbc

python3 tools/vw/can_analysis/analyze_match.py "$CSV" \
    ~/cabana_live_stream/vw_mqb.dbc \
    ~/cabana_live_stream/vw_mqb_2010.dbc
python3 tools/vw/can_analysis/decode_can.py "$CSV" "$DBC"
python3 tools/vw/can_analysis/full_scan.py "$CSV" "$DBC"
python3 tools/vw/can_analysis/acc_radar.py "$CSV" "$DBC"
```

## 动态验证（信号随真实操作变化，非仅存在性检查）

`decode_can.py` 默认只打印 min/max 摘要，无法看出数值变化是否真的跟随了操作时序。
加 `--series` 打印某个信号的完整时间序列，配合"边操作边抓包"（比如转方向盘/挂挡）
可以逐帧核对数值变化是否与操作动作对应：

```bash
# 打印方向盘角度随时间的完整序列（转方向盘时抓的包）
python3 tools/vw/can_analysis/decode_can.py "$CSV" "$DBC" 0 --series LWI_01.LWI_Lenkradwinkel

# 交叉核对 EPS 计算转角（应与上面同步变化）
python3 tools/vw/can_analysis/decode_can.py "$CSV" "$DBC" 0 --series LH_EPS_03.EPS_Berechneter_LW
```

完整的动态验证步骤（转向/挂挡/刹车/车速分场景，含判定标准）见
[learn-docs/车型适配/CAN数据抓取解析验证清单.md](../../../learn-docs/车型适配/CAN数据抓取解析验证清单.md)。

## 已验证结论（24 款速腾，vw_mqb.dbc）

- 车道预测所需信号（车速 `ESP_21.ESP_v_Signal`、方向盘 `LWI_01.LWI_Lenkradwinkel`、
  档位 `Getriebe_11.GE_Fahrstufe`）全部可靠可获取。
- ACC 前车雷达：中配车型硬件在位但功能未编码启用
  （`ACC_06.ACC_Typ = ACC_nicht_codiert`），所有距离/目标信号为空值，
  当前无法获取有效前车距离。
