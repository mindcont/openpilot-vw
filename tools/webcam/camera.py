import av
import os
import cv2 as cv

class Camera:
  def __init__(self, cam_type_state, stream_type, camera_id):
    try:
      camera_id = int(camera_id)
    except ValueError: # allow strings, ex: /dev/video0 or /path/to/video.mp4
      pass
    self.cam_type_state = cam_type_state
    self.stream_type = stream_type
    self.cur_frame_id = 0

    # 判断是否为视频文件
    self.is_video_file = isinstance(camera_id, str) and os.path.isfile(camera_id)

    print(f"Opening {cam_type_state} at {camera_id} ({'video file' if self.is_video_file else 'camera'})")

    self.camera_id = camera_id
    self.cap = cv.VideoCapture(camera_id)

    # 目标分辨率 — 必须与 DEVICE_CAMERAS 中的 intrinsics 对应
    # PC 模式下 fcam 的原始分辨率是 1928x1208
    self.target_W = 1928
    self.target_H = 1208

    if not self.is_video_file:
      self.cap.set(cv.CAP_PROP_FRAME_WIDTH, float(self.target_W))
      self.cap.set(cv.CAP_PROP_FRAME_HEIGHT, float(self.target_H))
      self.cap.set(cv.CAP_PROP_FPS, 25.0)

    self.W = self.target_W if self.is_video_file else self.cap.get(cv.CAP_PROP_FRAME_WIDTH)
    self.H = self.target_H if self.is_video_file else self.cap.get(cv.CAP_PROP_FRAME_HEIGHT)

  @classmethod
  def bgr2nv12(self, bgr):
    frame = av.VideoFrame.from_ndarray(bgr, format='bgr24')
    return frame.reformat(format='nv12').to_ndarray()

  def read_frames(self):
    while True:
      ret, frame = self.cap.read()
      if not ret:
        if self.is_video_file:
          # 视频文件播完后循环播放
          self.cap.set(cv.CAP_PROP_POS_FRAMES, 0)
          ret, frame = self.cap.read()
          if not ret:
            break
        else:
          break
      # 视频文件缩放到目标分辨率
      if self.is_video_file:
        h, w = frame.shape[:2]
        if w != self.target_W or h != self.target_H:
          frame = cv.resize(frame, (self.target_W, self.target_H))
      else:
        # 摄像头模式翻转 180 度
        frame = cv.flip(frame, -1)
      yuv = Camera.bgr2nv12(frame)
      yield yuv.data.tobytes()
    self.cap.release()
