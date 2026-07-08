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
# 摄像头配置（★ 需按实机调整 ★）
# ============================================================
# 设备号：用 `v4l2-ctl --list-devices` 查询后填写
export ROAD_CAM=0          # 前视窄视野摄像头 -> /dev/video0
export WIDE_CAM=1          # 前视宽视野摄像头 -> /dev/video1

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

# ============================================================
# 运行模式
# ============================================================
export USE_WEBCAM=1        # 使用 webcamerad（USB/CSI 摄像头）
export FORCE_ONROAD=1      # 无 panda 平台强制进入 onroad
export PASSIVE=1           # 被动模式，仅观察不输出控制
export NOBOARD=1           # 无 panda 硬件
export SKIP_FW_QUERY=1     # 跳过车辆固件查询
export FINGERPRINT="VOLKSWAGEN_GOLF_MK7"  # 代理指纹（MQB 平台）
export BIG=1               # 大屏 UI 布局（MainLayout + AugmentedRoadView）

# ★ 注意：切勿设置 IsDriverViewEnabled=True ★
#   它会使 startup_conditions["not_driver_view"]=False 从而阻塞 onroad 启动。
#   本脚本靠 FORCE_ONROAD 进入 onroad，不需要 driver view。

export LOGPRINT=info
export OPENPILOT_DATA=/tmp/data

echo "=================================================="
echo "  openpilot-vw  Jetson Orin NX  车道线预测"
echo "=================================================="
echo "  road cam : /dev/video${ROAD_CAM}  ${ROAD_CAM_SIZE}  K=${ROAD_CAM_INTRINSICS}"
echo "  wide cam : /dev/video${WIDE_CAM}  ${WIDE_CAM_SIZE}  K=${WIDE_CAM_INTRINSICS}"
echo "  FORCE_ONROAD=1  PASSIVE=1  NOBOARD=1"
echo "=================================================="

# 走正规 manager 流程：manager 会根据条件自动拉起
# webcamerad → modeld → ui 等进程
exec ./launch_openpilot.sh
