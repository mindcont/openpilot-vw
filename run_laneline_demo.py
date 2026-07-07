#!/usr/bin/env python3
"""
PC 端车道线预测验证脚本

使用 demo.mp4 替代摄像头，绕过 panda/ignition 限制，
直接启动视觉流水线验证车道线预测功能。

数据流:
  demo.mp4 → webcamerad → VisionIPC → modeld → modelV2 → UI

用法:
  cd /home/wio/openpilot
  source .venv/bin/activate
  python3 run_laneline_demo.py

环境变量:
  WEBCAM_VIDEO  - 视频文件路径（默认 tools/webcam/demo.mp4）
  NO_UI         - 设为 1 则不启动 UI（仅验证 modeld 输出）
"""

import os
import sys
import time
import signal

# 设置必要的环境变量（必须在导入 openpilot 模块之前）
os.environ['USE_WEBCAM'] = '1'
os.environ['PASSIVE'] = '1'
os.environ['FINGERPRINT'] = 'VOLKSWAGEN_GOLF_MK7'
os.environ['NOBOARD'] = '1'

# 视频文件路径
DEMO_VIDEO = os.environ.get('WEBCAM_VIDEO',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools/webcam/demo.mp4'))
os.environ['ROAD_CAM'] = DEMO_VIDEO
# 禁用广角摄像头（demo 只有一个视频源）
os.environ.pop('WIDE_CAM', None)
os.environ['WIDE_CAM'] = ''

from cereal import car, log, messaging
from openpilot.common.params import Params
from openpilot.system.manager.process_config import managed_processes
from openpilot.system.hardware import HARDWARE


def setup_params():
    """设置必要的参数"""
    params = Params()
    CP = car.CarParams(notCar=True, wheelbase=2.631, steerRatio=15.6)
    params.put("CarParams", CP.to_bytes())
    params.put_bool("IsDriverViewEnabled", True)
    params.put_bool("DisableLogging", True)
    print("[DEMO] 参数设置完成")


def start_processes():
    """启动流水线关键进程"""
    procs = ['webcamerad', 'modeld', 'calibrationd', 'plannerd']

    # 如果需要 UI
    if not os.environ.get('NO_UI'):
        procs.append('ui')

    print(f"[DEMO] 启动进程: {', '.join(procs)}")
    for p in procs:
        if p in managed_processes:
            managed_processes[p].start()
            print(f"  ✓ {p}")
        else:
            print(f"  ✗ {p} (未找到)")

    return procs


def simulate_onroad(procs):
    """模拟车辆上路状态，持续发送消息"""
    pm = messaging.PubMaster(['controlsState', 'deviceState', 'pandaStates', 'carParams'])

    msgs = {s: messaging.new_message(s) for s in ['controlsState', 'deviceState', 'carParams']}
    msgs['deviceState'].deviceState.started = True
    msgs['deviceState'].deviceState.deviceType = HARDWARE.get_device_type()
    msgs['carParams'].carParams.openpilotLongitudinalControl = True

    msgs['pandaStates'] = messaging.new_message('pandaStates', 1)
    msgs['pandaStates'].pandaStates[0].ignitionLine = True
    msgs['pandaStates'].pandaStates[0].pandaType = log.PandaState.PandaType.uno

    # 同时监听 modelV2 输出
    sm = messaging.SubMaster(['modelV2'])
    model_received = False
    frame_count = 0

    print("[DEMO] 开始模拟上路状态，等待 modeld 输出...")
    print("[DEMO] 按 Ctrl+C 停止")
    print("-" * 50)

    try:
        while True:
            # 发送模拟消息
            for s in msgs:
                pm.send(s, msgs[s])

            # 检查 modelV2 输出
            sm.update(0)
            if sm.updated['modelV2']:
                frame_count += 1
                if not model_received:
                    model_received = True
                    print("[DEMO] ✅ 首次收到 modelV2 输出！车道线预测已生效")

                if frame_count % 40 == 0:  # 每 2 秒打印一次
                    model = sm['modelV2']
                    lane_count = len(model.laneLines)
                    edge_count = len(model.roadEdges)
                    lane_probs = [f"{l.prob:.2f}" for l in model.laneLines] if lane_count > 0 else []
                    print(f"[MODEL] frame={frame_count} | laneLines={lane_count} probs=[{', '.join(lane_probs)}] | roadEdges={edge_count}")

            time.sleep(1 / 100)

    except KeyboardInterrupt:
        print("\n[DEMO] 停止中...")
    finally:
        for p in procs:
            if p in managed_processes:
                managed_processes[p].stop()
        print("[DEMO] 所有进程已停止")


def main():
    print("=" * 50)
    print("  openpilot 车道线预测验证（demo.mp4 模式）")
    print("=" * 50)
    print(f"[DEMO] 视频源: {DEMO_VIDEO}")

    if not os.path.exists(DEMO_VIDEO):
        print(f"[ERROR] 视频文件不存在: {DEMO_VIDEO}")
        sys.exit(1)

    setup_params()
    procs = start_processes()

    # 等待进程启动
    print("[DEMO] 等待进程启动 (3秒)...")
    time.sleep(3)

    simulate_onroad(procs)


if __name__ == "__main__":
    main()
