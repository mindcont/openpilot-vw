#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
openpilot 回放调试UI界面 - 中文版
支持配置切换和多语言显示的可视化调试工具
"""

import argparse
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any

# 图像处理和显示库
import cv2
import numpy as np
import pygame

# openpilot 消息系统
import cereal.messaging as messaging
from openpilot.common.basedir import BASEDIR
from openpilot.common.transformations.camera import DEVICE_CAMERAS

# UI辅助工具
from openpilot.tools.replay.lib.ui_helpers import (
    UP, BLACK, GREEN, YELLOW, RED, WHITE,
    Calibration, get_blank_lid_overlay, init_plots,
    maybe_update_radar_points, plot_lead, plot_model,
    pygame_modules_have_loaded
)

from msgq.visionipc import VisionIpcClient, VisionStreamType

os.environ['BASEDIR'] = BASEDIR
ANGLE_SCALE = 5.0

class UIConfig:
    """UI配置管理"""

    def __init__(self):
        self.config_file = Path.home() / ".openpilot_ui_config.json"
        self.default_config = {
            "language": "zh",
            "show_fps": True,
            "show_debug_info": True,
            "plot_history": 100,
            "font_size": 15,
            "window_mode": "auto",  # auto/horizontal/vertical
            "show_alerts": True,
            "show_calibration": True,
        }
        self.config = self.load_config()
        self.texts = self.load_texts()

    def load_config(self) -> Dict[str, Any]:
        """加载配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return {**self.default_config, **config}
            except:
                pass
        return self.default_config.copy()

    def save_config(self):
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        self.save_config()

    def load_texts(self) -> Dict[str, Dict[str, str]]:
        """加载多语言文本"""
        return {
            "zh": {
                "window_title": "openpilot 调试界面",
                "enabled": "已启用",
                "disabled": "已禁用",
                "speed": "速度",
                "long_control": "纵向控制状态",
                "long_mpc": "纵向MPC源",
                "angle_offset_avg": "角度偏移(平均)",
                "angle_offset_inst": "角度偏移(瞬时)",
                "stiffness": "刚度",
                "steer_ratio": "转向比",
                "fps": "帧率",
                "help_text": "按键: H-帮助 L-切换语言 D-调试信息 F-FPS Q-退出",
                "gas": "油门",
                "brake": "刹车",
                "steering": "转向",
                "acceleration": "加速度",
                "pedals_brake": "踏板和制动",
                "steering_related": "转向相关",
                "speed_related": "速度相关",
                "accel_related": "加速度相关",
            },
            "en": {
                "window_title": "openpilot Debug UI",
                "enabled": "ENABLED",
                "disabled": "DISABLED",
                "speed": "SPEED",
                "long_control": "LONG CONTROL STATE",
                "long_mpc": "LONG MPC SOURCE",
                "angle_offset_avg": "ANGLE OFFSET (AVG)",
                "angle_offset_inst": "ANGLE OFFSET (INSTANT)",
                "stiffness": "STIFFNESS",
                "steer_ratio": "STEER RATIO",
                "fps": "FPS",
                "help_text": "Keys: H-Help L-Language D-Debug F-FPS Q-Quit",
                "gas": "Gas",
                "brake": "Brake",
                "steering": "Steering",
                "acceleration": "Acceleration",
                "pedals_brake": "Pedals & Brake",
                "steering_related": "Steering Related",
                "speed_related": "Speed Related",
                "accel_related": "Acceleration Related",
            }
        }

    def t(self, key: str) -> str:
        """获取本地化文本"""
        lang = self.get("language", "zh")
        return self.texts.get(lang, self.texts["zh"]).get(key, key)

class OpenpilotUI:
    """openpilot UI主类"""

    def __init__(self, addr="127.0.0.1"):
        self.config = UIConfig()
        self.addr = addr
        self.running = True
        self.fps_counter = 0
        self.fps_timer = 0
        self.current_fps = 0

        # 初始化pygame
        cv2.setNumThreads(1)
        pygame.init()
        pygame.font.init()
        assert pygame_modules_have_loaded()

        self.setup_display()
        self.setup_fonts()
        self.setup_messaging()
        self.setup_plotting()
        self.setup_vision()

    def setup_display(self):
        """设置显示"""
        disp_info = pygame.display.Info()
        max_height = disp_info.current_h

        window_mode = self.config.get("window_mode", "auto")
        if window_mode == "horizontal":
            hor_mode = True
        elif window_mode == "vertical":
            hor_mode = False
        else:  # auto
            hor_mode = os.getenv("HORIZONTAL") is not None
            hor_mode = True if max_height < 960+300 else hor_mode

        if hor_mode:
            self.size = (640+384+640, 960)
            self.write_x, self.write_y = 5, 680
        else:
            self.size = (640+384, 960+300)
            self.write_x, self.write_y = 645, 970

        pygame.display.set_caption(self.config.t("window_title"))
        self.screen = pygame.display.set_mode(self.size, pygame.DOUBLEBUF)

        # 创建显示表面
        self.camera_surface = pygame.surface.Surface((640, 480), 0, 24).convert()
        self.top_down_surface = pygame.surface.Surface((UP.lidar_x, UP.lidar_y), 0, 8)

    def setup_fonts(self):
        """设置字体"""
        font_size = self.config.get("font_size", 15)

        # 尝试使用支持中文的字体
        chinese_fonts = [
            "WenQuanYi Micro Hei",  # Linux
            "Noto Sans CJK SC",  # Linux
            "PingFang SC",  # macOS
            "Hiragino Sans GB",  # macOS
            "DejaVu Sans",  # 备用
            "SimHei",  # Windows
            "arial"  # 默认
        ]

        font_found = False
        for font_name in chinese_fonts:
            try:
                test_font = pygame.font.SysFont(font_name, font_size)
                if test_font:
                    self.alert1_font = pygame.font.SysFont(font_name, 30)
                    self.alert2_font = pygame.font.SysFont(font_name, 20)
                    self.info_font = pygame.font.SysFont(font_name, font_size)
                    self.help_font = pygame.font.SysFont(font_name, 12)
                    font_found = True
                    print(f"使用字体: {font_name}")
                    break
            except:
                continue

        if not font_found:
            # 如果找不到合适的字体，使用默认字体
            self.alert1_font = pygame.font.Font(None, 30)
            self.alert2_font = pygame.font.Font(None, 20)
            self.info_font = pygame.font.Font(None, font_size)
            self.help_font = pygame.font.Font(None, 12)
            print("使用默认字体")

    def setup_messaging(self):
        """设置消息订阅"""
        self.sm = messaging.SubMaster([
            'carState', 'longitudinalPlan', 'carControl', 'radarState',
            'liveCalibration', 'controlsState', 'selfdriveState',
            'liveTracks', 'modelV2', 'liveParameters', 'roadCameraState'
        ], addr=self.addr)

    def setup_plotting(self):
        """设置绘图"""
        self.name_to_arr_idx = {
            "gas": 0, "computer_gas": 1, "user_brake": 2, "computer_brake": 3,
            "v_ego": 4, "v_pid": 5, "angle_steers_des": 6, "angle_steers": 7,
            "angle_steers_k": 8, "steer_torque": 9, "v_override": 10,
            "v_cruise": 11, "a_ego": 12, "a_target": 13
        }

        history_len = self.config.get("plot_history", 100)
        self.plot_arr = np.zeros((history_len, len(self.name_to_arr_idx)))

        plot_xlims = [(0, history_len)] * 4
        plot_ylims = [(-0.1, 1.1), (-ANGLE_SCALE, ANGLE_SCALE), (0., 75.), (-3.0, 2.0)]

        # 使用本地化标签
        plot_names = [
            ["gas", "computer_gas", "user_brake", "computer_brake"],
            ["angle_steers", "angle_steers_des", "angle_steers_k", "steer_torque"],
            ["v_ego", "v_override", "v_pid", "v_cruise"],
            ["a_ego", "a_target"]
        ]

        plot_colors = [
            ["b", "b", "g", "r", "y"],
            ["b", "g", "y", "r"],
            ["b", "g", "r", "y"],
            ["b", "r"]
        ]

        plot_styles = [["-"] * len(names) for names in plot_names]

        self.draw_plots = init_plots(
            self.plot_arr, self.name_to_arr_idx, plot_xlims, plot_ylims,
            plot_names, plot_colors, plot_styles
        )

        # 初始化图像变量
        self.img = np.zeros((480, 640, 3), dtype='uint8')
        self.calibration = None
        self.lid_overlay_blank = get_blank_lid_overlay(UP)

    def safe_render_text(self, font, text, color):
        """安全渲染文本，处理编码问题"""
        try:
            # 确保文本是字符串类型
            if isinstance(text, bytes):
                text = text.decode('utf-8', errors='replace')
            elif not isinstance(text, str):
                text = str(text)

            return font.render(text, True, color)
        except UnicodeEncodeError:
            # 如果编码失败，尝试使用ASCII版本
            try:
                ascii_text = text.encode('ascii', errors='replace').decode('ascii')
                return font.render(ascii_text, True, color)
            except:
                return font.render("[Encoding Error]", True, color)
        except Exception as e:
            print(f"渲染文本错误: {e}")
            return font.render("[Render Error]", True, color)

    def setup_vision(self):
        """设置视觉系统"""
        self.vipc_client = VisionIpcClient("camerad", VisionStreamType.VISION_STREAM_ROAD, True)

    def handle_events(self):
        """处理事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self.running = False
                elif event.key == pygame.K_l:
                    # 切换语言
                    current_lang = self.config.get("language", "zh")
                    new_lang = "en" if current_lang == "zh" else "zh"
                    self.config.set("language", new_lang)
                    pygame.display.set_caption(self.config.t("window_title"))
                elif event.key == pygame.K_d:
                    # 切换调试信息
                    debug = not self.config.get("show_debug_info", True)
                    self.config.set("show_debug_info", debug)
                elif event.key == pygame.K_f:
                    # 切换FPS显示
                    fps = not self.config.get("show_fps", True)
                    self.config.set("show_fps", fps)
                elif event.key == pygame.K_h:
                    # 显示帮助（切换）
                    pass  # 帮助信息始终显示在底部

    def update_fps(self):
        """更新FPS计算"""
        import time
        current_time = time.time()
        if self.fps_timer == 0:
            self.fps_timer = current_time

        self.fps_counter += 1
        if current_time - self.fps_timer >= 1.0:
            self.current_fps = self.fps_counter
            self.fps_counter = 0
            self.fps_timer = current_time

    def process_frame(self):
        """处理视频帧"""
        if not self.vipc_client.is_connected():
            self.vipc_client.connect(True)

        yuv_img_raw = self.vipc_client.recv()
        if yuv_img_raw is None or not yuv_img_raw.data.any():
            return False

        self.sm.update(0)

        try:
            camera = DEVICE_CAMERAS[("tici", str(self.sm['roadCameraState'].sensor))]

            imgff = np.frombuffer(yuv_img_raw.data, dtype=np.uint8).reshape(
                (len(yuv_img_raw.data) // self.vipc_client.stride, self.vipc_client.stride))
            num_px = self.vipc_client.width * self.vipc_client.height
            rgb = cv2.cvtColor(imgff[:self.vipc_client.height * 3 // 2, :self.vipc_client.width],
                              cv2.COLOR_YUV2RGB_NV12)

            qcam = "QCAM" in os.environ
            bb_scale = (528 if qcam else camera.fcam.width) / 640.
            zoom_matrix = np.asarray([
                [bb_scale, 0., 0.],
                [0., bb_scale, 0.],
                [0., 0., 1.]])
            cv2.warpAffine(rgb, zoom_matrix[:2], (self.img.shape[1], self.img.shape[0]),
                          dst=self.img, flags=cv2.WARP_INVERSE_MAP)

            if self.sm.updated['liveCalibration'] and num_px:
                rpyCalib = np.asarray(self.sm['liveCalibration'].rpyCalib)
                self.calibration = Calibration(num_px, rpyCalib, camera.fcam.intrinsics,
                                             camera.fcam.width / 640.)

            return True
        except Exception as e:
            print(f"处理帧错误: {e}")
            return False

    def update_plot_data(self):
        """更新绘图数据"""
        # 获取转向角数据
        w = self.sm['controlsState'].lateralControlState.which()
        if w == 'lqrStateDEPRECATED':
            angle_steers_k = self.sm['controlsState'].lateralControlState.lqrStateDEPRECATED.steeringAngleDeg
        elif w == 'indiState':
            angle_steers_k = self.sm['controlsState'].lateralControlState.indiState.steeringAngleDeg
        else:
            angle_steers_k = np.inf

        # 滚动数据数组
        self.plot_arr[:-1] = self.plot_arr[1:]

        # 更新最新数据
        self.plot_arr[-1, self.name_to_arr_idx['angle_steers']] = self.sm['carState'].steeringAngleDeg
        self.plot_arr[-1, self.name_to_arr_idx['angle_steers_des']] = self.sm['carControl'].actuators.steeringAngleDeg
        self.plot_arr[-1, self.name_to_arr_idx['angle_steers_k']] = angle_steers_k
        self.plot_arr[-1, self.name_to_arr_idx['gas']] = self.sm['carState'].gasDEPRECATED
        self.plot_arr[-1, self.name_to_arr_idx['computer_gas']] = np.clip(self.sm['carControl'].actuators.accel/4.0, 0.0, 1.0)
        self.plot_arr[-1, self.name_to_arr_idx['user_brake']] = self.sm['carState'].brake
        self.plot_arr[-1, self.name_to_arr_idx['steer_torque']] = self.sm['carControl'].actuators.torque * ANGLE_SCALE
        self.plot_arr[-1, self.name_to_arr_idx['computer_brake']] = np.clip(-self.sm['carControl'].actuators.accel/4.0, 0.0, 1.0)
        self.plot_arr[-1, self.name_to_arr_idx['v_ego']] = self.sm['carState'].vEgo
        self.plot_arr[-1, self.name_to_arr_idx['v_cruise']] = self.sm['carState'].cruiseState.speed
        self.plot_arr[-1, self.name_to_arr_idx['a_ego']] = self.sm['carState'].aEgo

        if len(self.sm['longitudinalPlan'].accels):
            self.plot_arr[-1, self.name_to_arr_idx['a_target']] = self.sm['longitudinalPlan'].accels[0]

    def render_info_text(self):
        """渲染信息文本"""
        if not self.config.get("show_debug_info", True):
            return

        SPACING = 25
        y_offset = self.write_y

        # 系统状态信息
        lines = [
            (self.config.t("enabled"), GREEN if self.sm['selfdriveState'].enabled else RED),
            (f"{self.config.t('speed')}: {round(self.sm['carState'].vEgo, 1)} m/s", YELLOW),
            (f"{self.config.t('long_control')}: {str(self.sm['controlsState'].longControlState)}", YELLOW),
            (f"{self.config.t('long_mpc')}: {str(self.sm['longitudinalPlan'].longitudinalPlanSource)}", YELLOW),
        ]

        # 标定参数
        if self.config.get("show_calibration", True):
            lines.extend([
                None,  # 空行
                (f"{self.config.t('angle_offset_avg')}: {round(self.sm['liveParameters'].angleOffsetAverageDeg, 2)} deg", YELLOW),
                (f"{self.config.t('angle_offset_inst')}: {round(self.sm['liveParameters'].angleOffsetDeg, 2)} deg", YELLOW),
                (f"{self.config.t('stiffness')}: {round(self.sm['liveParameters'].stiffnessFactor * 100., 2)} %", YELLOW),
                (f"{self.config.t('steer_ratio')}: {round(self.sm['liveParameters'].steerRatio, 2)}", YELLOW)
            ])

        # FPS信息
        if self.config.get("show_fps", True):
            lines.append((f"{self.config.t('fps')}: {self.current_fps}", WHITE))

        # 渲染文本
        for i, line in enumerate(lines):
            if line is not None:
                text, color = line
                rendered = self.safe_render_text(self.info_font, text, color)
                self.screen.blit(rendered, (self.write_x, y_offset + i * SPACING))

    def render_help(self):
        """渲染帮助信息"""
        help_text = self.config.t("help_text")
        rendered = self.safe_render_text(self.help_font, help_text, WHITE)
        self.screen.blit(rendered, (10, self.size[1] - 20))

    def render_alerts(self):
        """渲染警报信息"""
        if not self.config.get("show_alerts", True):
            return

        alert1 = self.safe_render_text(self.alert1_font, self.sm['selfdriveState'].alertText1, RED)
        alert2 = self.safe_render_text(self.alert2_font, self.sm['selfdriveState'].alertText2, RED)
        self.screen.blit(alert1, (180, 150))
        self.screen.blit(alert2, (180, 190))

    def run(self):
        """主运行循环"""
        print(f"启动 {self.config.t('window_title')}")
        print(f"地址: {self.addr}")

        while self.running:
            self.handle_events()
            self.update_fps()

            # 清空屏幕
            self.screen.fill((64, 64, 64))

            # 处理视频帧
            if self.process_frame():
                # 创建俯视图
                lid_overlay = self.lid_overlay_blank.copy()
                top_down = self.top_down_surface, lid_overlay

                # 更新绘图数据
                self.update_plot_data()

                # 绘制AI模型输出
                if self.sm.recv_frame['modelV2']:
                    plot_model(self.sm['modelV2'], self.img, self.calibration, top_down)

                # 绘制雷达数据
                if self.sm.recv_frame['radarState']:
                    plot_lead(self.sm['radarState'], top_down)

                # 绘制雷达点
                maybe_update_radar_points(self.sm['liveTracks'].points, top_down[1])

                # 显示摄像头画面
                pygame.surfarray.blit_array(self.camera_surface, self.img.swapaxes(0, 1))
                self.screen.blit(self.camera_surface, (0, 0))

                # 显示俯视图
                pygame.surfarray.blit_array(*top_down)
                self.screen.blit(top_down[0], (640, 0))

                # 显示图表
                if self.size[0] > 1024:  # 水平模式
                    self.screen.blit(self.draw_plots(self.plot_arr), (640+384, 0))
                else:  # 垂直模式
                    self.screen.blit(self.draw_plots(self.plot_arr), (0, 600))

            # 渲染UI元素
            self.render_alerts()
            self.render_info_text()
            self.render_help()

            pygame.display.flip()

        pygame.quit()

def get_arg_parser():
    parser = argparse.ArgumentParser(
        description="openpilot 回放调试UI - 支持中文显示和配置切换",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("ip_address", nargs="?", default="127.0.0.1",
                       help="ZMQ消息服务器IP地址")
    parser.add_argument("--config", action="store_true",
                       help="显示配置选项")

    return parser

if __name__ == "__main__":
    args = get_arg_parser().parse_args()

    if args.config:
        # 显示配置信息
        config = UIConfig()
        print("=== UI配置 ===")
        for key, value in config.config.items():
            print(f"{key}: {value}")
    else:
        if args.ip_address != "127.0.0.1":
            os.environ["ZMQ"] = "1"
            messaging.reset_context()

        ui = OpenpilotUI(args.ip_address)
        try:
            ui.run()
        except KeyboardInterrupt:
            print("\n用户中断")
