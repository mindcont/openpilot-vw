#!/usr/bin/env python3
"""
webcam 摄像头守护进程 (camerad)

功能说明：
- 用于在PC上使用USB摄像头替代openpilot专用硬件摄像头
- 采集摄像头数据并通过两种机制分发给其他进程：
  1. VisionIPC: 高效的共享内存传输，用于AI模型处理
  2. Messaging: 消息系统传输摄像头状态信息

数据流：
摄像头 → YUV数据 → VisionIPC → modeld (AI模型)
       ↓
   摄像头状态 → Messaging → 其他进程

支持的摄像头类型：
- ROAD_CAM: 主摄像头（前视道路）
- WIDE_CAM: 广角摄像头（可选）
- DRIVER_CAM: 驾驶员监控摄像头（可选）
"""

import threading
import os
import platform
from collections import namedtuple

# VisionIPC: 用于高效传输图像数据的共享内存机制
# - VisionIpcServer: 创建共享内存服务器
# - VisionStreamType: 定义不同类型的视频流
from msgq.visionipc import VisionIpcServer, VisionStreamType

# messaging: openpilot 消息传递系统
# 用于发布摄像头状态消息给其他进程
from cereal import messaging

# Camera: 摄像头抽象类，处理具体的摄像头操作
# 封装了摄像头的初始化、配置和数据读取
from openpilot.tools.webcam.camera import Camera

# Ratekeeper: 频率控制器，确保稳定的帧率
# 用于维持20fps的摄像头采集频率
from openpilot.common.realtime import Ratekeeper

# 环境变量配置摄像头设备ID
# ROAD_CAM: 主摄像头（前视窄视野/长焦），默认使用设备0
ROAD_CAM = os.getenv("ROAD_CAM", "0")
# WIDE_CAM: 广角摄像头（宽视野），默认使用设备1
WIDE_CAM = os.getenv("WIDE_CAM", "1")
# DRIVER_CAM: 驾驶员监控摄像头（可选）
DRIVER_CAM = os.getenv("DRIVER_CAM")

# 每个摄像头的目标分辨率（宽x高），必须与 DEVICE_CAMERAS 中对应 intrinsics 分辨率一致
# 默认使用 comma 硬件 AR/OX 传感器参数：road=1928x1208, wide=1928x1208
def _parse_size(env_name, default):
  val = os.getenv(env_name)
  if not val:
    return default
  try:
    w, h = val.lower().split("x")
    return (int(w), int(h))
  except (ValueError, AttributeError):
    print(f"[camerad] 无法解析 {env_name}={val}，使用默认 {default}")
    return default

ROAD_CAM_SIZE = _parse_size("ROAD_CAM_SIZE", (1928, 1208))
WIDE_CAM_SIZE = _parse_size("WIDE_CAM_SIZE", (1928, 1208))
DRIVER_CAM_SIZE = _parse_size("DRIVER_CAM_SIZE", (1928, 1208))

# 摄像头类型定义：包含消息名称、流类型、摄像头ID和目标分辨率
CameraType = namedtuple("CameraType", ["msg_name", "stream_type", "cam_id", "size"])

# 摄像头配置列表
# 至少包含主摄像头，根据环境变量添加其他摄像头
CAMERAS = [
  # 主摄像头：发布 roadCameraState 消息，使用 ROAD 流类型
  CameraType("roadCameraState", VisionStreamType.VISION_STREAM_ROAD, ROAD_CAM, ROAD_CAM_SIZE)
]
# 如果配置了广角摄像头，添加到列表
if WIDE_CAM:
  CAMERAS.append(CameraType("wideRoadCameraState", VisionStreamType.VISION_STREAM_WIDE_ROAD, WIDE_CAM, WIDE_CAM_SIZE))
  print(f"添加广角摄像头: {WIDE_CAM} ({WIDE_CAM_SIZE[0]}x{WIDE_CAM_SIZE[1]})")
# 如果配置了驾驶员监控摄像头，添加到列表
if DRIVER_CAM:
  CAMERAS.append(CameraType("driverCameraState", VisionStreamType.VISION_STREAM_DRIVER, DRIVER_CAM, DRIVER_CAM_SIZE))
  print(f"添加驾驶员摄像头: {DRIVER_CAM} ({DRIVER_CAM_SIZE[0]}x{DRIVER_CAM_SIZE[1]})")

class Camerad:
  """摄像头守护进程主类

  负责管理多个摄像头，采集图像数据并通过两种方式分发：
  1. VisionIPC: 高效的共享内存方式，用于传输原始图像数据给AI模型
  2. Messaging: 消息系统，用于传输摄像头状态信息给其他进程
  """

  def __init__(self):
    # 创建消息发布器，用于发布摄像头状态消息
    # 为每个摄像头创建对应的消息通道
    self.pm = messaging.PubMaster([c.msg_name for c in CAMERAS])

    # 创建 VisionIPC 服务器，用于高效传输图像数据
    # "camerad" 是服务名称，其他进程通过此名称连接
    self.vipc_server = VisionIpcServer("camerad")

    # 初始化摄像头列表
    self.cameras = []
    for c in CAMERAS:
      # 判断 cam_id 是否为视频文件路径
      if os.path.isfile(c.cam_id):
        cam_device = c.cam_id
      elif platform.system() != "Darwin":
        cam_device = f"/dev/video{c.cam_id}"
      else:
        cam_device = c.cam_id

      # 创建摄像头对象（传入该摄像头的目标分辨率）
      cam = Camera(c.msg_name, c.stream_type, cam_device, target_size=c.size)
      self.cameras.append(cam)

      # 为每个摄像头流创建共享内存缓冲区
      # 参数：流类型, 缓冲区数量(20), 宽度, 高度
      self.vipc_server.create_buffers(c.stream_type, 20, cam.W, cam.H)

    # 启动 VisionIPC 监听器，开始接受客户端连接
    self.vipc_server.start_listener()

  def _send_yuv(self, yuv, frame_id, pub_type, yuv_type):
    """发送YUV图像数据和摄像头状态消息

    Args:
        yuv: YUV格式的图像数据
        frame_id: 帧ID，用于同步和追踪
        pub_type: 消息发布类型（如 roadCameraState）
        yuv_type: VisionIPC流类型
    """
    # 计算帧结束时间戳（纳秒）
    # 假设20fps，每帧间隔0.05秒
    eof = int(frame_id * 0.05 * 1e9)

    # 通过 VisionIPC 发送原始图像数据
    # 参数：流类型, 图像数据, 帧ID, 开始时间戳, 结束时间戳
    self.vipc_server.send(yuv_type, yuv, frame_id, eof, eof)

    # 创建摄像头状态消息
    dat = messaging.new_message(pub_type, valid=True)

    # 构建消息内容
    msg = {
      "frameId": frame_id,  # 帧ID，用于与图像数据同步
      # 变换矩阵（3x3单位矩阵）- 表示无几何变换
      "transform": [1.0, 0.0, 0.0,
                    0.0, 1.0, 0.0,
                    0.0, 0.0, 1.0]
    }

    # 设置消息内容并发送
    setattr(dat, pub_type, msg)
    self.pm.send(pub_type, dat)

  def camera_runner(self, cam):
    """单个摄像头的运行循环

    每个摄像头在独立线程中运行此函数，持续采集和发送图像数据

    Args:
        cam: Camera对象，包含摄像头的所有配置和状态
    """
    # 创建频率控制器
    # 视频文件模式使用较低帧率（CPU推理较慢），摄像头模式用20fps
    fps = int(os.getenv("WEBCAM_FPS", "20")) if cam.is_video_file else 20
    rk = Ratekeeper(fps, None)

    # 持续读取摄像头帧数据
    for yuv in cam.read_frames():
      # 发送YUV图像数据和状态消息
      self._send_yuv(yuv, cam.cur_frame_id, cam.cam_type_state, cam.stream_type)

      # 递增帧计数器
      cam.cur_frame_id += 1

      # 维持稳定的帧率，如果处理太快会等待
      rk.keep_time()

  def run(self):
    """启动所有摄像头线程并等待完成

    为每个摄像头创建独立的线程，实现并行处理多个摄像头
    这样可以避免一个摄像头的延迟影响其他摄像头的帧率
    """
    threads = []

    # 为每个摄像头创建并启动独立线程
    for cam in self.cameras:
      cam_thread = threading.Thread(target=self.camera_runner, args=(cam,))
      cam_thread.start()
      threads.append(cam_thread)

    # 等待所有摄像头线程完成（通常不会退出，除非程序终止）
    for t in threads:
      t.join()


def main():
  """主函数：创建并运行摄像头守护进程

  这是webcam版本的camerad，用于在PC上使用USB摄像头
  替代openpilot专用硬件上的摄像头系统
  """
  # 创建摄像头守护进程实例
  camerad = Camerad()

  # 开始运行，此函数会阻塞直到程序终止
  camerad.run()


if __name__ == "__main__":
  main()
