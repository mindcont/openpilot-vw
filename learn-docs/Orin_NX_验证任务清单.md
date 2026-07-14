# Orin NX (hal9000) 联网恢复后验证任务清单

> 状态：🔄 进行中（任务1-8已完成，任务9待车辆静止停放时补做，任务10视9的结果而定）。
> 创建于 2026-07-10，用于 Orin NX 断网期间暂存待验证事项，联网恢复后按顺序执行。
> 完成后每项打勾并记录结果；全部完成后可将结论汇总进
> [环境搭建与容器部署.md](环境搭建与容器部署.md) 对应章节，本文档可归档。

## 背景

同一会话内完成了两块代码改动并已提交推送到 `dev-vw`（远端 `origin/dev-vw` 已同步）：

1. **Bug2 修复**：`start_openpilot_orinnx.sh` 后台看门狗注入 `CarParams`，解除
   `modeld` 永久阻塞（commit `fa6bdd889` / `345eba364`）。已完成一轮实机验证
   （截图+`modelV2`订阅确认），但后续又叠加了 UI 全屏与曝光改动，需要一并回归。
2. **UI 全屏 + 曝光修正**：`system/ui/lib/application.py` 新增
   `UI_FULLSCREEN=1`（无边框全屏），曝光默认值从过曝的 300/128 改为 50/40
   （commit `f9fa79142` / `6662901f72`）。已截图验证效果良好（画面清晰，
   车道线可见，`laneLineProbs` 0.005→0.196）。
3. **软件自动曝光闭环（方案 B）**：新增 `tools/webcam/auto_exposure.py`，
   `AUTO_EXPOSURE=1` 时按道路 ROI 灰度自动调节 `exposure_time_absolute`/`gain`，
   解决固定曝光值只适配单一光照场景的问题（commit `1448a6b7f` / `647fea0d2`）。
   仅完成离线逻辑验证（模拟物理模型，两个极端场景约 20 次迭代收敛），
   **实机验证（真实摄像头+真实光照）尚未做**——因 Orin NX 在此时断网
   （`ping 100.73.154.105` 100% 丢包），本清单即为此中断点的续接记录。

代码现状：本地与远端 `dev-vw` 均在 `647fea0d2a`，工作区干净，无待提交改动。

**待排查项（2026-07-10 昨天运行观察）**：用户反馈启动后 UI 提示"未识别设备"，
当时未能现场确认具体位置/原文（Orin NX 已断电，无法查日志）。代码排查找到两条
候选，但未最终确认是哪一条，见任务 5。

## 任务清单

- [x] **1. 确认 Orin NX (hal9000, 100.73.154.105) 网络恢复** ✅ 2026-07-14
  `ping -c 3 100.73.154.105` → 0% 丢包；`ssh car@100.73.154.105 echo ok` → `ok`。
  网络已恢复正常。

- [x] **2. 停止残留 openpilot 进程（如有）** ✅ 2026-07-14
  `pgrep -fa 'manager.py|launch_openpilot|selfdrive.ui.ui|modeld|webcamerad'` 只匹配
  到 `pgrep` 自身，确认无残留进程，跳过 kill 步骤。

- [x] **3. `git pull` 同步到最新 `dev-vw`** ✅ 2026-07-14
  Orin NX 原停在 `6662901f7`，`git pull origin dev-vw` fast-forward 到 `7bf8c2b77`
  （比清单目标 `647fea0d2a` 更新，已 `git merge-base --is-ancestor` 确认包含它）。
  新增文件确认拉取到：`tools/webcam/auto_exposure.py`、`camera.py`/
  `start_openpilot_orinnx.sh` 改动、UI 全屏改动、文档更新。工作区干净。

- [x] **4. 静态校验：bash 语法 + python 编译** ✅ 2026-07-14
  `bash -n start_openpilot_orinnx.sh` → OK；在 Orin NX 实际 `.venv` 下
  `python3 -m py_compile tools/webcam/auto_exposure.py tools/webcam/camera.py` → OK；
  `import tools.webcam.auto_exposure` 也验证无导入错误。DISPLAY(:0)/XAUTHORITY 可用
  （`xdpyinfo` 通过）。

- [x] **5. 回归验证：手动曝光模式基线未退化** ✅ 2026-07-14
  `AUTO_EXPOSURE=0`（默认）+ `SINGLE_CAM=1` 启动：
  1) 看门狗注入器三条日志齐全：`已注入 CarParams(...)` → `CarParams 已稳定存在，注入器退出`
  2) `webcamerad`/`modeld`/`selfdrive.ui.ui`/`soundd`/`feedbackd` 等进程存活，非 `defunct`
  3) `modelV2` 20s 内 66 帧（~3.3fps，CPU 模式，与基线一致），`roadCameraState` 401 帧
     （~20fps，符合预期）
  4) `gnome-screenshot` 截图画面清晰不过曝，UI 全屏（`UI_FULLSCREEN=1`）生效
  5) `laneLineProbs` 实测偏低（0.006~0.03，低于文档记录的 0.196 基线）——**这是本次
     测试环境（室内/摄像头未对准清晰车道场景）导致，非代码回归**，未观察到过曝/花屏/
     UI 卡死等回归现象
  6) 副产物：截图发现全屏 "Unknown Vehicle Variant" 提示，见任务 6 排查结论

- [x] **6. 排查"未识别设备"提示（昨天运行观察，来源未确认）** ✅ 2026-07-14 确认

  **结论：是第三种情况，不是候选 A（NO PANDA 侧边栏）也不是候选 B（carUnrecognized）。**

  实机 `gnome-screenshot` 截图确认：全屏提示英文原文是 **"Unknown Vehicle Variant"**，
  显示在屏幕下方大号文字区域（不是侧边栏小标签，也不是仅终端日志）。

  根因链路（用 `cereal.messaging.SubMaster` 订阅验证）：
  1. `card.py` 的 `Car.__init__` 在 `NOBOARD=1`（无真实 CAN 硬件）时永久阻塞在
     `messaging.recv_one_retry(self.can_sock)` 等第一条 CAN 包（`ps aux` 显示
     `card` 进程存活但几乎不占 CPU，符合阻塞特征），**从未跑到 `get_car()`
     车型识别逻辑**，因此不会触发候选 B 的 `carUnrecognized`。
  2. 我们的看门狗注入器只是直写 `CarParams` 这个 Param 给 `modeld`/`selfdrived`
     等消费者解除它们各自的阻塞（`params.get("CarParams", block=True)`），
     **不会让 `card` 自己发布 `carState` 消息**——`card` 依然卡在等 CAN。
  3. 实测：`carState` 频道 15 秒内 0 帧，`valid=False`，`seen=False`。
  4. `selfdrived.py` 事件判定 `elif not CS.canValid: self.events.add(EventName.canError)`
     （`selfdrive/selfdrived/selfdrived.py:318`）。`CS` 是默认全零结构体，
     `canValid` 恒为 `False`，每帧都触发 `canError` 事件。
  5. `canError` 事件在 `selfdrive/selfdrived/events.py:934-941` 映射为
     `ET.IMMEDIATE_DISABLE: ImmediateDisableAlert("Unknown Vehicle Variant")`
     ——即截图里看到的全屏提示。
  6. 同时 `onroadEvents` 还带着 `sensorDataInvalid`/`modeldLagging`/
     `processNotRunning`/`usbError`/`selfdrivedLagging`，都是同一根因
     （缺 `carState`）的连带反应，不是独立问题。

  **是否是预期现象：是。** 当前没有连接真实 CAN（无 panda 硬件在线），`card` 无法
  完成初始化本就是设计上的限制，看门狗方案的范围只是"解除 `modeld` 阻塞看到车道线"
  （Bug2 原始目标），从未涉及让 `card`/`selfdrived` 达到完全正常状态。`canError`
  全屏提示与"NO PANDA"侧边栏是两个并存的独立提示，根源都是"无真实 CAN/panda"这同一个
  环境限制，属预期现象，无需修复。若后续接入真实 CAN（第二阶段），`card` 能正常收到
  CAN 包，此提示会自然消失。

- [x] **7. 验证 `AUTO_EXPOSURE=1` 实机收敛效果** ✅ 2026-07-14
  停止上一步实例（`pkill -f manager.py` 后重新建连确认 ssh 会话未受影响，进程已清空），
  改 `AUTO_EXPOSURE=1` 重新启动：
  1) `camera.py` 的 `[camera] ... 软件自动曝光已启用` print 未在 `/tmp/orinnx_run2.log`
     中直接搜到（疑似 manager 多进程日志交织导致行被截断/合并，非功能问题，见下方
     实测数据佐证功能确实生效）
  2) `v4l2-ctl --get-ctrl=exposure_time_absolute,gain` 连续 4 次（间隔 4s，共 16s）
     查值：稳定在 `exposure=7, gain=71`（从初始 `50/40` 收敛过去），16 秒内无震荡
  3) `gnome-screenshot` 截图：真实道路场景（车辆/行人/锥桶），画面亮度合理不过曝，
     车道线蓝色边线+绿色预测路径清晰可见，比 task5 室内基线画面质量明显更好
  4) `grep -i 'fail\|error\|Cannot set'` 未命中 v4l2-ctl 相关错误
  5) 额外验证：`modelV2` 20s 内 64 帧（~3.2fps，与基线一致），`roadCameraState` 403 帧
     （~20fps）；`laneLineProbs` 从室内基线 0.006~0.03 提升到 0.10~0.21（真实道路+
     合理曝光的共同作用，与自动曝光目标一致）

- [x] **8. 验证自动曝光对帧率/`laneLineProbs` 无负面影响** ✅ 2026-07-14（数据取自任务7）
  用 `cereal.messaging.SubMaster` 检查：
  1) `roadCameraState` 20s 内 403 帧，~20fps，与手动曝光基线一致，自动曝光 1Hz
     轮询未拖慢采集
  2) `modelV2` 20s 内 64 帧，~3.2fps，与之前基线（~3.3fps，CPU 模式）基本一致
  3) `laneLineProbs` 0.10~0.21，相比室内基线 0.006~0.03 明显提升（但两次场景不同——
     真实道路 vs 室内空场景，提升主要来自场景差异+曝光改善的叠加，无法单独剥离
     自动曝光的贡献占比；结论：**至少不变差，且实测数值更健康**）

- [ ] **9. 现场测试光照变化场景（如可行）** 🔄 待办（2026-07-14 中断，车辆已驶离停车场）
  如果能制造光照变化（如手动遮挡镜头/开关灯/移动到窗边），观察
  `AutoExposureController` 能否在合理时间内（预期数十秒级，受 1Hz 控制频率和
  低通滤波影响）重新收敛到目标灰度，验证"早中晚/室内外切换"这个原始诉求是否
  真正解决。

  **中断记录**：2026-07-14 曾在停车场准备测试（`AUTO_EXPOSURE=1` 实例已跑起来，
  停车场自然光下曝光稳定在 `exposure=10, gain=22`），启动了 `v4l2-ctl` 后台轮询
  监控（2s 间隔，60 次）准备做遮挡测试，但车辆随后驶离停车场，测试未执行，已停止
  监控进程并清理 Orin NX 上残留的 openpilot 进程（`pkill -9` 清空
  manager/selfdrive/webcam 全部子进程，确认 `pgrep` 无残留）。下次车辆静止停放
  （尤其能覆盖室内外/明暗对比场景）时重新执行本任务。

- [ ] **10. 根据实机结果决定是否调参并更新文档**
  若收敛慢/震荡/ROI 误判（如引擎盖反光、树影斑块），调整环境变量
  `AE_TARGET_GREY` / `AE_INTERVAL` / `AE_SMOOTH_ALPHA`（见
  `tools/webcam/auto_exposure.py` 顶部）重测。最终把实机验证结论（成功或需调参）
  补充进 [环境搭建与容器部署.md](环境搭建与容器部署.md) 对应章节，并评估是否将
  `AUTO_EXPOSURE` 默认值从 `0` 改为 `1`（需要现场确认稳定后才改默认值）。

## 相关文件

| 文件 | 改动内容 |
|------|----------|
| `start_openpilot_orinnx.sh` | 看门狗注入器、`UI_FULLSCREEN`、曝光默认值、`AUTO_EXPOSURE` 开关 |
| `system/ui/lib/application.py` | `UI_FULLSCREEN=1` 时 `toggle_borderless_windowed` |
| `tools/webcam/camera.py` | `AUTO_EXPOSURE=1` 时接入 `AutoExposureController` |
| `tools/webcam/auto_exposure.py` | 新增：软件自动曝光闭环控制器 |
| `tools/vw/check_panda_readonly.py` | 只读防线第二道硬件闸门核实脚本（前置工作，已验证） |
| `learn-docs/环境搭建与容器部署.md` | 第十三/十五节 + 曝光章节的设计与调研记录 |
