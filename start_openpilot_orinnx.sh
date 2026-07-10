#!/usr/bin/env bash
# ============================================================
# openpilot-vw Jetson Orin NX 生产启动脚本
#
# 用途：无 panda 硬件的纯视觉车道线预测（不控车）
# 平台：NVIDIA Jetson Orin NX + 双 USB/CSI 摄像头
#       road（前视窄视野/长焦） + wide（前视宽视野）
#
# 与 run_laneline_demo.py 的区别：
#   - 走正规 manager 流程（manager 自动拉起 webcamerad/modeld/ui），
#     而非绕过 manager 手动发消息
#   - 用真实双摄像头，而非 demo.mp4
#   - 用 FORCE_ONROAD 进入 onroad 状态（无需 panda 点火信号）
#
# 首次部署前必做（见 learn-docs/车型适配/Orin_NX_部署指南.md）：
#   1. 用 v4l2-ctl --list-devices 确认两个摄像头的 /dev/videoN 编号
#   2. 标定两个摄像头的 intrinsics（焦距 fx），填入下方 *_INTRINSICS
# ============================================================

set -e

OPENPILOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
VENV_PATH="$OPENPILOT_DIR/.venv"

cd "$OPENPILOT_DIR"

# --- 虚拟环境 ---
if [ -d "$VENV_PATH" ]; then
  source "$VENV_PATH/bin/activate"
fi

# ============================================================
# 单摄验证模式开关
# ------------------------------------------------------------
# SINGLE_CAM=1 时只用 road 单摄，禁用 wide 摄像头。
# 首次实机建议先跑单摄跑通链路（规避双摄同步/带宽问题，见部署指南发现 3/4），
# 确认能出 modelV2/车道线后，再改回双摄（SINGLE_CAM=0）。
# 可从外部覆盖：  SINGLE_CAM=1 ./start_openpilot_orinnx.sh
# 原理：webcamerad 的 camerad.py 用 `if WIDE_CAM:` 判断是否加宽角摄像头，
#      置空 WIDE_CAM 即只保留 road；modeld 检测到无 wide 流会自动走单摄路径。
export SINGLE_CAM=${SINGLE_CAM:-0}

# ============================================================
# 摄像头配置（★ 需按实机调整 ★）
# ============================================================
# 设备号：用 `v4l2-ctl --list-devices` 查询后填写
# 实测（2026-07-10 hal9000）：两个 USB 摄像头分别挂在 video0/1 与 video2/3，
# 各自的采集节点是 video0（road）与 video2（wide）。
export ROAD_CAM=0          # 前视窄视野摄像头 -> /dev/video0
export WIDE_CAM=2          # 前视宽视野摄像头 -> /dev/video2

# 采集分辨率（宽x高），必须与下方 *_INTRINSICS 的分辨率一致
export ROAD_CAM_SIZE=1928x1208
export WIDE_CAM_SIZE=1928x1208

# 摄像头内参（宽,高,焦距px）★ 必须用实测标定值替换 ★
# 焦距错误会导致车道线投影错位、置信度骤降（demo 阶段已验证此现象）
# 标定方法见部署指南；下面是 comma AR/OX 默认值，仅占位
export ROAD_CAM_INTRINSICS="1928,1208,2648"
export WIDE_CAM_INTRINSICS="1928,1208,567"

# 摄像头安装方向：正装=0，倒装（180°）=1
export CAM_FLIP=0

# 单摄模式：置空 WIDE_CAM 以禁用宽角摄像头（camerad.py 的 `if WIDE_CAM:` 判空）
if [ "$SINGLE_CAM" = "1" ]; then
  export WIDE_CAM=""
fi

# ============================================================
# 曝光手动设置（★ 强光/室外场景必做 ★）
# ------------------------------------------------------------
# 两个摄像头默认 auto_exposure=3（光圈优先自动模式），在停车场顶棚等
# 强反光场景下会严重过曝（画面发白，车道线/车牌都看不清）。
# 实测（2026-07-10 hal9000，阴天顶棚停车场）：
#   road (video0)：exposure_time_absolute=8   （单位 1/10000 秒，即 0.8ms）
#   wide (video2)：exposure_time_absolute=40  （即 4ms）
# road 对着更亮的天空区域，需要比 wide 更低的曝光值。
# 这两个值是凭观感调的，不是精确标定；实际效果应结合 modeld 的
# laneLineProbs 置信度反馈微调，且白天/夜晚场景可能需要不同的值。
# 该设置不持久化（重启/摄像头断连后恢复默认），所以每次启动都重新应用。
export ROAD_CAM_EXPOSURE=${ROAD_CAM_EXPOSURE:-8}
export WIDE_CAM_EXPOSURE=${WIDE_CAM_EXPOSURE:-40}

function set_camera_exposure() {
  local dev="/dev/video$1"
  local exposure="$2"
  if [ -e "$dev" ] && command -v v4l2-ctl > /dev/null 2>&1; then
    v4l2-ctl -d "$dev" --set-ctrl=auto_exposure=1 2>/dev/null
    v4l2-ctl -d "$dev" --set-ctrl=exposure_time_absolute="$exposure" 2>/dev/null
    echo "  已设置 $dev 曝光: manual, exposure_time_absolute=$exposure"
  else
    echo "  [警告] $dev 不存在或 v4l2-ctl 未安装，跳过曝光设置"
  fi
}

set_camera_exposure "$ROAD_CAM" "$ROAD_CAM_EXPOSURE"
if [ -n "$WIDE_CAM" ]; then
  set_camera_exposure "$WIDE_CAM" "$WIDE_CAM_EXPOSURE"
fi

# ============================================================
# 运行模式
# ============================================================
export USE_WEBCAM=1        # 使用 webcamerad（USB/CSI 摄像头）
export FORCE_ONROAD=1      # 无 panda 平台强制进入 onroad
export PASSIVE=1           # 被动模式，仅观察不输出控制
export NOBOARD=1           # 无 panda 硬件
export SKIP_FW_QUERY=1     # 跳过车辆固件查询
export FINGERPRINT="VOLKSWAGEN_SAGITAR_MK7"  # 速腾正式车型指纹（MQB 平台，轴距2.731）
# 显示配置（7 寸屏 1024×600 用 MID_UI；comma 大屏/桌面全屏用 BIG）
export MID_UI=1                 # 7寸屏 1024×600：等比缩放大屏布局(MainLayout)，不变形
export MID_UI_SIZE=1024x600     # 目标物理分辨率，其他尺寸屏可改
# export BIG=1                  # 备选：2160×1080 大屏/桌面
# export CAN_DEBUG=1            # 可选：onroad 画面叠加显示 CAN 关键变量(调试用)

# ★ 注意：切勿设置 IsDriverViewEnabled=True ★
#   它会使 startup_conditions["not_driver_view"]=False 从而阻塞 onroad 启动。
#   本脚本靠 FORCE_ONROAD 进入 onroad，不需要 driver view。

export LOGPRINT=info
export OPENPILOT_DATA=/tmp/data

# ============================================================
# 跳过 onboarding（★ 首次跑通 manager 流程必做 ★）
# ------------------------------------------------------------
# hardwared 的 startup_conditions 在「首次进 onroad」时要求：
#   HasAcceptedTerms        == terms_version
#   CompletedTrainingVersion == training_version
# 全新设备这两个参数默认是 "0"，不满足 -> should_start=False ->
# deviceState.started 一直为 False -> modeld(only_onroad) 不会被拉起 ->
# 看不到车道线（日志里会刷 "Startup blocked"）。
# FORCE_ONROAD 只解决 ignition，解决不了 startup_conditions，所以这里补上。
# 做法与官方测试脚手架 selfdrive/test/helpers.py 一致。
python3 - <<'PY'
from openpilot.common.params import Params
from openpilot.system.version import terms_version, training_version
p = Params()
p.put("HasAcceptedTerms", terms_version)
p.put("CompletedTrainingVersion", training_version)
print(f"[orinnx] onboarding 已跳过: terms={terms_version} training={training_version}")

# 只读防线（第一道软件闸门）：强制关闭 openpilot 控车总开关。
# 见 learn-docs/环境搭建与容器部署.md 第十五节。
# card.py 会用该 Param 重算 passive：OpenpilotEnabledToggle=False ->
# controller_available=False -> CP.passive=True -> safetyConfigs=[noOutput]，
# openpilot 不生成控制 CAN，pandad 把 panda 设为 noOutput（固件层拒绝 TX）。
# 注意：PASSIVE 环境变量没有任何代码读取，不起保护作用，真正的杠杆是这个 Param。
p.put_bool("OpenpilotEnabledToggle", False)
print("[orinnx] 只读防线: OpenpilotEnabledToggle=False (passive 将被 card 锁定为 True)")
PY

echo "=================================================="
echo "  openpilot-vw  Jetson Orin NX  车道线预测"
echo "=================================================="
echo "  road cam : /dev/video${ROAD_CAM}  ${ROAD_CAM_SIZE}  K=${ROAD_CAM_INTRINSICS}  exposure=${ROAD_CAM_EXPOSURE}"
if [ "$SINGLE_CAM" = "1" ]; then
  echo "  wide cam : 已禁用（单摄验证模式 SINGLE_CAM=1）"
else
  echo "  wide cam : /dev/video${WIDE_CAM}  ${WIDE_CAM_SIZE}  K=${WIDE_CAM_INTRINSICS}  exposure=${WIDE_CAM_EXPOSURE}"
fi
echo "  FORCE_ONROAD=1  PASSIVE=1  NOBOARD=1  OpenpilotEnabledToggle=False(只读锁)"
echo "  显示: MID_UI=${MID_UI:-0} (${MID_UI_SIZE:-})  BIG=${BIG:-0}  CAN_DEBUG=${CAN_DEBUG:-0}"
echo "=================================================="

# ============================================================
# Bug 2 修复：后台注入 CarParams，解除 modeld 永久阻塞
# ------------------------------------------------------------
# 根因（见 learn-docs/环境搭建与容器部署.md 第十三节 Bug 2）：
#   NOBOARD=1 无真实 CAN 时，card.py 的 Car.__init__ 永久阻塞在
#   recv_one_retry(can_sock) 等第一条 CAN，从不写 CarParams；而 modeld 的
#   params.get("CarParams", block=True) 一直等 card 写入 -> modeld 永远卡死、
#   modelV2=0。这里由外部把 CarParams 写好，modeld 读到即解阻塞进入推理循环。
#
# 时序关键（见第十五节）：CarParams 的参数标志是
#   CLEAR_ON_MANAGER_START | CLEAR_ON_ONROAD_TRANSITION，
#   manager 启动时(manager.py:46-47)和进 onroad 时(manager.py:199)各清一次。
#   因此 pre-manager 预写一定会被清掉（已验证），必须等这两次清除都过去后再注入。
#
# 不能用 IsOnroad 做闸门（实机验证发现的坑）：IsOnroad 会残留上次运行的 stale
#   True（关机不清），若据此在 manager 启动前就注入，会被 manager_init 清掉。
#   故改为"看门狗"策略：不看 IsOnroad，只要 CarParams 缺失就补写，直到它连续稳定
#   存在 STABLE_SECS 才判定已越过所有清除点并退出（硬上限 HARD_CAP_SECS 防孤儿）。
#
# 安全性：card 无 CAN 会一直阻塞，永远不置 ControlsReady=True；pandad 的
#   setSafetyMode() 依赖 ControlsReady 才执行，故 panda 一直停在上电默认只读态
#   （SILENT/NO_OUTPUT）。本注入天然只读，无需修改 card.py。若真车 CAN 接入，
#   card 会正常识别并写入（注入器仅在 CarParams 缺失时写，不覆盖），行为安全。
#
# 参数：notCar=True 是已验证可行的最简方式（与 run_laneline_demo.py 一致），
#   wheelbase 用速腾真实值 2.731。需要更完整车辆几何时可改注入
#   CarInterface.get_non_essential_params(CAR.VOLKSWAGEN_SAGITAR_MK7)。
# ============================================================
(
  python3 - <<'PY'
import time
from openpilot.common.params import Params
from cereal import car

params = Params()
cp_bytes = car.CarParams(notCar=True, wheelbase=2.731, steerRatio=15.6).to_bytes()

STABLE_SECS = 10       # CarParams 连续存在这么久 -> 视为已越过所有清除点
HARD_CAP_SECS = 180    # 安全上限，防止注入器长驻成孤儿进程
POLL = 0.5

start = time.time()
ever_injected = False
stable_since = None

while time.time() - start < HARD_CAP_SECS:
    if params.get("CarParams") is None:
        params.put("CarParams", cp_bytes)
        stable_since = None
        if not ever_injected:
            print("[orinnx][inject] 已注入 CarParams(notCar=True, wheelbase=2.731) 解除 modeld 阻塞", flush=True)
            ever_injected = True
    else:
        if stable_since is None:
            stable_since = time.time()
        elif ever_injected and time.time() - stable_since >= STABLE_SECS:
            print("[orinnx][inject] CarParams 已稳定存在，注入器退出", flush=True)
            break
    time.sleep(POLL)
else:
    print("[orinnx][inject] 到达时间上限退出" +
          ("（已注入）" if ever_injected else "（CarParams 一直存在，可能 card 已写入，未注入）"), flush=True)
PY
) &
echo "  [inject] CarParams 后台看门狗注入器已启动（CarParams 缺失即补写，稳定后自退）"
echo "=================================================="

# 走正规 manager 流程：manager 会根据条件自动拉起
# webcamerad → modeld → ui 等进程
exec ./launch_openpilot.sh
