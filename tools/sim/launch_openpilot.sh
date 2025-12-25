#!/usr/bin/env bash

# 设置仿真环境变量
export PASSIVE="0"           # 非被动模式，允许控制
export NOBOARD="1"           # 无硬件板卡
export SIMULATION="1"        # 仿真模式
export SKIP_FW_QUERY="1"     # 跳过固件查询
export FINGERPRINT="HONDA_CIVIC"  # 使用基础的Honda Civic指纹

# 阻止不需要的服务启动
export BLOCK="${BLOCK},camerad,loggerd,encoderd,micd,logmessaged"
if [[ "$CI" ]]; then
  # TODO: 离屏UI应该可以工作
  export BLOCK="${BLOCK},ui"
fi

# 启用openpilot参数
python3 -c "from openpilot.selfdrive.test.helpers import set_params_enabled; set_params_enabled()"

# 获取脚本目录并切换到openpilot根目录
SCRIPT_DIR=$(dirname "$0")
OPENPILOT_DIR=$SCRIPT_DIR/../../

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
cd $OPENPILOT_DIR/system/manager && exec ./manager.py
