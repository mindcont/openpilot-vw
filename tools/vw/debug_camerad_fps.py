#!/usr/bin/env python3
"""
独立验证 camerad 喂帧频率（不启动 modeld，隔离 CUDA/调度变量）

用法:
  cd ~/openpilot && source .venv/bin/activate
  python3 tools/vw/debug_camerad_fps.py

只启动 webcamerad，订阅 roadCameraState，统计实际到达间隔。
固定参数：WEBCAM_FPS 用默认值（run_laneline_demo.py 中为 5），不在本次调试中更改。
"""
import os
import time

# 与 run_laneline_demo.py 完全一致的环境变量，保持可比性
os.environ['USE_WEBCAM'] = '1'
os.environ.setdefault('WEBCAM_FPS', '5')
DEMO_VIDEO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools/webcam/demo.mp4')
os.environ['ROAD_CAM'] = os.path.abspath(DEMO_VIDEO)
os.environ['WIDE_CAM'] = ''

from cereal import messaging
from openpilot.system.manager.process_config import managed_processes

DURATION_SEC = 30

def main():
    print(f"[probe] ROAD_CAM={os.environ['ROAD_CAM']}")
    print(f"[probe] WEBCAM_FPS={os.environ['WEBCAM_FPS']}")
    print(f"[probe] 只启动 webcamerad，不启动 modeld")

    managed_processes['webcamerad'].start()
    print("[probe] webcamerad 已启动，等待 2 秒热身...")
    time.sleep(2)

    sm = messaging.SubMaster(['roadCameraState'])
    timestamps = []
    frame_ids = []

    print(f"[probe] 开始采样 {DURATION_SEC} 秒...")
    t_start = time.monotonic()
    last_print = t_start
    while time.monotonic() - t_start < DURATION_SEC:
        sm.update(100)  # 100ms 超时
        if sm.updated['roadCameraState']:
            now = time.monotonic()
            timestamps.append(now)
            frame_ids.append(sm['roadCameraState'].frameId)
            if now - last_print > 5:
                print(f"  [t={now - t_start:5.1f}s] 已收到 {len(timestamps)} 帧，最新 frameId={frame_ids[-1]}")
                last_print = now

    managed_processes['webcamerad'].stop()

    print("-" * 60)
    print(f"[结果] 采样窗口 {DURATION_SEC}s 内共收到 {len(timestamps)} 帧")
    if len(timestamps) < 2:
        print("[结果] 帧数太少，无法算间隔统计，camerad 喂帧存在严重问题")
        return

    intervals = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
    intervals.sort()
    n = len(intervals)
    avg = sum(intervals) / n
    p50 = intervals[n // 2]
    p95 = intervals[int(n * 0.95)]
    worst = intervals[-1]
    actual_fps = len(timestamps) / (timestamps[-1] - timestamps[0])

    print(f"[结果] 实测平均 FPS: {actual_fps:.2f}  (期望 {os.environ['WEBCAM_FPS']})")
    print(f"[结果] 帧间隔: avg={avg*1000:.1f}ms  p50={p50*1000:.1f}ms  p95={p95*1000:.1f}ms  worst={worst*1000:.1f}ms")

    # frameId 连续性检查：是否有跳号（camerad 内部丢帧 / 重复）
    id_gaps = [frame_ids[i] - frame_ids[i-1] for i in range(1, len(frame_ids))]
    non_one_gaps = [g for g in id_gaps if g != 1]
    print(f"[结果] frameId 跳号次数（非+1的间隔）: {len(non_one_gaps)} / {len(id_gaps)}")
    if non_one_gaps:
        print(f"[结果] 跳号样例: {non_one_gaps[:10]}")

if __name__ == '__main__':
    main()
