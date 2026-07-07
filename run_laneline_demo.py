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
# 视频模式帧率（CPU推理慢，降低到5fps避免丢帧）
os.environ.setdefault('WEBCAM_FPS', '5')

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
    procs = ['webcamerad', 'modeld']

    # 如果需要 UI
    if not os.environ.get('NO_UI'):
        procs.append('ui')

    # 先创建 PubMaster 并发送初始消息（确保 modeld 启动时已有 publisher 在线）
    global _pm
    _pm = messaging.PubMaster(['controlsState', 'deviceState', 'pandaStates', 'carParams',
                               'liveCalibration', 'carState', 'liveDelay'])
    # 预发几条消息，确保 socket 就绪
    for _ in range(5):
        calib_msg = messaging.new_message('liveCalibration')
        calib_msg.liveCalibration.validBlocks = 20
        calib_msg.liveCalibration.calStatus = 1
        calib_msg.liveCalibration.rpyCalib = [0.0, 0.0, 0.0]
        _pm.send('liveCalibration', calib_msg)
        time.sleep(0.01)

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
    global _pm
    pm = _pm

    # 同时监听 modelV2 输出
    sm = messaging.SubMaster(['modelV2'])
    model_received = False
    frame_count = 0

    print("[DEMO] 开始模拟上路状态，等待 modeld 输出...")
    print("[DEMO] 按 Ctrl+C 停止")
    print("-" * 50)

    try:
        while True:
            # 每次发送新的消息对象，避免重复写入警告
            for s in ['controlsState', 'deviceState', 'carParams']:
                msg = messaging.new_message(s)
                if s == 'deviceState':
                    msg.deviceState.started = True
                    msg.deviceState.deviceType = HARDWARE.get_device_type()
                elif s == 'carParams':
                    msg.carParams.openpilotLongitudinalControl = True
                pm.send(s, msg)

            panda_msg = messaging.new_message('pandaStates', 1)
            panda_msg.pandaStates[0].ignitionLine = True
            panda_msg.pandaStates[0].pandaType = log.PandaState.PandaType.uno
            pm.send('pandaStates', panda_msg)

            # 发送标定数据（关键：没有这个 modeld 的 transform 矩阵为零，车道线置信度极低）
            calib_msg = messaging.new_message('liveCalibration')
            calib_msg.liveCalibration.validBlocks = 20
            calib_msg.liveCalibration.calStatus = 1
            calib_msg.liveCalibration.rpyCalib = [0.0, 0.0, 0.0]
            pm.send('liveCalibration', calib_msg)

            # 发送车辆状态（给模型提供车速估计）
            car_state_msg = messaging.new_message('carState')
            car_state_msg.carState.vEgo = 20.0  # 模拟 72km/h
            pm.send('carState', car_state_msg)

            # 发送延迟信息
            delay_msg = messaging.new_message('liveDelay')
            delay_msg.liveDelay.lateralDelay = 0.1
            pm.send('liveDelay', delay_msg)

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
                    lane_probs = [f"{p:.2f}" for p in model.laneLineProbs] if len(model.laneLineProbs) > 0 else []
                    edge_stds = [f"{s:.2f}" for s in model.roadEdgeStds] if len(model.roadEdgeStds) > 0 else []
                    # 打印车道线 y 坐标（在 10m 处的横向偏移）
                    lane_y_at_10m = []
                    for i, ll in enumerate(model.laneLines):
                        if len(ll.y) > 10:
                            lane_y_at_10m.append(f"L{i}={ll.y[10]:.1f}m")
                    # 打印路径 position
                    path_info = ""
                    if hasattr(model, 'position') and len(model.position.x) > 10:
                        path_info = f" path_x[10]={model.position.x[10]:.1f}"
                    print(f"[MODEL] frame={frame_count} | probs={lane_probs} | lanes=[{', '.join(lane_y_at_10m)}] | edges_std={edge_stds}{path_info}")

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
