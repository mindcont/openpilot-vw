# Jetson Orin NX 车道线预测部署指南

> 目标：将车道线预测从 PC demo 移植到 NVIDIA Jetson Orin NX + 双摄像头，
> 走正规 openpilot manager 流程运行，纯视觉、不控车。

## 一、当前完成状态（务必先读）

| 项 | 状态 | 说明 |
|----|------|------|
| 框架代码改动 | ✅ 已完成并提交 | FORCE_ONROAD / 双摄像头 / intrinsics 覆盖 |
| 生产启动脚本 | ✅ 已完成 | `start_openpilot_orinnx.sh` |
| PC demo 路径 | ✅ 已验证 | `run_laneline_demo.py`（绕过 manager，能看到车道线）|
| **manager 正规流程** | ⚠️ **未实测** | 代码已改，但走 manager 的完整链路尚未在实机跑通 |
| **Orin NX 实机** | ⚠️ **未验证** | 设备号 / 双摄像头 / intrinsics 标定需在目标硬件完成 |

**结论**：框架代码已就绪，但「在 Orin NX 上直接运行」还需在实机完成设备配置、
摄像头标定，并首次跑通 manager 流程后才能确认。下面是完成这些步骤的方法。

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

## 五、验证与排查

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
| onroad 启动被阻塞 | 设了 IsDriverViewEnabled | 清除该参数，勿设 |
| laneLineProbs≈0 | intrinsics/分辨率错 | 重新标定，三处分辨率对齐 |
| 车道线上下颠倒 | 安装方向 | 调 `CAM_FLIP` |
| 双摄像头帧不同步 | 两路时间戳漂移 | 见下方限制 |
| UI 黑屏 | 无显示/GL | 确认接了屏，JetPack GL 正常 |

## 六、已知限制 / 未验证点（需实机确认）

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
