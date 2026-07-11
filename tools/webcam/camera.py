import av
import os
import cv2 as cv


class Camera:
  def __init__(self, cam_type_state, stream_type, camera_id, target_size=(1928, 1208)):
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

    # 软件自动曝光（方案 B，默认关闭）：AUTO_EXPOSURE=1 时对实体摄像头启用。
    # 视频文件没有曝光可调，跳过。详见 auto_exposure.py 顶部说明。
    self.auto_exposure = None
    if not self.is_video_file and os.getenv("AUTO_EXPOSURE") == "1":
      from openpilot.tools.webcam.auto_exposure import AutoExposureController
      # camera_id 此时是 int（纯数字设备号）或 str（已是 /dev/videoN 完整路径）
      dev = camera_id if isinstance(camera_id, str) else f"/dev/video{camera_id}"
      is_wide = "wide" in str(cam_type_state).lower()
      prefix = "WIDE_CAM" if is_wide else "ROAD_CAM"
      init_exposure = int(os.getenv(f"{prefix}_EXPOSURE", "50"))
      init_gain = int(os.getenv(f"{prefix}_GAIN", "40"))
      self.auto_exposure = AutoExposureController(dev, init_exposure, init_gain, label=cam_type_state)
      print(f"[camera] {cam_type_state} 软件自动曝光已启用: {dev} 初始 exposure={init_exposure} gain={init_gain}")

    # 目标分辨率 — 必须与 DEVICE_CAMERAS 中对应摄像头的 intrinsics 分辨率一致
    # road(fcam) 与 wide(ecam) 可能不同，因此按摄像头独立传入
    self.target_W, self.target_H = target_size

    if not self.is_video_file:
      self.cap.set(cv.CAP_PROP_FRAME_WIDTH, float(self.target_W))
      self.cap.set(cv.CAP_PROP_FRAME_HEIGHT, float(self.target_H))
      self.cap.set(cv.CAP_PROP_FPS, 25.0)

    # read_frames() 无条件将每一帧 resize 到 target_W/target_H（见下方），
    # 所以对外暴露的分辨率必须始终是 target_W/target_H，不能用摄像头协商后的
    # 实际分辨率（cap.get 返回值），否则 camerad.py 按此值分配的 VisionIPC buffer
    # 大小会和实际产出的帧数据大小不一致，触发 `assert buf.len == len(data)` 崩溃。
    # 实测：USB 摄像头请求 1928x1208 时驱动协商到 1920x1080（设备不支持精确尺寸），
    # 此前用协商值导致 buffer=1920x1080 而数据=1928x1208，webcamerad 静默崩溃退出。
    self.W = self.target_W
    self.H = self.target_H

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
      # 缩放到目标分辨率（视频文件或摄像头实际输出与目标不一致时）
      h, w = frame.shape[:2]
      if w != self.target_W or h != self.target_H:
        frame = cv.resize(frame, (self.target_W, self.target_H))
      # 实体摄像头按需翻转 180 度（安装方向），视频文件不翻转
      if not self.is_video_file and os.getenv("CAM_FLIP", "1") == "1":
        frame = cv.flip(frame, -1)
      # 软件自动曝光：用翻转后的帧测光，保证 ROI（画面下半部分=道路）与实际
      # 显示方向一致；内部按低频率降采样，不会拖慢这里的采集主循环。
      if self.auto_exposure is not None:
        self.auto_exposure.update(frame)
      yuv = Camera.bgr2nv12(frame)
      yield yuv.data.tobytes()
    self.cap.release()
