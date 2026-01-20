#!/usr/bin/env bash

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1

export BIG=1
#export CAMERA=webcam
#export WEBCAM=1
#export WEBCAM_DEVICE=/dev/video2
#export WEBCAM_WIDTH=640
#export WEBCAM_HEIGHT=480
#export WEBCAM_FPS=30
#export WEBCAM_FORMAT=yuyv

# 关键！！！
export PASSIVE=1
export PC=1
export OPENPILOT_DATA=/data

# PC模式日志配置 - 使用/data目录
export LOGPRINT=info  # 设置控制台日志级别为info
export LOG_ROOT=/data/media/0/realdata  # 自定义数据日志根目录
# 确保PC模式下的日志目录存在
mkdir -p /data/logs
mkdir -p /data/media/0/realdata
mkdir -p /data/params
mkdir -p /data/stats

# models get lower priority than ui
# - ui is ~5ms
# - modeld is 20ms
# - DM is 10ms
# in order to run ui at 60fps (16.67ms), we need to allow
# it to preempt the model workloads. we have enough
# headroom for this until ui is moved to the CPU.
export QCOM_PRIORITY=12

if [ -z "$AGNOS_VERSION" ]; then
  export AGNOS_VERSION="16"
fi

export STAGING_ROOT="/data/safe_staging"
