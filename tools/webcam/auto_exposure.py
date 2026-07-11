"""
软件自动曝光（USB webcam 专用，方案 B）

背景：
  官方 openpilot（system/camerad/cameras/camera_qcom2.cc）在真实传感器
  (AR0231/OX03C10/OS04C10) 上跑了一套逐帧闭环自动曝光：在 ROI 内测中位灰度，
  与随场景动态调整的目标灰度比较，用两个时间常数不同的低通滤波（灰度用
  ts_grey=10s 防抖，EV 用 ts_ev=0.05s 跟手）算出期望 EV，再在增益表里搜索
  最优 (exposure_time, gain) 组合，通过 I2C 直接写传感器寄存器。

  这套算法深度绑定 comma 专用传感器的寄存器/增益表，USB webcam 没有这个接口，
  没法直接搬。本模块借鉴其"测光 ROI + 动态目标灰度 + 双时间常数平滑反馈环"的
  思路，改用 V4L2 标准控件（exposure_time_absolute/gain）实现一个简化版闭环，
  解决手动曝光值只适配单一光照场景、早中晚/室内外切换就需要重新调参的问题。
  背景讨论见 learn-docs/环境搭建与容器部署.md 曝光相关章节。

设计要点：
  - 测光成本低：每帧只对下半部分道路 ROI 做灰度均值，不做直方图
  - 控制频率低（默认 1Hz）：曝光变化在物理上是慢变量，不需要逐帧调节，
    避免和 20fps 采集主循环抢时间、也避免震荡
  - 双层调节：优先调 exposure_time（对画质影响更小），触及上下限后才调 gain
    （gain 越高噪点越明显，做兜底而非首选）
  - 平滑：一阶低通滤波（时间常数可调）防止画面明暗抽动
  - 默认关闭：AUTO_EXPOSURE=1 才启用；不开时行为与之前完全一致（仅启动时
    v4l2-ctl 设一次固定值）
  - 用 v4l2-ctl 子进程写入而非 OpenCV 的 CAP_PROP_EXPOSURE ——社区反馈该属性
    在 V4L2 backend 下经常不可靠（部分驱动会忽略或被 auto_exposure 覆盖）
"""

import os
import subprocess
import threading
import time

import cv2 as cv
import numpy as np


class AutoExposureController:
  """单个摄像头的软件自动曝光闭环控制器。

  用法：在采集循环里每帧调用 update(frame)（内部会自行按频率降采样），
  独立于渲染/发布路径，不阻塞主循环。
  """

  # 安全范围：exposure 单位 1/10000s；450 对应 45ms，20fps(50ms 周期)内留余量。
  EXPOSURE_MIN = 5
  EXPOSURE_MAX = 450
  GAIN_MIN = 0
  GAIN_MAX = 128

  # 目标灰度（0~255 的均值），室外/室内经验值都落在这个区间；
  # 参考已验证的手动曝光效果：exposure=50,gain=40（室内清晰）画面均值 ~110-130。
  TARGET_GREY = float(os.getenv("AE_TARGET_GREY", "120"))

  # 控制频率：曝光是慢变量，不需要逐帧调节
  CONTROL_INTERVAL_SEC = float(os.getenv("AE_INTERVAL", "1.0"))

  # 一阶低通滤波系数（0~1，越大跟手越快、越容易抽动）
  SMOOTH_ALPHA = float(os.getenv("AE_SMOOTH_ALPHA", "0.3"))

  # 灰度死区：测量值与目标差小于此比例时不调节，避免在目标附近来回震荡
  DEADBAND_FRAC = 0.06

  def __init__(self, device_path: str, init_exposure: int, init_gain: int, label: str = ""):
    self.device_path = device_path
    self.label = label or device_path
    self.exposure = float(np.clip(init_exposure, self.EXPOSURE_MIN, self.EXPOSURE_MAX))
    self.gain = float(np.clip(init_gain, self.GAIN_MIN, self.GAIN_MAX))
    self._smoothed_grey: float | None = None
    self._last_apply_t = 0.0
    self._lock = threading.Lock()
    self._apply(self.exposure, self.gain, force=True)

  @staticmethod
  def _measure_grey(frame_bgr) -> float:
    """对画面下半部分（道路 ROI，排除天空/引擎盖边缘）取灰度均值。"""
    h, w = frame_bgr.shape[:2]
    roi = frame_bgr[int(h * 0.35):int(h * 0.85), int(w * 0.1):int(w * 0.9)]
    gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)
    return float(np.mean(gray))

  def _apply(self, exposure: float, gain: float, force: bool = False):
    exposure_i = int(round(np.clip(exposure, self.EXPOSURE_MIN, self.EXPOSURE_MAX)))
    gain_i = int(round(np.clip(gain, self.GAIN_MIN, self.GAIN_MAX)))
    if not force and exposure_i == int(round(self.exposure)) and gain_i == int(round(self.gain)):
      return
    try:
      subprocess.run(
        ["v4l2-ctl", "-d", self.device_path,
         "--set-ctrl", f"exposure_time_absolute={exposure_i}",
         "--set-ctrl", f"gain={gain_i}"],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0,
      )
    except (OSError, subprocess.TimeoutExpired) as e:
      print(f"[auto_exposure][{self.label}] v4l2-ctl 调用失败: {e}")
    self.exposure = exposure_i
    self.gain = gain_i

  def update(self, frame_bgr):
    """每帧调用；内部按 CONTROL_INTERVAL_SEC 降频，其余帧直接返回。"""
    now = time.monotonic()
    if now - self._last_apply_t < self.CONTROL_INTERVAL_SEC:
      return
    self._last_apply_t = now

    grey = self._measure_grey(frame_bgr)
    self._smoothed_grey = grey if self._smoothed_grey is None else (
      (1 - self.SMOOTH_ALPHA) * self._smoothed_grey + self.SMOOTH_ALPHA * grey
    )

    error = (self.TARGET_GREY - self._smoothed_grey) / self.TARGET_GREY
    if abs(error) < self.DEADBAND_FRAC:
      return  # 死区内不调节，避免震荡

    with self._lock:
      # 曝光时间与亮度大致线性，用比例调节；用当前设定值而非测量值做基准更稳定
      new_exposure = self.exposure * (1.0 + error)
      new_gain = self.gain

      if new_exposure > self.EXPOSURE_MAX:
        # 曝光时间到顶，剩余差额转给增益承担
        overflow_ratio = new_exposure / self.EXPOSURE_MAX
        new_exposure = self.EXPOSURE_MAX
        new_gain = self.gain * overflow_ratio
      elif new_exposure < self.EXPOSURE_MIN:
        # 曝光时间到底（画面过亮），优先降增益
        new_gain = self.gain * (new_exposure / self.EXPOSURE_MIN) if self.EXPOSURE_MIN > 0 else self.gain
        new_exposure = self.EXPOSURE_MIN

      self._apply(new_exposure, new_gain)

  def status(self) -> str:
    grey = f"{self._smoothed_grey:.1f}" if self._smoothed_grey is not None else "?"
    return f"{self.label}: exposure={int(self.exposure)} gain={int(self.gain)} grey={grey}(target={self.TARGET_GREY:.0f})"
