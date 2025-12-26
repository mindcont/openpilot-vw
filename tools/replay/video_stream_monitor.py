#!/usr/bin/env python3
"""
openpilot 视频流监听器
实时监听和显示 openpilot 摄像头数据流
"""

import cv2
import numpy as np
import argparse
import time
from msgq.visionipc import VisionIpcClient, VisionStreamType

class VideoStreamMonitor:
    def __init__(self, stream_type="road", server="camerad"):
        """
        初始化视频流监听器
        
        Args:
            stream_type: 摄像头类型 ("road", "driver", "wide")
            server: VisionIPC服务器名称
        """
        self.stream_types = {
            "road": VisionStreamType.VISION_STREAM_ROAD,
            "driver": VisionStreamType.VISION_STREAM_DRIVER, 
            "wide": VisionStreamType.VISION_STREAM_WIDE_ROAD
        }
        
        if stream_type not in self.stream_types:
            raise ValueError(f"不支持的流类型: {stream_type}")
            
        self.stream_type = self.stream_types[stream_type]
        self.server = server
        self.client = None
        self.frame_count = 0
        self.start_time = time.time()
        
    def connect(self):
        """连接到视频流"""
        print(f"连接到 {self.server} 的 {list(self.stream_types.keys())[list(self.stream_types.values()).index(self.stream_type)]} 流...")
        
        self.client = VisionIpcClient(self.server, self.stream_type, True)
        
        # 等待连接
        retry_count = 0
        while not self.client.is_connected() and retry_count < 10:
            print(f"尝试连接... ({retry_count + 1}/10)")
            self.client.connect(True)
            time.sleep(1)
            retry_count += 1
            
        if not self.client.is_connected():
            raise ConnectionError("无法连接到视频流")
            
        print(f"已连接! 分辨率: {self.client.width}x{self.client.height}")
        
    def yuv_to_rgb(self, yuv_data):
        """将YUV数据转换为RGB - 按照openpilot标准方式"""
        h, w = self.client.height, self.client.width
        actual_size = len(yuv_data)
        
        # openpilot使用NV12格式: Y平面 + UV交错
        # 数据结构: [Y_data(h*w)] + [UV_data(h*w/2)]
        expected_size = h * w * 3 // 2  # NV12格式的标准大小
        
        if actual_size != expected_size:
            print(f"数据大小不匹配: 期望 {expected_size}, 实际 {actual_size}")
            # 尝试计算正确的尺寸
            if actual_size > h * w:
                # 可能是不同的YUV格式
                pass
        
        try:
            # 按照cameraview.py的方式处理
            # Y平面数据
            y_size = h * w
            y_data = yuv_data[:y_size].reshape((h, w))
            
            # UV交错数据 (NV12格式)
            uv_size = h * w // 2
            if actual_size >= y_size + uv_size:
                uv_data = yuv_data[y_size:y_size + uv_size].reshape((h // 2, w // 2, 2))
                
                # 手动YUV到RGB转换 (按照OpenGL着色器逻辑)
                # 从 cameraview.py 的 fragment shader
                rgb_img = np.zeros((h, w, 3), dtype=np.uint8)
                
                for i in range(h):
                    for j in range(w):
                        y = y_data[i, j] / 255.0
                        
                        # UV采样 (下采样)
                        uv_i, uv_j = i // 2, j // 2
                        if uv_i < h // 2 and uv_j < w // 2:
                            u = (uv_data[uv_i, uv_j, 0] / 255.0) - 0.5
                            v = (uv_data[uv_i, uv_j, 1] / 255.0) - 0.5
                        else:
                            u = v = 0
                        
                        # YUV到RGB转换公式
                        r = y + 1.402 * v
                        g = y - 0.344 * u - 0.714 * v  
                        b = y + 1.772 * u
                        
                        # 限制到[0,1]范围并转换为字节
                        rgb_img[i, j, 0] = int(np.clip(r * 255, 0, 255))
                        rgb_img[i, j, 1] = int(np.clip(g * 255, 0, 255))
                        rgb_img[i, j, 2] = int(np.clip(b * 255, 0, 255))
                
                return rgb_img
            else:
                # 如果UV数据不足，只显示灰度图像
                return cv2.cvtColor(y_data, cv2.COLOR_GRAY2RGB)
                
        except Exception as e:
            print(f"YUV解析失败: {e}")
            # 创建占位图像
            placeholder = np.zeros((h, w, 3), dtype=np.uint8)
            cv2.putText(placeholder, f"Parse Error: {actual_size} bytes", (50, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(placeholder, f"Expected: {expected_size} bytes", (50, 100), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            return placeholder
        
    def display_frame_info(self, frame, fps):
        """在帧上显示信息"""
        info_text = [
            f"帧数: {self.frame_count}",
            f"FPS: {fps:.1f}",
            f"分辨率: {self.client.width}x{self.client.height}",
            f"流类型: {list(self.stream_types.keys())[list(self.stream_types.values()).index(self.stream_type)]}",
            "按 'q' 退出, 's' 截图"
        ]
        
        for i, text in enumerate(info_text):
            cv2.putText(frame, text, (10, 30 + i * 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        return frame
        
    def save_screenshot(self, frame):
        """保存截图"""
        timestamp = int(time.time())
        filename = f"openpilot_frame_{timestamp}.jpg"
        try:
            cv2.imwrite(filename, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            print(f"截图已保存: {filename}")
        except Exception as e:
            print(f"保存截图失败: {e}")
        
    def run(self):
        """运行视频流监听器"""
        try:
            self.connect()
            
            print("开始监听视频流... (按 Ctrl+C 退出)")
            
            while True:
                # 接收帧数据
                yuv_frame = self.client.recv()
                
                if yuv_frame is None:
                    print("未收到帧数据")
                    time.sleep(0.01)
                    continue
                    
                # 转换为RGB
                try:
                    rgb_frame = self.yuv_to_rgb(yuv_frame.data)
                    
                    # 只在第一帧显示数据信息
                    if self.frame_count == 0:
                        print(f"成功解析帧数据: {len(yuv_frame.data)} bytes -> {rgb_frame.shape}")
                        
                except Exception as e:
                    if self.frame_count < 10:  # 只显示前10次错误
                        print(f"帧转换错误: {e}")
                    continue
                
                # 计算FPS
                self.frame_count += 1
                elapsed_time = time.time() - self.start_time
                fps = self.frame_count / elapsed_time if elapsed_time > 0 else 0
                
                # 保存帧到文件（每100帧保存一次）
                if self.frame_count % 100 == 0:
                    timestamp = int(time.time())
                    filename = f"frame_{self.frame_count}_{timestamp}.jpg"
                    cv2.imwrite(filename, cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR))
                    print(f"帧 {self.frame_count} 已保存: {filename} (FPS: {fps:.1f})")
                    
        except KeyboardInterrupt:
            print(f"\n用户中断，总共处理了 {self.frame_count} 帧")
        except Exception as e:
            print(f"错误: {e}")

def main():
    parser = argparse.ArgumentParser(description="openpilot 视频流监听器")
    parser.add_argument("--stream", choices=["road", "driver", "wide"], 
                       default="road", help="摄像头类型")
    parser.add_argument("--server", default="camerad", 
                       help="VisionIPC服务器名称")
    
    args = parser.parse_args()
    
    print("=== openpilot 视频流监听器 ===")
    print(f"流类型: {args.stream}")
    print(f"服务器: {args.server}")
    
    monitor = VideoStreamMonitor(args.stream, args.server)
    monitor.run()

if __name__ == "__main__":
    main()