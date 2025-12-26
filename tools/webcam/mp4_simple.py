#!/usr/bin/env python3
"""
简化版 MP4 转 openpilot 工具
最小化依赖，快速测试用

功能特性：
  最小化代码，快速测试
  固定20FPS输出
  直接命令行使用


python tools/webcam/mp4_simple.py video.mp4

"""

import cv2
import numpy as np
import sys
import time

from msgq.visionipc import VisionIpcServer, VisionStreamType
from cereal import messaging

def convert_mp4(mp4_file, fps=20):
    """转换MP4文件为openpilot格式"""

    # openpilot前置摄像头标准参数
    W, H = 1928, 1208

    # 初始化
    pm = messaging.PubMaster(["roadCameraState"])
    vipc = VisionIpcServer("camerad")
    vipc.create_buffers(VisionStreamType.VISION_STREAM_ROAD, 20, W, H)
    vipc.start_listener()

    # 打开视频
    cap = cv2.VideoCapture(mp4_file)
    if not cap.isOpened():
        print(f"无法打开: {mp4_file}")
        return

    print(f"开始转换: {mp4_file}")
    print(f"输出格式: {W}x{H} @ {fps}FPS")

    frame_id = 0
    frame_time = 1.0 / fps

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 调整尺寸并转YUV
            resized = cv2.resize(frame, (W, H))
            yuv = cv2.cvtColor(resized, cv2.COLOR_BGR2YUV_I420).flatten()

            # 发送数据
            eof = int(frame_id * frame_time * 1e9)
            vipc.send(VisionStreamType.VISION_STREAM_ROAD, yuv, frame_id, eof, eof)

            # 发送状态
            dat = messaging.new_message("roadCameraState", valid=True)
            dat.roadCameraState = {"frameId": frame_id, "transform": [1,0,0,0,1,0,0,0,1]}
            pm.send("roadCameraState", dat)

            frame_id += 1
            time.sleep(frame_time)

            if frame_id % 50 == 0:
                print(f"已处理 {frame_id} 帧")

    except KeyboardInterrupt:
        print("\n停止")
    finally:
        cap.release()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python mp4_simple.py <mp4文件>")
        sys.exit(1)

    convert_mp4(sys.argv[1])
