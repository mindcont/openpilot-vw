# 第二阶段：接入真实 CAN 实车任务清单（只读，不控车）

> 状态：🔄 未开始。前置可行性评估见
> [第二阶段_接入CAN可行性评估.md](第二阶段_接入CAN可行性评估.md)（结论：能，完全满足
> 车道显示+预测的需求）。本文档是把评估落到实车的**分步执行清单**，核心底线：
> **CAN 只读，任何情况下不向总线发送任何数据**。每一步都先做只读校验，通过才进
> 下一步；任何一步发现异常（哪怕不确定），立即物理拔线/断电，不继续。

## 零、安全设计基线（已落地，实车前必须先复核）

项目在 [环境搭建与容器部署.md](../环境搭建与容器部署.md) 第十五节做过一次风险分析，
结论是：`PASSIVE`/`NOBOARD` 这两个环境变量**没有任何代码读取它们**，是摆设，真正
决定 panda 会不会向 CAN 发送数据的是下面两道闸门：

| 闸门 | 机制 | 落地状态 |
|------|------|---------|
| 第一道·软件 | `Params().put_bool("OpenpilotEnabledToggle", False)` → `card.py` 重算 `passive=True` → `safetyConfigs=[noOutput]` | ✅ 已写入 `start_openpilot.sh`/`start_openpilot_orinnx.sh` |
| 第二道·硬件 | `panda.health()` 直接核实固件 `safety_mode ∈ {silent, noOutput}` 且 `controls_allowed==0` | ✅ 脚本已建：`tools/vw/check_panda_readonly.py` |

**这两道闸门是在"无真实 panda/CAN"场景下设计的，还没有在真实 panda + 真实 CAN 场景
下验证过**。接入真车后 `card.py` 不再阻塞（会收到真实 CAN 包），会走到之前从未走过的
`get_car()` 真实识别分支，所以第一步必须是**代码走查复核**，不能假设结论依然成立。

### 待复核问题（实车接入前，在本地/远程先做完，不需要车）

- [x] **R1. 复核 `card.py` 真实识别分支下，两道闸门是否依然生效** ✅ 2026-07-15 确认

  **结论：生效。** `card.py` 第 113-119 行的重算逻辑
  （`openpilot_enabled_toggle`判断 → `self.CP.passive` → `safetyConfigs=[noOutput]`）
  在 `if CI is None`（真实识别）与 `else`（注入）两个分支**之后统一执行，代码路径
  不分叉**。无论 `CI` 是通过 `get_car()` 真实识别出来的，还是外部注入的，走到这里
  都会用同一段代码重算 `passive`。`OpenpilotEnabledToggle=False` 时
  `controller_available=False` → `self.CP.passive=True` → `safetyConfigs`
  被强制覆盖为 `[noOutput]`，与 `CI` 的来源无关。**闸门在真实 CAN 场景下依然生效**。

- [x] **R2. 复核 `pandad` 的安全模式切换时序，是否存在"中途可写"的时间窗口**
  ✅ 2026-07-15 确认，**发现一个需要新增防护的点**

  **(a) 写入时序无中间态风险**：`self.CP.to_bytes()` 写入 `CarParams` 时，
  `passive`/`safetyConfigs` 的赋值已在同一次 `__init__` 同步代码里完成。
  `pandad` 侧 `fetchCarParams()` 要 `FirmwareQueryDone` **和** `ControlsReady`
  都为真才读取 `CarParams`；而 `ControlsReady` 只在 `controls_update()` 里置位，
  `controls_update()` 只在 `self.CP.passive=False` 时才会被 `step()` 调用。
  `OpenpilotEnabledToggle=False` → `passive` 恒为 `True` → `controls_update()`
  永远不被调用 → `ControlsReady` 永远不会置位 → `pandad.setSafetyMode()`
  **永远不会执行，panda 固件会一直停留在初始的 `ELM327` 模式，绝不会被切换到
  真实车型的可控 safety mode**。这条链路是自洽的，无中途可写窗口。

  **(b) ELM327 模式本身允许发送标准诊断帧 —— 之前设计未充分考虑，需新增防护**：
  查阅 `opendbc_repo/opendbc/safety/modes/elm327.h` 的 `elm327_tx_hook`，
  **确认它允许发送 ISO 15765-4 标准诊断帧**（8 字节，地址在
  `0x18DB33F1`/`0x18DA00F1`系/`0x600-0x6FF`/`0x700-0x7FF` 等诊断地址范围）。
  `SKIP_FW_QUERY=1` 只能让 `car_helpers.py` 的 `fingerprint()` 跳过
  `get_vin()`/`get_present_ecus()`/`get_fw_versions_ordered()` 这些**openpilot
  软件层主动发起**固件查询的代码路径，**不能改变 panda 固件本身处于的
  safety_model**——固件既然停留在 ELM327（见 (a)），理论上任何触发 TX 的路径都
  会被这个 hook 放行（只要符合诊断帧格式），不只是 `fingerprint()` 那一条路径。

  **已处理**：`tools/vw/check_panda_readonly.py` 已更新，把 `elm327`（值=3）单独
  归为"需人工确认"档（区别于 `silent`/`noOutput` 的"完全静默"），脚本会明确提示
  该模式允许发送诊断帧、不是绝对零发送，退出码非0需要人工判断是否可接受。
  **结论：ELM327 不会发送转向/加速等控制指令（最大风险已封死），但严格来说不是
  100% 零发送，如需更高保证需要评估 R3 物理层防线。**

- [x] **R3. 评估是否需要第三道防线：物理层只读** ✅ 2026-07-15 决定：暂不追加

  确认现有硬件是**普通双向读写 panda**（非专用只读嗅探设备），没有现成的物理层
  TX 禁用条件。**决定：不追加物理层防线，用现有软件+固件双闸门方案继续**。
  依据：R2 已确认最大风险（切换到真实车型可控 safety mode 发送转向/加速指令）
  被完全封死；ELM327 阶段允许的诊断帧风险已知且可接受（不是行驶控制报文，
  `check_panda_readonly.py` 会在检测到 ELM327 时提示需人工关注）。若后续想进一步
  收紧，可以考虑单独采购只读嗅探硬件，但不阻塞当前验证。

- [x] **R4. 确认之前 CAN 抓包时的接入方式是否还在车上** ✅ 2026-07-15 决定：走 J533 网关

  **决定接入点：复用 J533 网关**（[大众速腾CAN抓包解析报告.md](大众速腾CAN抓包解析报告.md)
  记录过的接入方式，已验证信号完整性最高，17/17 carState 依赖消息全部可获取）。
  需要在下面「二、Day 0：物理接线」步骤 3 现场确认：
  1) 之前抓包那次接线是否还物理连着车，还是已经拆了需要重新接
  2) 如果还连着，核对具体是哪块 panda（型号/固件版本），能否直接复用
  不选 OBD-II 路线（未验证过该接入点能否透传目标信号，J533 已验证过，优先复用
  已验证路径）。

## 一、准备阶段（不接车，纯静态验证）

- [ ] **1. 确认 panda 硬件与固件**
  `lsusb` 确认识别到 panda；跑 `python3 -c "from panda import Panda; p = Panda(); print(p.get_version())"`
  确认固件版本；跑 `tools/vw/check_panda_readonly.py` 确认默认态是只读
  （初始应为 ELM327/silent，`controls_allowed=0`）。**此步不接车，纯 USB 接 Orin NX**。

- [ ] **2. 准备"真实 CAN 版"启动脚本（区别于当前纯视觉版）**
  当前 `start_openpilot_orinnx.sh` 是 `NOBOARD=1` + 看门狗注入 `CarParams` 的纯视觉
  路径，接入真实 CAN 后这条路径不再适用（`card` 不会阻塞，会自己走真实识别）。
  需要建一个新版本或加分支开关，改动点：
  - 去掉 `NOBOARD=1`（让 `pandad` 正常连接真实硬件）
  - 去掉看门狗 `CarParams` 注入器（不再需要，`card` 会自己写）
  - **保留** `OpenpilotEnabledToggle=False` 只读闸门（这是接真车后最重要的一行，
    不能删）
  - 保留 `FINGERPRINT=VOLKSWAGEN_SAGITAR_MK7` + `SKIP_FW_QUERY=1`（跳过固件查询，
    避免走 R2 提到的诊断请求路径，且 `FW_VERSIONS`/`chassis_codes` 还是占位，自动
    识别大概率识别不出来，继续用强制指定）
  - `FORCE_ONROAD` 是否还需要：接入真实点火信号（钥匙 ON）后，`hardwared` 应该能
    正常检测到 ignition，理论上不再需要强制；但保留也无害，可先保留过渡
  - 建议：先另存一个新文件（如 `start_openpilot_orinnx_can.sh`），不要直接改现在
    跑得好的纯视觉版本，两者独立，方便随时切回纯视觉验证基线

## 二、Day 0：物理接线（车辆熄火，钥匙 OFF）

- [ ] **3. 物理接线**
  按 R4 确认的接入点（J533 网关或 OBD-II）接线。全程车辆熄火、钥匙 OFF，避免热插拔
  引发仪表报故障码。接完先不给车上电，不接 Orin NX。

- [ ] **4. 接线核对**
  万用表核对线序（尤其 CAN-H/CAN-L 不能接反），确认接头卡到位、无短路。

## 三、Day 1：钥匙 ON，静止，发动机不启动（风险最低的首次通电）

**每一小步之间都跑一次 `check_panda_readonly.py`，全程不离手机/笔记本。**

- [ ] **5. 上电前只读核实**
  Orin NX 接 panda（USB），车辆钥匙还是 OFF：跑 `check_panda_readonly.py`，
  确认默认态只读。

- [ ] **6. 钥匙 ON（发动机不启动），观察 CAN 总线原始流量（不启动 openpilot）**
  用 `cabana` 或 `can_capture_daemon` 之类工具**只监听**，确认能收到 CAN 帧（说明
  接线通），且**此时还没启动 openpilot 相关进程**，总线上不应有任何来自 Orin/panda
  的新增地址（用之前 J533 抓包的地址列表做基线比对，若接线正确、只读，总线上的
  报文种类应该和以前抓包时一致，不多不少）。

- [ ] **7. 再次只读核实**
  `check_panda_readonly.py` 再跑一次，确认收到真实 CAN 帧后固件状态没有变化
  （还是只读）。

- [ ] **8. 启动"真实 CAN 版"openpilot（步骤 2 准备的脚本）**
  观察：
  1) `card.py` 是否正常初始化，`FINGERPRINT` 强制指定是否生效
  2) `carState` 是否开始正常产出（用之前验证过的
     `cereal.messaging.SubMaster(['carState'])` 订阅脚本）
  3) `vEgo`/方向盘角度等信号是否与仪表显示一致（车速应为 0，方向盘角度可转动方向盘
     观察是否跟随变化）

- [ ] **9. openpilot 运行期间持续只读核实**
  openpilot 跑起来之后，每隔 10-20 秒跑一次 `check_panda_readonly.py`（可以写个循环
  脚本），观察至少 2-3 分钟，确认全程 `safety_mode` 保持 `noOutput`、
  `controls_allowed` 恒为 0，没有任何时刻翻转成可写状态。

- [ ] **10. 再用 cabana 交叉核对总线流量**
  openpilot 跑起来之后，总线上的报文种类/地址集合应该和步骤 6（openpilot 未启动时）
  完全一致，**不应该多出任何新地址**（这是脱离 openpilot 框架代码本身、纯从总线
  物理层面的独立验证，比只看软件日志更可信）。

- [ ] **11. 确认车道预测链路未受影响**
  订阅 `modelV2`，确认 `laneLineProbs` 依然正常产出（这一步接入真实 CAN 主要是让
  `vEgo` 从 demo 假定值变成真实值，理论上不影响车道线本身有没有输出，只影响预测
  准不准）。

## 四、Day 2：静止场景，长时间运行稳定性

- [ ] **12. 同 Day1 场景，运行 30 分钟以上**
  持续每隔 1-2 分钟跑 `check_panda_readonly.py`，观察长时间运行是否有任何异常
  （固件重启、参数被意外重置为默认值 `OpenpilotEnabledToggle=1` 等）。
  重点关注 `OpenpilotEnabledToggle` 是 `PERSISTENT` 参数——理论上不会被程序自己
  改回 `True`，但如果 UI 上有开关入口，需要确认没有人为误触。

- [ ] **13. carState 完整性核对（对照可行性评估的 17 个信号）**
  用 `tools/vw/can_analysis/check_carstate_deps.py` 或直接订阅 `carState` 各字段，
  确认此前静态解析验证过的 17 个 carState 依赖信号在实际动态运行下都能拿到、
  刷新率正常（之前只验证过静止抓包的静态解析，没验证过实时刷新率）。

## 五、Day 3：低速移动场景（非道路，比如挪车/倒车）

- [ ] **14. 低速移动，确认车速信号真实变化**
  在安全的封闭场地（不是开放道路）挪动车辆，确认 `vEgo` 随实际车速变化，
  `calibrationd` 能否开始在线标定（第二阶段评估里提到的"车速+相机里程计做在线标定，
  替代 demo 的固定 rpy=[0,0,0]"）。

- [ ] **15. 移动场景下依然全程只读核实**
  同样的 `check_panda_readonly.py` 循环 + cabana 总线比对，确认车辆运动状态下
  防护依然生效（不应有任何差异，但仍需实测确认，不能假设静止场景验证过就代表
  移动场景也一定没问题）。

## 六、Day 4+：开放道路场景（仍不控车）

- [ ] **16. 开放道路测试**
  确认前面所有验证都通过后，才考虑开放道路测试。全程车道预测 + 真实 carState，
  持续观察 `laneLineProbs`、`vEgo`、在线标定效果，以及**全程只读核实**（建议用
  第三方乘客专职盯 `check_panda_readonly.py` 的循环输出或 CAN_DEBUG 叠加层）。

## 七、收尾

- [ ] **17. 文档归档**
  把实测结论（哪个接入点用的、panda 型号、实际验证到哪一步、有无异常）补进本文档
  或汇总进 [第二阶段_接入CAN可行性评估.md](第二阶段_接入CAN可行性评估.md)。

- [ ] **18. 代码收尾**
  确认"真实 CAN 版"启动脚本是否要合并回主脚本或保持独立文件，更新
  [README.md](../README.md) 索引。

## 中止条件（任何一步出现，立即物理拔线，停止测试）

- `check_panda_readonly.py` 报告 `safety_mode` 不是 `silent`/`noOutput`，或
  `controls_allowed != 0`
- cabana 观察到总线上出现了之前基线没有的新地址（可能意味着 panda 发送了东西）
- 仪表出现任何异常报警/故障灯
- 车辆有任何非驾驶员操作引起的意外反应（转向盘力矩变化、灯光变化等，哪怕很轻微）

## 相关文档 / 工具

| 文件 | 用途 |
|------|------|
| [第二阶段_接入CAN可行性评估.md](第二阶段_接入CAN可行性评估.md) | 信号可获取性的前置评估结论 |
| [大众速腾CAN抓包解析报告.md](大众速腾CAN抓包解析报告.md) | 已验证的 J533 接入 + vw_mqb.dbc 解析结论 |
| [../环境搭建与容器部署.md](../环境搭建与容器部署.md) 第十五节 | 只读双闸门方案的完整风险分析与设计 |
| `tools/vw/check_panda_readonly.py` | 第二道硬件闸门核实脚本 |
| `tools/vw/can_analysis/check_carstate_deps.py` | carState 依赖信号核对 |
| [../硬件改造.md](../硬件改造.md) | J533 网关接线方式参考 |
