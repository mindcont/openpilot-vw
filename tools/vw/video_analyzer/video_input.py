#!/usr/bin/env python3
import cv2
import numpy as np
import time
import threading
from typing import Optional

import cereal.messaging as messaging
from cereal.visionipc import VisionIpcServer, VisionStreamType
from common.realtime import Ratekeeper

W, H = 1928, 1208

class VideoInput:
    def __init__(self, video_path: str, fps: float = 20.0):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        self.fps = fps
        self.frame_id = 0
        self.running = False
        
        # Get video properties
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.video_fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        # Vision IPC server
        self.vipc_server = VisionIpcServer("video_analyzer")
        self.vipc_server.create_buffers(VisionStreamType.VISION_STREAM_ROAD, 5, False, W, H)
        self.vipc_server.start_listener()
        
        # Messaging
        self.pm = messaging.PubMaster(['roadCameraState'])
        
        print(f"Video loaded: {self.total_frames} frames at {self.video_fps} fps")
    
    def process_frame(self) -> bool:
        ret, frame = self.cap.read()
        if not ret:
            return False
        
        # Resize to openpilot standard
        frame = cv2.resize(frame, (W, H))
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert to YUV420 format
        frame_yuv = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2YUV_I420)
        
        # Send to vision IPC
        timestamp = int(time.time() * 1e9)
        self.vipc_server.send(VisionStreamType.VISION_STREAM_ROAD, 
                             frame_yuv.tobytes(), self.frame_id, timestamp, timestamp)
        
        # Send camera state message
        dat = messaging.new_message('roadCameraState')
        dat.roadCameraState = {
            'frameId': self.frame_id,
            'timestampSof': timestamp,
            'timestampEof': timestamp,
            'transform': [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        }
        self.pm.send('roadCameraState', dat)
        
        self.frame_id += 1
        return True
    
    def run_threaded(self):
        """Run video processing in a separate thread"""
        self.running = True
        rk = Ratekeeper(self.fps)
        
        while self.running and self.process_frame():
            rk.keep_time()
        
        self.running = False
    
    def start(self):
        """Start video processing thread"""
        self.thread = threading.Thread(target=self.run_threaded)
        self.thread.start()
    
    def stop(self):
        """Stop video processing"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join()
    
    def get_progress(self) -> float:
        """Get processing progress (0.0 to 1.0)"""
        return self.frame_id / self.total_frames if self.total_frames > 0 else 0.0
    
    def __del__(self):
        if self.cap:
            self.cap.release()