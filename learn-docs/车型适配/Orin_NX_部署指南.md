# Jetson Orin NX 车道线预测部署指南

> 目标：将车道线预测从 PC demo 移植到 NVIDIA Jetson Orin NX + 双摄像头，
> 走正规 openpilot manager 流程运行，纯视觉、不控车。

## 一、当前完成状态（务必先读）

| 项 | 状态 | 说明 |
|----|------|------|
| 框架代码改动 | ✅ 已完成并提交 | FORCE_ONROAD / 双摄像头 / intrinsics 覆盖 |
| 生产启动脚本 | ✅ 已完成 | `start_openpilot_orinnx.sh`（含跳过 onboarding）|
| PC demo 路径 | ✅ 已验证 | `run_laneline_demo.py`（绕过 manager，能看到车道线）|
| 静态代码走查 | ✅ 已完成 | 见第七节，已排出 7 个风险点并修复其一 |
| onboarding 阻塞 | ✅ 已修复 | 启动脚本自动写入 terms/training 参数（原会卡死首次 onroad）|
| **manager 正规流程** | ⚠️ **未实测** | 代码已改，但走 manager 的完整链路尚未在实机跑通 |
| **Orin NX 实机** | ⚠️ **未验证** | 设备号 / 双摄像头 / intrinsics 标定需在目标硬件完成 |

**结论**：框架代码已就绪，静态走查已把「首次进 onroad 被 onboarding 卡死」这个必现
阻塞修掉（见第七节发现 1）。剩余需在实机确认的是设备配置、摄像头标定、`card` 是否
正常写 CarParams，以及双摄同步表现。下面是完成这些步骤的方法。

## 二、架构：demo vs 生产

```
demo（run_laneline_demo.py，绕过 manager）：
  demo.mp4 → webcamerad → VisionIPC → modeld → modelV2 → 主进程内 AugmentedRoadView
  （手动发 deviceState.started / ignition / liveCalibration）

生产（start_openpilot_orinnx.sh，正规 manager）：
  双摄像头 → webcamerad → VisionIPC → modeld → modelV2 → ui 进程
  （FORCE_ONROAD 使 hardwared 发出 started；manager 自动拉起所有进程）
```

关键点：demo 里 UI 收不到 modelV2 的问题（子进程时序）在正规 manager 流程下
**不存在**，因为 modeld 是真实进程、真实产出 modelV2，ui 作为 manager 子进程正常订阅。

## 三、框架改动清单（已提交 d5d8e4518）

| 文件 | 改动 | 环境变量 |
|------|------|---------|
| `system/hardware/hardwared.py` | 无 panda 平台强制点火进 onroad | `FORCE_ONROAD` |
| `tools/webcam/camera.py` | 每摄像头独立分辨率；翻转可控 | `CAM_FLIP` |
| `tools/webcam/camerad.py` | 双摄像头分辨率配置 | `ROAD_CAM_SIZE` / `WIDE_CAM_SIZE` |
| `common/transformations/camera.py` | intrinsics 环境变量覆盖 | `ROAD_CAM_INTRINSICS` / `WIDE_CAM_INTRINSICS` |

## 四、实机部署步骤（在 Orin NX 上执行）

### 步骤 1：确认摄像头设备号

```bash
v4l2-ctl --list-devices
# 或
ls -l /dev/video*
```

分辨哪个是 road（窄视野/长焦）、哪个是 wide（宽视野），把设备号填入
`start_openpilot_orinnx.sh` 的 `ROAD_CAM` / `WIDE_CAM`。

用 mpv/ffplay 逐个确认视角：
```bash
ffplay /dev/video0
ffplay /dev/video1
```

### 步骤 2：标定摄像头 intrinsics（★ 最关键 ★）

demo 阶段已验证：**intrinsics 焦距错误会导致车道线投影错位、置信度骤降到接近 0**。
两个摄像头都必须标定。

用棋盘格 + OpenCV 标定得到内参矩阵 K，取其中的 fx（≈fy）：

```python
import cv2, numpy as np, glob
# 采集 15~20 张不同角度的棋盘格照片（用目标摄像头的实际分辨率）
CHECKERBOARD = (9, 6)   # 内角点数，按你的标定板调整
objp = np.zeros((CHECKERBOARD[0]*CHECKERBOARD[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
objpoints, imgpoints = [], []
for f in glob.glob("calib_imgs/*.jpg"):
    img = cv2.imread(f); gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ok, corners = cv2.findChessboardCorners(gray, CHECKERBOARD)
    if ok:
        objpoints.append(objp); imgpoints.append(corners)
ret, K, dist, _, _ = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)
print("K =\n", K)
print(f"填入: 宽,高,{K[0,0]:.0f}")   # fx = K[0,0]
```

把结果填入 `start_openpilot_orinnx.sh`：
```bash
export ROAD_CAM_INTRINSICS="1928,1208,<road_fx>"
export WIDE_CAM_INTRINSICS="1928,1208,<wide_fx>"
export ROAD_CAM_SIZE=1928x1208   # 与上面分辨率一致
export WIDE_CAM_SIZE=1928x1208
```

> 分辨率必须三处一致：摄像头采集 = *_CAM_SIZE = *_INTRINSICS 的宽高。

### 步骤 3：确认安装方向

摄像头正装设 `CAM_FLIP=0`，倒装（旋转 180°）设 `CAM_FLIP=1`。

### 步骤 4：启动

```bash
cd /home/wio/openpilot
./start_openpilot_orinnx.sh
```

manager 会自动拉起 webcamerad → modeld → ui。首次启动 tinygrad 需编译 kernel，
Orin NX 上通常数十秒。

> **首跑建议用单摄模式**（规避双摄同步/带宽问题，见第七节发现 3）：
> ```bash
> SINGLE_CAM=1 ./start_openpilot_orinnx.sh
> ```
> 单摄模式只用 road 相机，禁用 wide；确认能出 modelV2/车道线后，再改回双摄
> （去掉 `SINGLE_CAM=1` 或设 `SINGLE_CAM=0`）。

## 五、七寸屏显示配置与 CAN 调试

### 七寸屏(1024×600)显示

openpilot UI 原生逻辑分辨率是 **2160×1080**(comma 大屏)。7 寸屏用 `MID_UI`：
复用大屏布局(MainLayout，功能全、含车道线叠加)，**等比缩放**到目标物理尺寸，不变形。

```bash
export MID_UI=1                 # 启用中屏模式
export MID_UI_SIZE=1024x600     # 目标物理分辨率(默认即 1024x600)
```

原理：`scale = min(1024/2160, 600/1080) = 0.474`，窗口 1024×512(x/y 同一 scale
故不变形)，7 寸屏底部约 88px 空白/黑边。`start_openpilot_orinnx.sh` 已默认 `MID_UI=1`。

三种显示模式对比：

| 模式 | 环境变量 | 逻辑分辨率 | 适用 |
|------|---------|-----------|------|
| 大屏 | `BIG=1` | 2160×1080 | comma 3X / 桌面全屏 |
| **中屏** | `MID_UI=1` | 2160×1080→等比缩放 | **7 寸屏 1024×600** |
| 小屏 | (默认) | 536×240 | mici 设备 |

> 实现见 `system/ui/lib/application.py`：`MID_UI` 使 `big_ui()=True`（用 MainLayout
> 与大屏字体），并在 `__init__` 按 `MID_UI_SIZE` 等比设定 scale。

### CAN 调试叠加

`CAN_DEBUG=1` 时，onroad 画面左上角叠加半透明面板，实时显示 CAN 关键变量，
方便实车调试：

```bash
export CAN_DEBUG=1
```

显示内容（来自 `CarState`，由 `vw_mqb.dbc` 解析）：
- 车速 vEgo / 仪表车速、方向盘角度、方向盘力矩、档位
- 油门/刹车、踏板状态、静止标志、转向灯、巡航状态、latActive
- 关键消息 alive/valid：carState / modelV2 / liveCalibration / pandaStates / carControl

实现：`selfdrive/ui/onroad/can_debug_overlay.py`（`CanDebugOverlay`），
在 `AugmentedRoadView` 的自定义叠加扩展点渲染。PC 验证也可用：
`CAN_DEBUG=1 python3 run_laneline_demo.py`。

## 六、验证与排查

### 确认 modeld 产出车道线
```bash
python3 -c "
import cereal.messaging as messaging, time
sm = messaging.SubMaster(['modelV2'])
for _ in range(40):
    sm.update(1000)
    if sm.updated['modelV2']:
        m = sm['modelV2']
        print('laneLineProbs:', [round(p,2) for p in m.laneLineProbs])
        break
"
```
正常应看到内侧两条车道线 prob > 0.5（demo 实测达 0.9+）。若全部接近 0 → intrinsics 不对。

### 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| modeld 未启动 | 未进 onroad | 确认 `FORCE_ONROAD=1` |
| 日志刷 `Startup blocked` | 未接受 terms/training（onboarding）| 启动脚本已自动写入；手动跑见发现 1 |
| onroad 启动被阻塞 | 设了 IsDriverViewEnabled | 清除该参数，勿设 |
| modeld 卡住不出 modelV2 | 等 CarParams（card 没起/没写）| 见发现 4，确认 `card` 正常启动 |
| laneLineProbs≈0 | intrinsics/分辨率错 | 重新标定，三处分辨率对齐 |
| 车道线上下颠倒 | 安装方向 | 调 `CAM_FLIP` |
| 双摄像头帧不同步 | 两路时间戳漂移 | 见发现 3，先用单 road 相机 |
| UI 黑屏 | 无显示/GL | 确认接了屏，JetPack GL 正常 |

## 七、已知限制 / 未验证点（需实机确认）

1. **manager 正规流程首次跑通未验证**：FORCE_ONROAD 代码已加，但没在实机用
   manager 完整跑过。首次启动需重点确认 modeld 是否被 `only_onroad` 条件正常拉起。
2. **双摄像头时间同步**：当前 webcamerad 用 `frame_id * 0.05` 作时间戳，两路各自
   Ratekeeper(20) 维持对齐，modeld 用 25ms 窗口匹配。若实机两摄像头帧率漂移导致
   不同步，需改为用实际采集时间戳。
3. **wide/road 切换**：UI 会按车速在 road/wide 间切换（实验模式）。纯视觉展示下
   可固定用 road 流。
4. **intrinsics 是内参，不含畸变校正**：鱼眼 wide 摄像头畸变较大时，可能需要额外
   去畸变处理（当前未做）。
5. **标定 rpy 外参**：当前用固定 rpy=[0,0,0]（假设摄像头水平正装）。若安装有俯仰/
   偏航角，车道线会整体偏移，需要真实标定外参或手工微调。

## 七、静态代码走查（demo → 生产链路，实机前预排风险）

对 `launch_openpilot.sh → manager → hardwared → modeld → ui` 整条链路做了一次静态
走查，重点排 demo 绕过 manager 时没触发、但正规流程会遇到的坑。以下发现均标注了
代码位置，可按图索骥。

### 启动链路（已确认）

```
launch_openpilot.sh → manager
  → hardwared 发布 deviceState.started
  → manager 用 started 驱动 only_onroad(modeld) 与 driverview(webcamerad)
  → modeld 读 相机帧 + CarParams + 标定 → 发 modelV2
  → ui 订阅 modelV2 → AugmentedRoadView / model_renderer 画车道线
```

### 发现 1 —— 高危 · 首次进 onroad 被 onboarding 参数卡死【已修复】

- 位置：`system/hardware/hardwared.py:314,318`；默认值 `common/params_keys.h:27,56`
- 现象：`started_ts is None`（首次启动）时 `should_start` 要求 **全部** `startup_conditions`
  为真，其中 `accepted_terms`（`HasAcceptedTerms == terms_version`）与
  `completed_training`（`CompletedTrainingVersion == training_version`）在全新设备上默认
  是 `"0"`，不满足 → `deviceState.started` 恒为 False → `modeld`(only_onroad) 不被拉起
  → 看不到车道线，日志刷 `"Startup blocked"`。
- 关键点：`FORCE_ONROAD` 只覆盖 `onroad_conditions["ignition"]`，**解决不了**
  `startup_conditions`。demo 绕过 manager 从没触发这条。
- 修复：`start_openpilot_orinnx.sh` 启动前用 python 写入这两个参数（做法同官方测试
  脚手架 `selfdrive/test/helpers.py:21-22`）。已随本次提交生效。

### 发现 2 —— 好消息 · PC 模式适配在 Orin NX 上确实生效

- 位置：`system/hardware/__init__.py:11` → `PC = not TICI`。Jetson 无 `/TICI` 文件 →
  **`PC=True`**。
- 因此靠常量 `PC` 判断的适配全部生效：
  - `selfdrive/modeld/modeld.py`：默认标定分支运行，用 `DEVICE_CAMERAS[('pc','unknown')]`，
    该 entry 即 `transformations/camera.py:79-80,113` 的 `_pc_config_from_env()` →
    **你的 `ROAD_CAM_INTRINSICS`/`WIDE_CAM_INTRINSICS` 确实注入了 modeld 的标定矩阵**。
  - `ui_state.py:139`、`augmented_road_view.py:148,155`、`model_renderer.py:92` 均 import
    硬件常量 `PC`（非环境变量），在 Jetson 上一致生效。
- 注意不一致：`system/manager/process_config.py` 的 `driverview()` 用的是
  `os.getenv("PC")`（环境变量，脚本未设），所以「PC+WEBCAM 摄像头常开」分支不会走，
  `webcamerad` 改为随 `started` 一起起。不致命，知悉即可。

### 发现 3 —— 中危 · 双摄同步脆弱

- 位置：`tools/webcam/camerad.py`（`_send_yuv`：`eof = frame_id * 0.05 * 1e9`）；
  `selfdrive/modeld/modeld.py` 主循环配对逻辑。
- 时间戳是**帧号推算**而非真实采集时间；两摄像头各自线程、各自 `frame_id` 与
  `Ratekeeper(20)`。modeld out-of-sync 报错阈值 10ms，而一帧 50ms → 差 1 帧即刷错误；
  且 `vipc_client_extra` 非阻塞，wide 跟不上时 `recv()` 返 None → modeld 跳过整轮 →
  modelV2 停更 → 车道线卡住。
- 风险：两路 1928×1208@20fps NV12 走 USB 带宽压力大，实机大概率喂不满。
- 建议：纯车道线展示优先**单 road 相机**（wide 流缺席时 modeld 自动走
  `use_extra_client=False` 单摄路径，更稳）；或降分辨率；坚持双摄则改用真实采集时间戳。

### 发现 4 —— 中危 · modeld 阻塞等 CarParams

- 位置：`selfdrive/modeld/modeld.py` → `params.get("CarParams", block=True)`。
- 生产模式（非 `--demo`）会**阻塞**直到 `card`(only_onroad) 写入 CarParams。链路：
  onroad → card → 写 CarParams → modeld 解阻塞。若 `card` 在
  `VOLKSWAGEN_GOLF_MK7 + SKIP_FW_QUERY + NOBOARD` 组合下起不来或不写 CarParams，
  modeld 会永久挂住。实机需确认 `card` 正常启动并写了 CarParams。

### 发现 5 —— 低危 · CAM_FLIP 默认值反直觉

- 位置：`tools/webcam/camera.py:58` → `os.getenv("CAM_FLIP", "1")` 默认翻转。
- 脚本已显式设 `CAM_FLIP=0`；脱离脚本裸跑会默认倒转 180°。

### 发现 6 —— 低危 · modeld PC 标定分支假设 road=main

- 位置：`selfdrive/modeld/modeld.py` 的 `if PC:` 分支硬编码 `fcam→main / ecam→extra`，
  未看 `main_wide_camera`。双摄都在时 main=road，正确；仅 wide 单摄时会用错内参。
  当前双摄场景无影响。

### 发现 7 —— 低危 · NOBOARD 下 pandad 仍运行

- 位置：`system/manager/process_config.py`（pandad 为 `always_run`）；
  `hardwared.py` 中 `FORCE_ONROAD` 在超时把 ignition 置 False 后仍每轮覆盖为 True。
- 结论：pandad 无 panda 时可能报错但不会阻塞 onroad（FORCE_ONROAD 每轮胜出）。

### 优先级建议

1. 发现 1 已修复（启动脚本自动跳过 onboarding）——这是首次实机第一个必现卡点。
2. 首跑先用**单 road 相机**验证链路通：`SINGLE_CAM=1 ./start_openpilot_orinnx.sh`，
   跑通后再上双摄（规避发现 3/4）。
3. 实机确认 `card` 正常写 CarParams（发现 4）。
