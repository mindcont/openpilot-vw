#!/usr/bin/env bash
# ============================================================
# openpilot-vw Jetson Orin NX 生产启动脚本（真实 CAN 版）
#
# 用途：接入真实 panda + 真实 CAN（J533 网关），车道线预测 + 真实车速/方向盘等
#       carState，仍然不控车。
# 平台：NVIDIA Jetson Orin NX + 双 USB/CSI 摄像头 + comma panda（USB）
#
# 与 start_openpilot_orinnx.sh（纯视觉版）的区别：
#   - 去掉 NOBOARD=1：让 pandad 正常连接真实 panda 硬件
#   - 去掉看门狗 CarParams 注入器：不再需要，card.py 会收到真实 CAN 后自己
#     调用 get_car() 识别车型并写入 CarParams
#   - 保留 FORCE_ONROAD=1：接入真实点火信号前先保留，减少变量，跑通后可评估
#     是否切换成靠真实 ignition 信号进 onroad
#   - **保留只读防线不变**：OpenpilotEnabledToggle=False 仍是最重要的一行，
#     决定 card.py 重算出 passive=True，panda 固件层最终锁定在只读态（详见
#     learn-docs/车型适配/CAN接入实车任务清单.md 「零、安全设计基线」）
#
# 使用前必读：learn-docs/车型适配/CAN接入实车任务清单.md
#   本脚本仅在该清单「三、Day1」步骤 8 及之后使用，之前的步骤（R1-R4 复核、
#   步骤 1 panda 硬件确认、步骤 3/4 物理接线、步骤 5-7 上电前/中的只读核实）
#   必须先完成。核心底线：CAN 只读，任何情况下不向总线发送任何数据。
#   每一步都要配合 tools/vw/check_panda_readonly.py 做只读核实，任何异常立即
#   物理拔线，不继续。
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
# 单摄验证模式开关（沿用纯视觉版的验证经验：首跑建议单摄）
# ============================================================
export SINGLE_CAM=${SINGLE_CAM:-0}

# ============================================================
# 摄像头配置（★ 需按实机调整 ★，与纯视觉版一致）
# ============================================================
export ROAD_CAM=0
export WIDE_CAM=2
export ROAD_CAM_SIZE=1928x1208
export WIDE_CAM_SIZE=1928x1208
export ROAD_CAM_INTRINSICS="1928,1208,2648"
export WIDE_CAM_INTRINSICS="1928,1208,567"
export CAM_FLIP=0

if [ "$SINGLE_CAM" = "1" ]; then
  export WIDE_CAM=""
fi

# ============================================================
# 曝光（与纯视觉版一致，软件自动曝光已实机验证通过，默认开启）
# ============================================================
export ROAD_CAM_EXPOSURE=${ROAD_CAM_EXPOSURE:-50}
export WIDE_CAM_EXPOSURE=${WIDE_CAM_EXPOSURE:-50}
export ROAD_CAM_GAIN=${ROAD_CAM_GAIN:-40}
export WIDE_CAM_GAIN=${WIDE_CAM_GAIN:-40}
export AUTO_EXPOSURE=${AUTO_EXPOSURE:-1}

function set_camera_exposure() {
  local dev="/dev/video$1"
  local exposure="$2"
  local gain="$3"
  if [ -e "$dev" ] && command -v v4l2-ctl > /dev/null 2>&1; then
    v4l2-ctl -d "$dev" --set-ctrl=auto_exposure=1 2>/dev/null
    v4l2-ctl -d "$dev" --set-ctrl=exposure_time_absolute="$exposure" 2>/dev/null
    [ -n "$gain" ] && v4l2-ctl -d "$dev" --set-ctrl=gain="$gain" 2>/dev/null
    echo "  已设置 $dev 曝光: manual, exposure_time_absolute=$exposure, gain=${gain:-默认}"
  else
    echo "  [警告] $dev 不存在或 v4l2-ctl 未安装，跳过曝光设置"
  fi
}

set_camera_exposure "$ROAD_CAM" "$ROAD_CAM_EXPOSURE" "$ROAD_CAM_GAIN"
if [ -n "$WIDE_CAM" ]; then
  set_camera_exposure "$WIDE_CAM" "$WIDE_CAM_EXPOSURE" "$WIDE_CAM_GAIN"
fi

# ============================================================
# 运行模式（★ 与纯视觉版的关键差异 ★）
# ============================================================
export USE_WEBCAM=1        # 使用 webcamerad（USB/CSI 摄像头）
export FORCE_ONROAD=1      # 暂保留：先减少变量，跑通后再评估是否靠真实 ignition
# 不设 NOBOARD —— 让 pandad 正常连接真实 panda 硬件（纯视觉版靠 NOBOARD=1
#   让 pandad 视为无硬件；真实 CAN 场景需要 pandad 真正工作，不能设它）
export SKIP_FW_QUERY=1     # 跳过固件查询：避免走 get_vin/get_present_ecus/
                            # get_fw_versions_ordered 这些主动发 CAN 请求的路径
                            # （见 CAN接入实车任务清单.md R2 复核结论）
export FINGERPRINT="VOLKSWAGEN_SAGITAR_MK7"  # 速腾正式车型指纹；FW_VERSIONS/
                            # chassis_codes 仍是占位，自动识别大概率识别不出来，
                            # 继续用强制指定绕开 VIN/FW 匹配

# 显示配置：与纯视觉版一致
export MID_UI=1
export MID_UI_SIZE=${MID_UI_SIZE:-1280x720}
export UI_FULLSCREEN=${UI_FULLSCREEN:-1}
# export CAN_DEBUG=1        # 建议接入 CAN 后打开，onroad 画面叠加显示 CAN 关键变量

# ★ 注意：切勿设置 IsDriverViewEnabled=True ★
export LOGPRINT=info
export OPENPILOT_DATA=/tmp/data

# ============================================================
# 跳过 onboarding（与纯视觉版一致，首次进 onroad 必做）
# ------------------------------------------------------------
# 同时是【只读防线第一道 · 最重要的一行不能删】：OpenpilotEnabledToggle=False
# 强制关闭 openpilot 控车总开关。card.py 会用该 Param 重算 passive：
#   OpenpilotEnabledToggle=False -> controller_available=False ->
#   CP.passive=True -> safetyConfigs=[noOutput]
# 这一行对真实识别路径（get_car()）与注入路径同样生效（已在 CAN接入实车任务
# 清单.md R1 复核确认，代码路径不分叉）。
# ============================================================
python3 - <<'PY'
from openpilot.common.params import Params
from openpilot.system.version import terms_version, training_version
p = Params()
p.put("HasAcceptedTerms", terms_version)
p.put("CompletedTrainingVersion", training_version)
print(f"[orinnx-can] onboarding 已跳过: terms={terms_version} training={training_version}")

# 只读防线（第一道软件闸门）—— 真实 CAN 场景下最重要的一行，不能删/不能注释掉。
# 见 learn-docs/车型适配/CAN接入实车任务清单.md 「零、安全设计基线」。
p.put_bool("OpenpilotEnabledToggle", False)
print("[orinnx-can] 只读防线: OpenpilotEnabledToggle=False (passive 将被 card 锁定为 True)")
PY

echo "=================================================="
echo "  openpilot-vw  Jetson Orin NX  真实 CAN 版（不控车）"
echo "=================================================="
echo "  road cam : /dev/video${ROAD_CAM}  ${ROAD_CAM_SIZE}  K=${ROAD_CAM_INTRINSICS}  exposure=${ROAD_CAM_EXPOSURE}"
if [ "$SINGLE_CAM" = "1" ]; then
  echo "  wide cam : 已禁用（单摄验证模式 SINGLE_CAM=1）"
else
  echo "  wide cam : /dev/video${WIDE_CAM}  ${WIDE_CAM_SIZE}  K=${WIDE_CAM_INTRINSICS}  exposure=${WIDE_CAM_EXPOSURE}"
fi
echo "  FORCE_ONROAD=1  FINGERPRINT=${FINGERPRINT}  SKIP_FW_QUERY=1"
echo "  OpenpilotEnabledToggle=False(只读锁，不控车)  ★ NOBOARD 未设置，pandad 将连接真实 panda ★"
echo "  显示: MID_UI=${MID_UI:-0} (${MID_UI_SIZE:-})  CAN_DEBUG=${CAN_DEBUG:-0}"
echo "=================================================="
echo "  ⚠️  上路前请先跑一次: python3 tools/vw/check_panda_readonly.py"
echo "  ⚠️  运行期间建议持续用该脚本轮询核实，任何异常立即物理拔线"
echo "=================================================="

# 走正规 manager 流程：manager 会自动拉起
# webcamerad → modeld → ui → pandad → card 等进程
# card.py 会阻塞等待真实 CAN 包，收到后走 get_car() 识别车型（FINGERPRINT 强制
# 指定时跳过 VIN/FW 匹配），随后正常写入 CarParams，本脚本不需要任何看门狗注入器。
exec ./launch_openpilot.sh
