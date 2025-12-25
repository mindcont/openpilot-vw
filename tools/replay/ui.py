#!/usr/bin/env python3
"""
openpilot 回放调试UI界面

功能说明：
- 实时显示openpilot系统的运行状态和数据
- 可视化车辆控制参数、传感器数据和AI模型输出
- 支持本地回放和远程连接模式
- 提供多种图表和可视化元素帮助调试

主要显示内容：
1. 摄像头画面 + AI模型预测结果（车道线、前车等）
2. 俯视图显示雷达点和轨迹
3. 实时数据图表（速度、转向、加速度等）
4. 系统状态信息（使能状态、控制模式等）
5. 标定参数（角度偏移、转向比等）
"""

import argparse
import os
import sys

# 图像处理和显示库
import cv2          # OpenCV - 图像处理
import numpy as np  # NumPy - 数值计算
import pygame       # Pygame - 图形界面显示

# openpilot 消息系统
import cereal.messaging as messaging
from openpilot.common.basedir import BASEDIR
from openpilot.common.transformations.camera import DEVICE_CAMERAS

# UI辅助工具和可视化函数
from openpilot.tools.replay.lib.ui_helpers import (
    UP,                          # UI参数配置
    BLACK, GREEN, YELLOW,        # 颜色常量
    Calibration,                 # 相机标定类
    get_blank_lid_overlay,       # 获取空白覆盖层
    init_plots,                  # 初始化图表
    maybe_update_radar_points,   # 更新雷达点
    plot_lead,                   # 绘制前车
    plot_model,                  # 绘制AI模型输出
    pygame_modules_have_loaded   # 检查pygame模块加载
)

# VisionIPC - 高效的图像数据传输
from msgq.visionipc import VisionIpcClient, VisionStreamType

# 设置基础目录环境变量
os.environ['BASEDIR'] = BASEDIR

# 角度缩放因子，用于显示转向力矩
ANGLE_SCALE = 5.0

def ui_thread(addr):
  """
  UI主线程函数
  
  Args:
      addr: ZMQ消息服务器地址，用于接收openpilot数据
  
  功能：
  - 初始化pygame显示系统
  - 创建各种可视化界面元素
  - 持续接收和显示openpilot数据
  - 处理用户交互事件
  """
  # 设置OpenCV使用单线程，避免与pygame冲突
  cv2.setNumThreads(1)
  
  # 初始化pygame显示和字体系统
  pygame.init()
  pygame.font.init()
  
  # 确保pygame模块正确加载
  assert pygame_modules_have_loaded()

  # 获取显示器信息，用于自适应布局
  disp_info = pygame.display.Info()
  max_height = disp_info.current_h

  # 确定显示模式：水平布局 vs 垂直布局
  # 可通过环境变量HORIZONTAL强制使用水平模式
  hor_mode = os.getenv("HORIZONTAL") is not None
  # 如果屏幕高度不足，自动切换到水平模式
  hor_mode = True if max_height < 960+300 else hor_mode

  if hor_mode:
    # 水平布局：摄像头(640) + 俯视图(384) + 图表(640) = 1664x960
    size = (640+384+640, 960)
    write_x = 5    # 文字信息显示位置X
    write_y = 680  # 文字信息显示位置Y
  else:
    # 垂直布局：摄像头+俯视图(1024) x (摄像头+图表)(1260)
    size = (640+384, 960+300)
    write_x = 645  # 文字信息显示位置X
    write_y = 970  # 文字信息显示位置Y

  # 创建pygame显示窗口
  pygame.display.set_caption("openpilot debug UI")
  screen = pygame.display.set_mode(size, pygame.DOUBLEBUF)  # 双缓冲提高性能

  # 创建不同大小的字体，用于显示不同类型的信息
  alert1_font = pygame.font.SysFont("arial", 30)  # 主要警告信息字体
  alert2_font = pygame.font.SysFont("arial", 20)  # 次要警告信息字体
  info_font = pygame.font.SysFont("arial", 15)    # 状态信息字体

  # 创建显示表面
  # 摄像头画面显示表面 (640x480, 24位色深)
  camera_surface = pygame.surface.Surface((640, 480), 0, 24).convert()
  # 俯视图显示表面 (雷达和轨迹显示)
  top_down_surface = pygame.surface.Surface((UP.lidar_x, UP.lidar_y), 0, 8)

  # 创建消息订阅器，接收openpilot各模块的数据
  # 订阅的消息类型包括：
  # - carState: 车辆状态（速度、转向角、踏板等）
  # - longitudinalPlan: 纵向规划（加速度计划）
  # - carControl: 车辆控制指令
  # - radarState: 雷达状态和前车信息
  # - liveCalibration: 实时相机标定
  # - controlsState: 控制系统状态
  # - selfdriveState: 自动驾驶系统状态
  # - liveTracks: 实时目标跟踪
  # - modelV2: AI模型输出（车道线、轨迹预测等）
  # - liveParameters: 实时参数（转向比、角度偏移等）
  # - roadCameraState: 道路摄像头状态
  sm = messaging.SubMaster(['carState', 'longitudinalPlan', 'carControl', 'radarState', 'liveCalibration', 'controlsState',
                            'selfdriveState', 'liveTracks', 'modelV2', 'liveParameters', 'roadCameraState'], addr=addr)

  # 初始化图像相关变量
  img = np.zeros((480, 640, 3), dtype='uint8')  # RGB图像缓冲区
  imgff = None                                   # 原始图像数据
  num_px = 0                                     # 像素总数
  calibration = None                             # 相机标定对象

  # 获取空白的俯视图覆盖层模板
  lid_overlay_blank = get_blank_lid_overlay(UP)

  # 图表数据配置
  # 将各种数据名称映射到数组索引，用于实时绘图
  name_to_arr_idx = { 
      "gas": 0,                    # 油门踏板位置
      "computer_gas": 1,           # 计算机油门指令
      "user_brake": 2,             # 用户刹车踏板
      "computer_brake": 3,         # 计算机刹车指令
      "v_ego": 4,                  # 车辆实际速度
      "v_pid": 5,                  # PID控制目标速度
      "angle_steers_des": 6,       # 期望转向角
      "angle_steers": 7,           # 实际转向角
      "angle_steers_k": 8,         # 卡尔曼滤波转向角
      "steer_torque": 9,           # 转向力矩
      "v_override": 10,            # 用户接管速度
      "v_cruise": 11,              # 巡航设定速度
      "a_ego": 12,                 # 车辆实际加速度
      "a_target": 13               # 目标加速度
  }

  # 创建数据存储数组，保存最近100个时间点的数据
  plot_arr = np.zeros((100, len(name_to_arr_idx.values())))

  # 图表配置：X轴和Y轴范围
  plot_xlims = [(0, plot_arr.shape[0]), (0, plot_arr.shape[0]), (0, plot_arr.shape[0]), (0, plot_arr.shape[0])]
  plot_ylims = [(-0.1, 1.1),                    # 踏板位置范围 0-1
                (-ANGLE_SCALE, ANGLE_SCALE),     # 转向角度范围
                (0., 75.),                       # 速度范围 0-75 m/s
                (-3.0, 2.0)]                     # 加速度范围 -3到2 m/s²
  
  # 每个子图包含的数据系列
  plot_names = [
      ["gas", "computer_gas", "user_brake", "computer_brake"],           # 踏板和制动
      ["angle_steers", "angle_steers_des", "angle_steers_k", "steer_torque"], # 转向相关
      ["v_ego", "v_override", "v_pid", "v_cruise"],                      # 速度相关
      ["a_ego", "a_target"]                                               # 加速度相关
  ]
  
  # 每条线的颜色配置
  plot_colors = [
      ["b", "b", "g", "r", "y"],  # 蓝、蓝、绿、红、黄
      ["b", "g", "y", "r"],       # 蓝、绿、黄、红
      ["b", "g", "r", "y"],       # 蓝、绿、红、黄
      ["b", "r"]                  # 蓝、红
  ]
  
  # 每条线的样式配置（都是实线）
  plot_styles = [
      ["-", "-", "-", "-", "-"],
      ["-", "-", "-", "-"],
      ["-", "-", "-", "-"],
      ["-", "-"]
  ]

  # 初始化图表绘制函数
  draw_plots = init_plots(plot_arr, name_to_arr_idx, plot_xlims, plot_ylims, plot_names, plot_colors, plot_styles)

  # 创建VisionIPC客户端，用于接收摄像头图像数据
  # 连接到camerad进程，接收道路摄像头流，启用缓冲
  vipc_client = VisionIpcClient("camerad", VisionStreamType.VISION_STREAM_ROAD, True)
  # 主显示循环
  while True:
    # 处理pygame事件（如窗口关闭）
    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        pygame.quit()
        sys.exit()

    # 清空屏幕，填充深灰色背景
    screen.fill((64, 64, 64))
    
    # 创建俯视图覆盖层的副本（用于绘制雷达点等）
    lid_overlay = lid_overlay_blank.copy()
    top_down = top_down_surface, lid_overlay

    # ***** frame *****
    if not vipc_client.is_connected():
      vipc_client.connect(True)

    yuv_img_raw = vipc_client.recv()
    if yuv_img_raw is None or not yuv_img_raw.data.any():
      continue

    sm.update(0)

    camera = DEVICE_CAMERAS[("tici", str(sm['roadCameraState'].sensor))]

    imgff = np.frombuffer(yuv_img_raw.data, dtype=np.uint8).reshape((len(yuv_img_raw.data) // vipc_client.stride, vipc_client.stride))
    num_px = vipc_client.width * vipc_client.height
    rgb = cv2.cvtColor(imgff[:vipc_client.height * 3 // 2, :vipc_client.width], cv2.COLOR_YUV2RGB_NV12)

    qcam = "QCAM" in os.environ
    bb_scale = (528 if qcam else camera.fcam.width) / 640.
    calib_scale = camera.fcam.width / 640.
    zoom_matrix = np.asarray([
        [bb_scale, 0., 0.],
        [0., bb_scale, 0.],
        [0., 0., 1.]])
    cv2.warpAffine(rgb, zoom_matrix[:2], (img.shape[1], img.shape[0]), dst=img, flags=cv2.WARP_INVERSE_MAP)

    intrinsic_matrix = camera.fcam.intrinsics

    w = sm['controlsState'].lateralControlState.which()
    if w == 'lqrStateDEPRECATED':
      angle_steers_k = sm['controlsState'].lateralControlState.lqrStateDEPRECATED.steeringAngleDeg
    elif w == 'indiState':
      angle_steers_k = sm['controlsState'].lateralControlState.indiState.steeringAngleDeg
    else:
      angle_steers_k = np.inf

    plot_arr[:-1] = plot_arr[1:]
    plot_arr[-1, name_to_arr_idx['angle_steers']] = sm['carState'].steeringAngleDeg
    plot_arr[-1, name_to_arr_idx['angle_steers_des']] = sm['carControl'].actuators.steeringAngleDeg
    plot_arr[-1, name_to_arr_idx['angle_steers_k']] = angle_steers_k
    plot_arr[-1, name_to_arr_idx['gas']] = sm['carState'].gasDEPRECATED
    # TODO gas is deprecated
    plot_arr[-1, name_to_arr_idx['computer_gas']] = np.clip(sm['carControl'].actuators.accel/4.0, 0.0, 1.0)
    plot_arr[-1, name_to_arr_idx['user_brake']] = sm['carState'].brake
    plot_arr[-1, name_to_arr_idx['steer_torque']] = sm['carControl'].actuators.torque * ANGLE_SCALE
    # TODO brake is deprecated
    plot_arr[-1, name_to_arr_idx['computer_brake']] = np.clip(-sm['carControl'].actuators.accel/4.0, 0.0, 1.0)
    plot_arr[-1, name_to_arr_idx['v_ego']] = sm['carState'].vEgo
    plot_arr[-1, name_to_arr_idx['v_cruise']] = sm['carState'].cruiseState.speed
    plot_arr[-1, name_to_arr_idx['a_ego']] = sm['carState'].aEgo

    if len(sm['longitudinalPlan'].accels):
      plot_arr[-1, name_to_arr_idx['a_target']] = sm['longitudinalPlan'].accels[0]

    if sm.recv_frame['modelV2']:
      plot_model(sm['modelV2'], img, calibration, top_down)

    if sm.recv_frame['radarState']:
      plot_lead(sm['radarState'], top_down)

    # draw all radar points
    maybe_update_radar_points(sm['liveTracks'].points, top_down[1])

    if sm.updated['liveCalibration'] and num_px:
      rpyCalib = np.asarray(sm['liveCalibration'].rpyCalib)
      calibration = Calibration(num_px, rpyCalib, intrinsic_matrix, calib_scale)

    # *** blits ***
    pygame.surfarray.blit_array(camera_surface, img.swapaxes(0, 1))
    screen.blit(camera_surface, (0, 0))

    # display alerts
    alert_line1 = alert1_font.render(sm['selfdriveState'].alertText1, True, (255, 0, 0))
    alert_line2 = alert2_font.render(sm['selfdriveState'].alertText2, True, (255, 0, 0))
    screen.blit(alert_line1, (180, 150))
    screen.blit(alert_line2, (180, 190))

    if hor_mode:
      screen.blit(draw_plots(plot_arr), (640+384, 0))
    else:
      screen.blit(draw_plots(plot_arr), (0, 600))

    pygame.surfarray.blit_array(*top_down)
    screen.blit(top_down[0], (640, 0))

    SPACING = 25

    lines = [
      info_font.render("ENABLED", True, GREEN if sm['selfdriveState'].enabled else BLACK),
      info_font.render("SPEED: " + str(round(sm['carState'].vEgo, 1)) + " m/s", True, YELLOW),
      info_font.render("LONG CONTROL STATE: " + str(sm['controlsState'].longControlState), True, YELLOW),
      info_font.render("LONG MPC SOURCE: " + str(sm['longitudinalPlan'].longitudinalPlanSource), True, YELLOW),
      None,
      info_font.render("ANGLE OFFSET (AVG): " + str(round(sm['liveParameters'].angleOffsetAverageDeg, 2)) + " deg", True, YELLOW),
      info_font.render("ANGLE OFFSET (INSTANT): " + str(round(sm['liveParameters'].angleOffsetDeg, 2)) + " deg", True, YELLOW),
      info_font.render("STIFFNESS: " + str(round(sm['liveParameters'].stiffnessFactor * 100., 2)) + " %", True, YELLOW),
      info_font.render("STEER RATIO: " + str(round(sm['liveParameters'].steerRatio, 2)), True, YELLOW)
    ]

    for i, line in enumerate(lines):
      if line is not None:
        screen.blit(line, (write_x, write_y + i * SPACING))

    # this takes time...vsync or something
    pygame.display.flip()

def get_arg_parser():
  parser = argparse.ArgumentParser(
    description="Show replay data in a UI.",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument("ip_address", nargs="?", default="127.0.0.1",
                      help="The ip address on which to receive zmq messages.")

  parser.add_argument("--frame-address", default=None,
                      help="The frame address (fully qualified ZMQ endpoint for frames) on which to receive zmq messages.")
  return parser

if __name__ == "__main__":
  args = get_arg_parser().parse_args(sys.argv[1:])

  if args.ip_address != "127.0.0.1":
    os.environ["ZMQ"] = "1"
    messaging.reset_context()

  ui_thread(args.ip_address)
