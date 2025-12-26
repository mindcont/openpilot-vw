#!/usr/bin/env python3
"""
MP4 to openpilot 转换工具

功能：将本地MP4文件转换为openpilot可支持的格式，发送到消息队列
用途：前置摄像头数据模拟，用于测试和开发

功能特性：
  完整的命令行参数支持
  自动调整分辨率到openpilot标准 (1928x1208)
  支持循环播放
  帧率控制和状态显示

错误处理和资源清理
# 基本使用
python tools/webcam/mp4_to_openpilot.py video.mp4

# 指定帧率
python tools/webcam/mp4_to_openpilot.py video.mp4 --fps 30

# 循环播放
python tools/webcam/mp4_to_openpilot.py video.mp4 --loop

"""

import cv2
import numpy as np
import argparse
import time
from pathlib import Path

from msgq.visionipc import VisionIpcServer, VisionStreamType
from cereal import messaging
from openpilot.common.realtime import Ratekeeper

class MP4ToOpenpilot:
    def __init__(self, mp4_path, fps=20):
        self.mp4_path = mp4_path
        self.fps = fps

        # openpilot标准分辨率
        self.W = 1928
        self.H = 1208

        # 创建消息发布器
        self.pm = messaging.PubMaster(["roadCameraState"])

        # 创建VisionIPC服务器
        self.vipc_server = VisionIpcServer("camerad")
        self.vipc_server.create_buffers(VisionStreamType.VISION_STREAM_ROAD, 20, self.W, self.H)
        self.vipc_server.start_listener()

        # 打开视频文件
        self.cap = cv2.VideoCapture(str(mp4_path))
        if not self.cap.isOpened():
            raise ValueError(f"无法打开视频文件: {mp4_path}")

        # 获取原始视频信息
        self.orig_fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"视频信息: {self.total_frames} 帧, {self.orig_fps:.2f} FPS")
        print(f"输出: {self.W}x{self.H}, {self.fps} FPS")

    def resize_and_convert(self, frame):
        """调整尺寸并转换为YUV420格式"""
        # 调整到openpilot标准分辨率
        resized = cv2.resize(frame, (self.W, self.H))

        # BGR转YUV420
        yuv = cv2.cvtColor(resized, cv2.COLOR_BGR2YUV_I420)

        return yuv.flatten()

    def send_frame(self, yuv_data, frame_id):
        """发送YUV数据和摄像头状态消息"""
        # 计算时间戳
        eof = int(frame_id * (1.0 / self.fps) * 1e9)

        # 发送图像数据
        self.vipc_server.send(VisionStreamType.VISION_STREAM_ROAD, yuv_data, frame_id, eof, eof)

        # 发送状态消息
        dat = messaging.new_message("roadCameraState", valid=True)
        msg = {
            "frameId": frame_id,
            "transform": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        }
        setattr(dat, "roadCameraState", msg)
        self.pm.send("roadCameraState", dat)

    def run(self, loop=False):
        """运行转换和发送"""
        rk = Ratekeeper(self.fps, None)
        frame_id = 0

        print(f"开始发送视频数据...")

        while True:
            ret, frame = self.cap.read()

            if not ret:
                if loop:
                    # 循环播放
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    print("视频结束，重新开始...")
                    continue
                else:
                    print("视频播放完成")
                    break

            # 转换格式
            yuv_data = self.resize_and_convert(frame)

            # 发送数据
            self.send_frame(yuv_data, frame_id)

            frame_id += 1

            # 控制帧率
            rk.keep_time()

            if frame_id % 100 == 0:
                print(f"已发送 {frame_id} 帧")

    def __del__(self):
        if hasattr(self, 'cap'):
            self.cap.release()

def main():
    parser = argparse.ArgumentParser(description="将MP4文件转换为openpilot格式并发送到消息队列")
    parser.add_argument("mp4_file", help="输入的MP4文件路径")
    parser.add_argument("--fps", type=int, default=20, help="输出帧率 (默认: 20)")
    parser.add_argument("--loop", action="store_true", help="循环播放")

    args = parser.parse_args()

    mp4_path = Path(args.mp4_file)
    if not mp4_path.exists():
        print(f"错误: 文件不存在 {mp4_path}")
        return 1

    try:
        converter = MP4ToOpenpilot(mp4_path, args.fps)
        converter.run(args.loop)
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"错误: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
