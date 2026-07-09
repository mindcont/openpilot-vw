# 第二阶段：接入 CAN 总线可行性评估（不控车 + 车道预测）

> 评估在「不控车」前提下，接入真实 CAN 总线能否满足车道显示、轨迹预测、
> 车速等功能的全部条件。基于 `vw_mqb.dbc` 与 J533 实车抓包数据核验。

## 结论

**能，完全满足**，且相比纯视觉 demo 是质的提升。唯一拿不到的前车雷达距离
不在「车道显示 + 预测、不控车」的目标范围内。

## 一、车道预测的真实 CAN 需求（最小集）

驱动模型 `modeld` 对 CAN 的唯一硬需求是 **车速 `vEgo`**（模型辅助输入），
外加 `carControl.latActive`（不控车时恒为 False，只影响变道意图，不影响车道线本身）。

| 需求 | 信号源 | 状态 |
|------|--------|------|
| 车速 `vEgo` | `ESP_19` 四轮速 | ✅ 已验证可获取 |

即：车道线预测本身，CAN 侧只需车速。

## 二、carState 完整产出（car 进程正常运行）

接入真实 CAN 后，`card.py → CarInterface → CarState`（`opendbc/car/volkswagen/carstate.py`）
需解析其引用的全部消息。实测 **17/17 消息在 bus0 全部存在**，carState 可完整产出：

| 能力 | 信号源 | ID | 状态 |
|------|--------|----|----|
| 车速（四轮速→vEgo）| `ESP_19.ESP_*_Radgeschw_02` | 178 | ✅ |
| 仪表车速 / 手刹 | `Kombi_01.KBI_angez_Geschw / KBI_Handbremse` | 779 | ✅ |
| 方向盘角度 / 转速 | `LWI_01.LWI_Lenkradwinkel / ...Geschw` | 134 | ✅ |
| 转向力矩 / EPS 状态 | `LH_EPS_03.EPS_Lenkmoment / EPS_HCA_Status` | 159 | ✅ |
| 档位 | `Gateway_73.GE_Fahrstufe` | 988 | ✅ |
| 油门 | `Motor_20.MO_Fahrpedalrohwert_01` | 289 | ✅ |
| 刹车踏板 | `Motor_14.MO_Fahrer_bremst` | 958 | ✅ |
| 制动压力 / 刹车 | `ESP_05.ESP_Bremsdruck / ESP_Fahrer_bremst` | 262 | ✅ |
| ESP 状态 / 驻停 | `ESP_21.ESP_Eingriff / ESP_Haltebestaetigung` | 253 | ✅ |
| 安全带 | `Airbag_02.AB_Gurtschloss_FA` | 1312 | ✅ |
| 车门 | `Gateway_72.ZV_*_offen` | 987 | ✅ |
| 转向灯 | `Blinkmodi_02.Comfort_Signal_*` | 870 | ✅ |
| 巡航状态 | `TSK_06.TSK_Status` | 288 | ✅ |
| ACC 设定速度 / 时距 | `ACC_02.ACC_Wunschgeschw_02` | 780 | ✅(空值) |
| ACC 类型 | `ACC_06.ACC_Typ` | 290 | ✅(未编码) |
| stock FCW/AEB | `ACC_10` | 279 | ✅ |
| 巡航按钮透传 | `GRA_ACC_01` | 299 | ✅ |

> 注意档位信号源：carstate.py 用的是 `Gateway_73.GE_Fahrstufe`，不是首轮全量
> 解析里看到的 `Getriebe_11.GE_Fahrstufe`。两者都在总线上，carstate 用的正确。

## 三、在线标定（calibrationd）—— 解决 demo 痛点

`calibrationd` 需要 **车速 + 相机里程计** 做在线标定。车速可获取，行驶中能自动
标定出真实 rpy 外参，**替代 demo 里 hardcode 的 `rpy=[0,0,0]`**，直接改善车道线
投影精度（demo 的固定标定是已知近似）。

## 四、不控车安全性

- `PASSIVE=1` / dashcam 模式：只读不写，不发送任何转向/油门/刹车指令。
- 即使 `accFaulted`（因 ACC 未编码），不控车模式下不影响车道预测。
- 接入真车后可评估用真实点火信号替代 `FORCE_ONROAD`。

## 五、唯一缺口：前车距离（不影响目标）

CAN 拿不到有效前车距离（ACC 未编码，见《大众速腾CAN抓包解析报告.md》）。
车道显示 + 轨迹预测不需要它；若将来需要，用视觉 `modelV2.leadsV3`（摄像头预测）。

## 六、相比纯视觉 demo 的提升

| 维度 | demo（纯视觉）| 接入 CAN 后 |
|------|--------------|------------|
| 车速 | hardcode 20 m/s | **真实车速** → 预测更准 |
| 标定 | 固定 rpy=[0,0,0] | **在线标定** → 投影更准 |
| 车辆状态 | 全部模拟 | **真实档位/刹车/转向灯** |
| 方向盘 | 无 | **真实转向角** |

## 七、注意事项

1. **总线选择**：`LH_EPS_03 / Gateway_73 / ACC_02` 在 bus1 缺失但 bus0 全有；
   openpilot 读 `Bus.pt`（动力总成 = bus0），正确。
2. **CarParams 配置**：速腾为 DSG 自动变速箱 → `transmissionType=automatic`
   （用 Gateway_73 读档位），数据里 `GE_Fahrstufe=P` 印证自动挡，匹配；
   `FINGERPRINT=VOLKSWAGEN_GOLF_MK7` 已配置。
3. **CANParser valid 检查**：所有消息在总线且按频率刷新，valid 应能通过；
   实车接入后需确认各消息实际刷新率达标。
4. **网络位置 networkLocation**：需确认相机网络位置（fwdCamera / gateway），
   影响 `ext_cp` 从哪条总线取 ACC 报文；本项目不控车、不读 ACC，影响有限。

## 八、延伸:完整 openpilot(控车)可行性

> 本项目定位是**不控车纯视觉预测**。此节仅评估「若将来要跑完整 openpilot(横向+纵向
> 控车)」的前提,供参考。控车是完全不同的安全等级,涉及法规与安全责任。

### 横向控制(转向)—— 实测硬件前提基本具备

`check_lateral_deps.py` 对抓包核查(基于 opendbc MQB `carcontroller.py`/`interface.py`):

| 判据 | 结果 | 含义 |
|------|------|------|
| `HCA_01` (0x126) | ✓ bus0/bus2 | 有原厂车道保持相机(R242),转向报文在总线广播 |
| `LDW_02` (919) | ✓ bus0/bus2 | 有原厂车道偏离警告 |
| `LH_EPS_03.EPS_HCA_Status` | `initializing`(非 DISABLED) | EPS 支持 HCA 转向注入,不拒绝 |
| networkLocation | gateway | bus0 命中 Airbag_01/LWI_01/ESP_19/ESP_21 |

**结论**:该中配速腾**物理具备原厂车道保持(Lane Assist)硬件**,EPS 也配置了接受
转向注入的能力。这修正了早前"中配可能无 Lane Assist"的猜测。
`interface.py` 会因 `0x126 in fingerprint[2]` 置 `STOCK_HCA_PRESENT`,openpilot 可拦截
并替换相机 HCA 报文实现转向。

### 纵向控制 —— 需开通 ACC

- 开通(编码激活)前雷达 ACC 后,`pcmCruise` 模式借用**原厂 ACC** 做纵向跟车
  (VW `radarUnavailable=True`,openpilot 不直接用雷达点,由原厂 ACC 处理)。
- openpilot 自控纵向(`openpilotLongitudinalControl`)是实验性:需 Panda ALLOW_DEBUG
  固件、无雷达点(靠视觉 E2E),不推荐。

### 剩余的真正门槛(硬件为主)

| 条件 | 状态 | 说明 |
|------|------|------|
| 横向硬件(HCA/EPS)| ✅ 基本具备 | 实测 HCA_01 + EPS 支持 |
| 开通 ACC(纵向)| 待编码 | 编码激活前雷达 |
| **可写 panda + 相机中间人 harness** | ❌ **主要门槛** | 当前旁路只读,控车需接在 R242 相机与车之间并能写 CAN |
| 去 PASSIVE/NOBOARD、在线标定、驾驶员监控 | 待配置 | 软件层面 |

### 待坐实的不确定性

1. `EPS_HCA_Status` 静止为 `initializing`,需**行驶中验证能到 `READY`/`ACTIVE`**。
2. 最终以**车辆配置单 / EPS 编码**为准,静止抓包为强提示但非编码级确认。

## 九、复核方法

```bash
cd /home/wio/openpilot && source .venv/bin/activate
# carState 依赖消息核对(纵向/预测所需)
python3 tools/vw/can_analysis/check_carstate_deps.py <csv> <dbc>
# 横向控制前提核查(HCA/EPS/网络位置)
python3 tools/vw/can_analysis/check_lateral_deps.py <csv> <dbc>
```
