# Orin NX (hal9000) 联网恢复后验证任务清单

> 状态：🔄 进行中。创建于 2026-07-10，用于 Orin NX 断网期间暂存待验证事项，
> 联网恢复后按顺序执行。完成后每项打勾并记录结果；全部完成后可将结论汇总进
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

## 任务清单

- [ ] **1. 确认 Orin NX (hal9000, 100.73.154.105) 网络恢复**
  `ping -c 3 100.73.154.105`；恢复后 `ssh car@100.73.154.105 echo ok` 测试连接。
  之前 100% 丢包，需先确认设备开机/联网正常，再继续后续步骤。

- [ ] **2. 停止残留 openpilot 进程（如有）**
  `pkill -f manager.py` / `launch_openpilot` / `selfdrive.ui.ui` / `modeld` /
  `webcamerad`，`sleep 3` 后 `pgrep` 确认已清空。
  注意：`pkill` 曾导致当前 ssh 会话被误杀断连（历史现象），建议在独立命令里执行
  并重新建连确认结果，不要和其他命令合并在同一 ssh 会话里等结果。

- [ ] **3. `git pull` 同步到最新 `dev-vw` (`647fea0d2a`)**
  `cd ~/openpilot && git pull origin dev-vw`，确认 fast-forward 到 `647fea0d2a`
  （含 `auto_exposure.py` 新增、`camera.py`/`start_openpilot_orinnx.sh` 改动、
  UI 全屏改动、文档更新）。

- [ ] **4. 静态校验：bash 语法 + python 编译**
  `bash -n start_openpilot_orinnx.sh`；
  `python3 -m py_compile tools/webcam/auto_exposure.py tools/webcam/camera.py`；
  确认在 Orin NX 实际 venv 环境下也无导入错误（之前只在本地 wio 机器验证过语法，
  未在 Orin NX 上重新 py_compile 这两个新文件）。

- [ ] **5. 回归验证：手动曝光模式基线未退化**
  `AUTO_EXPOSURE=0`（默认）+ `SINGLE_CAM=1` + `DISPLAY=:0
  XAUTHORITY=/run/user/1000/gdm/Xauthority` 启动，确认：
  1) 看门狗注入器正常完成（`[orinnx][inject]` 日志三条：启动/已注入/稳定退出）
  2) UI 进程存活、非 `defunct`
  3) 全屏（`UI_FULLSCREEN=1`）+ 曝光（`exposure=50, gain=40`）效果与之前截图一致，
     没有因 `camera.py` 改动引入回归。用 `gnome-screenshot` 截图确认画面清晰不过曝。

- [ ] **6. 验证 `AUTO_EXPOSURE=1` 实机收敛效果**
  停止上一步实例，改 `AUTO_EXPOSURE=1` 重新启动。观察：
  1) `camera.py` 打印的 `[camera] ... 软件自动曝光已启用` 日志
  2) `v4l2-ctl --get-ctrl=exposure_time_absolute,gain` 每隔几秒查值，确认在变化
     且趋于稳定（不是持续震荡）
  3) `gnome-screenshot` 多次截图对比曝光是否合理（不过曝不过暗）
  4) 检查是否有 `v4l2-ctl` 调用失败的错误日志

- [ ] **7. 验证自动曝光对帧率/`laneLineProbs` 无负面影响**
  用之前验证过的 python 订阅脚本方式（`cereal.messaging.SubMaster`）检查：
  1) `roadCameraState` 帧率是否仍 ~20fps（自动曝光 1Hz 轮询不应拖慢采集）
  2) `modelV2` 产出帧率是否与之前基线（~3.3fps，CPU 模式）一致
  3) `laneLineProbs` 是否因曝光更合理而提升或至少不变差

- [ ] **8. 现场测试光照变化场景（如可行）**
  如果能制造光照变化（如手动遮挡镜头/开关灯/移动到窗边），观察
  `AutoExposureController` 能否在合理时间内（预期数十秒级，受 1Hz 控制频率和
  低通滤波影响）重新收敛到目标灰度，验证"早中晚/室内外切换"这个原始诉求是否
  真正解决。

- [ ] **9. 根据实机结果决定是否调参并更新文档**
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
