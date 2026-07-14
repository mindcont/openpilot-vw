# 第二阶段：接入真实 CAN 实车任务清单（只读，不控车）

> 状态：🔄 进行中（2026-07-15）。零/一/二已全部完成，三的步骤 5-7 已通过，步骤 8
> 遇到技术卡点（`pandad` 未能从 panda 读到真实 CAN 数据转发给 `card`，详见步骤 8
> 记录），已安全收尾，明天继续排查。前置可行性评估见
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

- [x] **1. 确认 panda 硬件与固件** ✅ 2026-07-15
  Orin NX 上 `lsusb` 确认识别到 panda（`ID 3801:ddcc comma.ai panda`，序列号
  `3e001d001051313338343730`，与 [环境搭建与容器部署.md](../环境搭建与容器部署.md)
  第七节记录的是同一块硬件）。`Panda().get_version()` → `DEV-3dd38b76-DEBUG`。
  `check_panda_readonly.py` 确认默认态：`safety_mode=0(silent)`，
  `controls_allowed=0`，退出码 0（完全静默，不是 ELM327——说明当前未连接真实
  CAN/未跑过 pandad，固件停在上电默认态）。**此步未接车，纯 USB 接 Orin NX**。

- [x] **2. 准备"真实 CAN 版"启动脚本（区别于当前纯视觉版）** ✅ 2026-07-15

  新建独立文件 `start_openpilot_orinnx_can.sh`（未改动现有跑得好的纯视觉版
  `start_openpilot_orinnx.sh`，两者独立，可随时切回纯视觉基线）。改动点：
  - 去掉 `NOBOARD=1`：让 `pandad` 正常连接真实 panda 硬件
  - 去掉看门狗 `CarParams` 注入器：`card.py` 收到真实 CAN 后自己走
    `get_car()` 识别并写入
  - **保留** `OpenpilotEnabledToggle=False`（脚本内注释标注"最重要的一行，
    不能删"，并引用 R1 复核结论说明为何对真实识别路径同样生效）
  - 保留 `FINGERPRINT=VOLKSWAGEN_SAGITAR_MK7` + `SKIP_FW_QUERY=1`（注释引用 R2
    复核结论说明这是为了避开主动发 CAN 请求的固件查询路径）
  - `FORCE_ONROAD=1` 暂保留（先减少变量，跑通后再评估是否切换成真实 ignition）
  - 摄像头/曝光/UI 配置与纯视觉版保持一致（复用已验证过的默认值）
  - 脚本内多处注释直接指向本清单对应章节，方便现场执行时查阅依据
  `bash -n` 语法检查通过；内嵌 python heredoc 块单独 `ast.parse` 语法检查通过。

## 二、Day 0：物理接线（车辆熄火，钥匙 OFF）

- [ ] **3. 物理接线**
  按 R4 确认的接入点（J533 网关或 OBD-II）接线。全程车辆熄火、钥匙 OFF，避免热插拔
  引发仪表报故障码。接完先不给车上电，不接 Orin NX。

- [ ] **4. 接线核对**
  万用表核对线序（尤其 CAN-H/CAN-L 不能接反），确认接头卡到位、无短路。

## 三、Day 1：钥匙 ON，静止，发动机不启动（风险最低的首次通电）

**每一小步之间都跑一次 `check_panda_readonly.py`，全程不离手机/笔记本。**

- [x] **5. 上电前只读核实** ✅ 2026-07-15

  J533 网关接线完成（用户已现场核对线序、接头卡到位），车辆钥匙 OFF：
  - `check_panda_readonly.py`：`safety_mode=0(silent)`，`controls_allowed=0`，
    退出码 0（完全静默）
  - `panda.health()` 交叉核实：`voltage=12441mV`（12.4V，车辆已通过 harness 供电，
    接线确认导通）、`ignition_line=0`（熄火状态，与实际钥匙位置一致，从硬件层面
    独立验证了车辆状态，不只是听口头确认）、`ignition_can=0`、
    `car_harness_status=1(normal)`、`fault_status=0`（无故障）
  - `car_harness_status` 说明：查 `panda/board/drivers/harness.h` 源码确认，
    `normal`/`flipped` 指 panda 与 harness 盒之间连接器的插入方向（类似 USB-C
    双向可插），firmware 自动检测并适配两种方向的 GPIO 映射，**不是故障或安全
    问题**，纯粹是这次插接方向与 [环境搭建与容器部署.md](../环境搭建与容器部署.md)
    第七节记录的上次（`flipped`）不同，两种方向 panda 都能正确处理。

- [x] **6. 钥匙 ON（发动机不启动），观察 CAN 总线原始流量（不启动 openpilot）** ✅ 2026-07-15

  钥匙 ON、openpilot 相关进程确认未启动（`pgrep` 确认 manager/selfdrive/webcam
  全部未运行）时，用新建的 `tools/vw/can_analysis/passive_listen.py`
  （只调用 `can_recv()`，从不调用 `can_send`）监听 15 秒：
  - 15 秒内收到 79565 帧，三条总线（0/1/2）均有数据，接线确认通
  - `ignition_line=1`，与实际钥匙 ON 状态一致
  - 监听前后 `safety_mode=0(silent)`/`controls_allowed=0` **完全未变化**，纯监听
    没有对 panda 状态产生任何影响
  - bus0 103 种地址，与 [大众速腾CAN抓包解析报告.md](大众速腾CAN抓包解析报告.md)
    记录的历史基线（88 个标准帧+21 个扩展帧）量级一致，未见异常暴增

  进一步用同样纯监听方式采集 12 秒 CSV（`/tmp/capture_can_csv.py`，监听前后同样
  确认 `safety_mode`/`controls_allowed` 无变化），跑现成解析脚本核对：
  ```
  check_carstate_deps.py: 17/17 carState 依赖消息全部命中，且全部在 bus0
  ```
  抽查关键信号数值自洽性（比历史静态抓包报告更进一步，这次是钥匙 ON 场景）：
  - `ESP_19` 四轮速全部 `0.000`（车辆静止，发动机未启动，符合预期）
  - `Getriebe_11.GE_Fahrstufe = 'P'`（停车挡，符合当前场景）
  - `LWI_01.LWI_Lenkradwinkel=16.700°` 与 `LH_EPS_03.EPS_Berechneter_LW=16.200°`
    两个独立信号源互相印证（相差 0.5° 在合理误差范围），确认方向盘角度信号映射
    正确，不是巧合数值
  - `LH_EPS_03.EPS_HCA_Status='initializing'`，与历史报告记录的结论一致

  **结论：接线确认通、carState 依赖信号 17/17 全部可获取且数值自洽、纯监听全程
  未改变 panda 安全态。**

- [x] **7. 再次只读核实** ✅ 2026-07-15
  步骤 6 收到大量真实 CAN 帧（79565+64482 帧）之后再跑 `check_panda_readonly.py`：
  `safety_mode=0(silent)`，`controls_allowed=0`，退出码 0，与步骤 5 的上电前基线
  完全一致。确认接收大量真实 CAN 数据不会对 panda 固件安全态产生任何影响。

- [ ] **8. 启动"真实 CAN 版"openpilot（步骤 2 准备的脚本）** 🔄 进行中，2026-07-15
  中断，明天继续

  首次用 `start_openpilot_orinnx_can.sh`（`SINGLE_CAM=1`）启动，发现 `card.py`
  卡住，`carState` 15 秒内 0 帧。排查过程与当前定位（**未修复，留给下次接手**）：

  **表面现象**：`card` 进程 CPU 占用低但存活，`FirmwareQueryDone`/`ControlsReady`
  均为 `False`，`CarParams` 不存在。`py-spy dump`（用 `sudo -S` 传密码后可用，
  `~/.local/bin/py-spy`）两次采样均确认卡在 `card.py:88`
  （`messaging.recv_one_retry(self.can_sock)`，即等待第一条**非空** CAN 包）。

  **关键诊断发现**：
  1. 直接用 `panda` Python 库连接（绕开 `pandad`）能正常收到大量真实 CAN 帧
     （之前步骤 6/7 已验证），说明硬件、接线、panda 固件本身没问题。
  2. 但订阅 `pandad` 发布的 `can` 消息通道（`cereal.messaging.SubMaster(['can'])`
     或直接 `sub_sock('can')`+`receive()`），收到的消息**频率正常**（近 100Hz，
     心跳级别），但消息里的 `can` 字段（实际 CAN 帧列表）**持续为空**
     （多次采样，数百到近千条消息，`nonempty` 计数均为 0）。
  3. 追查 `selfdrive/pandad/pandad.cc` 的 `can_receive()`：从 panda bulk endpoint
     `0x81` 读数据，`bulk_read` 返回 0 字节时不解包，`can` 字段自然为空——问题
     指向 `pandad` 从 panda 硬件读 USB bulk 数据这一步没有读到东西。
  4. 追查 `panda_safety.cc` 的 `configureSafetyMode(is_onroad)`：只有
     `is_onroad=True` 才会执行 `updateMultiplexingMode()`（切到 `ELM327`
     并开始正常的多路复用/CAN 转发配置流程）。`is_onroad` 来自
     `params.getBool("IsOnroad")`——**这是一个独立于 `FORCE_ONROAD` 环境变量的
     Param**，由 `system/manager/helpers.py` 的 `write_onroad_params(started, ...)`
     写入，`started` 来自 `hardwared.py` 算出的 `deviceState.started`。
  5. 实测 `safety_mode` 稳定读到 `19(noOutput)`（不是 `updateMultiplexingMode()`
     应该设置的初始值 `ELM327(3)`），且从未变化——**怀疑 `pandad` 从未真正执行过
     这条初始化路径**，当前的 `noOutput` 可能是 panda 硬件断电前遗留的状态
     （safety_mode 不是每次都会被重置，取决于是否真正走到 `setSafetyMode()`）。

  **当前假设（未证实，明天first要验证）**：`IsOnroad` 这个 Param 在本次运行期间
  可能一直是 `False`（或者写入时序落后于 `card`/`pandad` 读取的时间点），导致
  `pandad` 的 `configureSafetyMode` 从未真正把 panda 切到正常 CAN 转发模式。
  这与 [环境搭建与容器部署.md](../环境搭建与容器部署.md) 第十五节记录过的
  `IsOnroad` stale 状态坑是同一个 Param，但表现方向相反（那次是 stale `True`
  导致过早注入，这次疑似 `False`/时序不对导致 `pandad` 配置不完整）。

  **明天继续的具体步骤**：
  1. 运行期间实测 `Params().get_bool("IsOnroad")` 的实际值和变化时序，对照
     `deviceState.started` 与 `manager.py:213-214` 的 `write_onroad_params` 调用时机
  2. 如果确认是 `IsOnroad` 时序或取值问题，需要搞清楚为什么这次（真实 CAN 版）
     与之前纯视觉版（`NOBOARD=1`）表现不同——纯视觉版走看门狗注入绕开了
     `card`/`pandad` 的正常初始化路径，从未真正测过 `pandad` 这条 onroad 判断逻辑
  3. 排查时**不要同时用多个脚本反复直连 panda 库**（会与 `pandad` 产生 USB 层面
     竞争，实测出现过 `usb1.USBErrorBusy`，可能干扰观测结果，需要先停掉所有直连
     诊断脚本，只留 `pandad` 独占访问后再观察）
  4. 这一步排查未触及任何安全边界——全程 `check_panda_readonly.py` 反复确认
     `controls_allowed=0`，收尾时确认 `safety_mode` 回落到 `silent`，只读闸门
     未受影响
  5. `FirmwareQueryDone`/`ControlsReady` 沿本清单 R2 的复核结论，`card` 一旦真的
     跑完 `get_car()` 应该能顺利往下走（`OpenpilotEnabledToggle=False` 闸门在
     真实识别路径下已验证生效，见 R1），当前卡点在更早的"等第一条非空 CAN"这一步，
     R1/R2 的结论本身不受这次卡点影响

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
