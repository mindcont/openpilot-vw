#!/usr/bin/env python3
import time
import cv2
import numpy as np

from msgq.visionipc.visionipc_pyx import (
  VisionIPCServer,
  VisionStreamType,
  VisionStream
)

from msgq.visionipc import VisionIpcServer, VisionIpcClient, VisionStreamType

# =====================
# 配置
# =====================
VIDEO_DEV = "/dev/video2"
WIDTH = 640
HEIGHT = 480
FPS = 30

# =====================
# 打开 USB 摄像头
# =====================
cap = cv2.VideoCapture(VIDEO_DEV, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
cap.set(cv2.CAP_PROP_FPS, FPS)

if not cap.isOpened():
  raise RuntimeError("❌ 无法打开摄像头 /dev/video2")

print("✅ USB 摄像头已打开")

# =====================
# 创建 VisionIPC Server
# =====================
server = VisionIPCServer("fake_camerad", [
  VisionStream(
    VisionStreamType.VISION_STREAM_ROAD,
    WIDTH,
    HEIGHT,
    VisionStreamType.VISION_STREAM_TYPE_RGB
  )
])

server.start()
print("✅ VisionIPC Server 启动")

# =====================
# 主循环：送帧
# =====================
frame_interval = 1.0 / FPS

while True:
  t0 = time.time()

  ret, frame = cap.read()
  if not ret:
    print("⚠️ 读取帧失败")
    time.sleep(0.01)
    continue

  # OpenCV 默认是 BGR → 转 RGB
  frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

  # 必须是连续内存
  frame_rgb = np.ascontiguousarray(frame_rgb)

  # 发送到 openpilot
  server.send(
    VisionStreamType.VISION_STREAM_ROAD,
    frame_rgb.data,
    int(time.time() * 1e9)  # 纳秒时间戳
  )

  # 控制帧率
  dt = time.time() - t0
  if dt < frame_interval:
    time.sleep(frame_interval - dt)
