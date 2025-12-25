#!/usr/bin/env python3
"""
openpilot 数据流查看器
提供简单的UI界面选择和查看replay中的各类数据流

carState: 车辆状态（速度、加速度、转向角等）
carControl: 控制指令（油门、刹车、转向等）
controlsState: 控制系统状态
radarState: 雷达数据（前车距离、相对速度等）
modelV2: AI模型输出（轨迹预测等）
liveParameters: 实时参数（转向比、角度偏移等）
longitudinalPlan: 纵向规划数据
deviceState: 设备状态（温度、内存使用等）
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import threading
import time
from collections import deque

import cereal.messaging as messaging
from openpilot.tools.lib.logreader import LogReader


class DataViewer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("openpilot 数据流查看器")
        self.root.geometry("1200x800")

        # 数据存储
        self.log_reader = None
        self.current_data = {}
        self.data_buffer = deque(maxlen=1000)
        self.is_playing = False

        # 可用的数据流类型 - 完整版本
        self.available_streams = {
            # 车辆状态
            'carState': {
                '车辆速度': 'vEgo',
                '车辆加速度': 'aEgo',
                '转向角度': 'steeringAngleDeg',
                '刹车踏板': 'brake',
                '油门踏板': 'gas',
                '车轮速度': 'wheelSpeeds',
                '方向盘力矩': 'steeringTorque',
                '档位': 'gearShifter',
                '手刹': 'handbrakePressed',
                '转向灯': 'leftBlinker'
            },
            # 控制指令
            'carControl': {
                '期望加速度': 'actuators.accel',
                '期望转向角': 'actuators.steeringAngleDeg',
                '转向力矩': 'actuators.torque',
                '长按喇叭': 'hudControl.visualAlert'
            },
            # 控制系统状态
            'controlsState': {
                '系统启用': 'enabled',
                '系统激活': 'active',
                '纵向控制状态': 'longControlState',
                '横向控制状态': 'lateralControlState',
                '警报状态': 'alertStatus'
            },
            # 雷达状态
            'radarState': {
                '前车距离': 'leadOne.dRel',
                '前车相对速度': 'leadOne.vRel',
                '前车加速度': 'leadOne.aRel',
                '前车方位角': 'leadOne.yRel'
            },
            # AI模型输出
            'modelV2': {
                '轨迹X坐标': 'position.x',
                '轨迹Y坐标': 'position.y',
                '轨迹速度X': 'velocity.x',
                '轨迹速度Y': 'velocity.y',
                '车道线置信度': 'laneLines'
            },
            # 实时参数
            'liveParameters': {
                '转向比': 'steerRatio',
                '角度偏移': 'angleOffsetDeg',
                '刚度系数': 'stiffnessFactor'
            },
            # 纵向规划
            'longitudinalPlan': {
                '规划速度': 'speeds',
                '规划加速度': 'accels',
                '目标速度': 'vTarget'
            },
            # 设备状态
            'deviceState': {
                'CPU温度': 'cpuTempC',
                '内存使用率': 'memoryUsagePercent',
                '存储空间': 'freeSpacePercent',
                '电池电量': 'batteryPercent',
                '充电状态': 'chargingError'
            },
            # GPS定位
            'gpsLocationExternal': {
                '纬度': 'latitude',
                '经度': 'longitude',
                '海拔': 'altitude',
                '速度': 'speed',
                '航向': 'bearing'
            },
            # 传感器数据
            'gyroscope': {
                'X轴角速度': 'gyro.v[0]',
                'Y轴角速度': 'gyro.v[1]',
                'Z轴角速度': 'gyro.v[2]'
            },
            'accelerometer': {
                'X轴加速度': 'accel.v[0]',
                'Y轴加速度': 'accel.v[1]',
                'Z轴加速度': 'accel.v[2]'
            },
            # 摄像头状态
            'roadCameraState': {
                '帧ID': 'frameId',
                '时间戳': 'timestampSof',
                '曝光时间': 'exposureTime'
            },
            # 驾驶员监控
            'driverStateV2': {
                '驾驶员注意力': 'attentionScore',
                '面部朝向': 'faceOrientation',
                '眼睛睁开度': 'leftEyeProb'
            },
            # 实时跟踪
            'liveTracks': {
                '跟踪点数': 'points'
            },
            # 标定数据
            'liveCalibration': {
                '俯仰角': 'rpyCalib[0]',
                '偏航角': 'rpyCalib[1]',
                '横滚角': 'rpyCalib[2]'
            }
        }

        self.setup_ui()

    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", width=300)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        control_frame.pack_propagate(False)

        # 文件选择
        ttk.Label(control_frame, text="选择日志文件:").pack(pady=5)
        file_frame = ttk.Frame(control_frame)
        file_frame.pack(fill=tk.X, padx=5)

        self.file_path = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_path, width=25).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="浏览", command=self.browse_file, width=8).pack(side=tk.RIGHT)

        # 数据流选择
        ttk.Label(control_frame, text="选择数据流:").pack(pady=(20, 5))

        # 创建树形视图显示可用数据流
        self.tree = ttk.Treeview(control_frame, height=15)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5)

        # 填充数据流树 - 中文显示
        for stream, fields in self.available_streams.items():
            parent = self.tree.insert('', 'end', text=stream, open=True)
            for chinese_name, field_path in fields.items():
                self.tree.insert(parent, 'end', text=chinese_name, values=(stream, field_path))

        # 播放控制
        control_buttons = ttk.Frame(control_frame)
        control_buttons.pack(fill=tk.X, pady=10, padx=5)

        self.play_button = ttk.Button(control_buttons, text="播放", command=self.toggle_playback)
        self.play_button.pack(side=tk.LEFT, padx=2)

        ttk.Button(control_buttons, text="重置", command=self.reset_data).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_buttons, text="添加图表", command=self.add_plot).pack(side=tk.LEFT, padx=2)

        # 右侧图表区域
        self.plot_frame = ttk.LabelFrame(main_frame, text="数据图表")
        self.plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 创建matplotlib图表
        self.fig, self.ax = plt.subplots(figsize=(8, 6))
        self.canvas = FigureCanvasTkAgg(self.fig, self.plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def browse_file(self):
        """浏览并选择日志文件"""
        filename = filedialog.askopenfilename(
            title="选择openpilot日志文件",
            filetypes=[("日志文件", "*.rlog *.bz2"), ("所有文件", "*.*")]
        )
        if filename:
            self.file_path.set(filename)
            self.load_log_file(filename)

    def load_log_file(self, filename):
        """加载日志文件"""
        try:
            self.status_var.set("正在加载日志文件...")
            self.log_reader = LogReader(filename)
            self.status_var.set(f"已加载: {filename}")
            messagebox.showinfo("成功", "日志文件加载成功！")
        except Exception as e:
            messagebox.showerror("错误", f"加载日志文件失败: {str(e)}")
            self.status_var.set("加载失败")

    def add_plot(self):
        """添加选中的数据到图表"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要显示的数据流")
            return

        if not self.log_reader:
            messagebox.showwarning("警告", "请先加载日志文件")
            return

        # 获取选中的数据流和字段
        item = self.tree.item(selection[0])
        if not item['values']:  # 选中的是父节点
            messagebox.showwarning("警告", "请选择具体的数据字段")
            return

        stream_name, field_name = item['values']
        self.plot_data_stream(stream_name, field_name)

    def plot_data_stream(self, stream_name, field_name):
        """绘制指定数据流"""
        try:
            self.status_var.set(f"正在提取数据: {stream_name}.{field_name}")

            # 提取数据
            timestamps = []
            values = []

            for msg in self.log_reader:
                if msg.which() == stream_name:
                    try:
                        # 获取时间戳
                        timestamps.append(msg.logMonoTime / 1e9)  # 转换为秒

                        # 获取字段值
                        obj = getattr(msg, stream_name)
                        value = self.get_nested_attr(obj, field_name)
                        values.append(float(value) if value is not None else 0)

                    except Exception as e:
                        continue  # 跳过无法解析的消息

            if not timestamps:
                messagebox.showwarning("警告", f"未找到 {stream_name}.{field_name} 的数据")
                return

            # 绘制图表
            self.ax.clear()
            self.ax.plot(timestamps, values, label=f"{stream_name}.{field_name}")
            self.ax.set_xlabel("时间 (秒)")
            self.ax.set_ylabel("值")
            self.ax.set_title(f"数据流: {stream_name}.{field_name}")
            self.ax.legend()
            self.ax.grid(True)

            self.canvas.draw()
            self.status_var.set(f"已绘制: {stream_name}.{field_name} ({len(values)} 个数据点)")

        except Exception as e:
            messagebox.showerror("错误", f"绘制数据失败: {str(e)}")
            self.status_var.set("绘制失败")

    def get_nested_attr(self, obj, attr_path):
        """获取嵌套属性值"""
        attrs = attr_path.split('.')
        for attr in attrs:
            if hasattr(obj, attr):
                obj = getattr(obj, attr)
            else:
                return None
        return obj

    def toggle_playback(self):
        """切换播放状态"""
        if not self.log_reader:
            messagebox.showwarning("警告", "请先加载日志文件")
            return

        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_button.config(text="暂停")
            threading.Thread(target=self.playback_thread, daemon=True).start()
        else:
            self.play_button.config(text="播放")

    def playback_thread(self):
        """播放线程"""
        selection = self.tree.selection()
        if not selection or not self.tree.item(selection[0])['values']:
            return

        stream_name, field_name = self.tree.item(selection[0])['values']

        timestamps = []
        values = []

        for msg in self.log_reader:
            if not self.is_playing:
                break

            if msg.which() == stream_name:
                try:
                    timestamp = msg.logMonoTime / 1e9
                    obj = getattr(msg, stream_name)
                    value = self.get_nested_attr(obj, field_name)

                    if value is not None:
                        timestamps.append(timestamp)
                        values.append(float(value))

                        # 实时更新图表
                        if len(timestamps) > 1:
                            self.ax.clear()
                            self.ax.plot(timestamps, values, 'b-')
                            self.ax.set_xlabel("时间 (秒)")
                            self.ax.set_ylabel("值")
                            self.ax.set_title(f"实时数据: {stream_name}.{field_name}")
                            self.ax.grid(True)
                            self.canvas.draw()

                        time.sleep(0.05)  # 控制播放速度

                except Exception:
                    continue

        self.is_playing = False
        self.play_button.config(text="播放")

    def reset_data(self):
        """重置数据和图表"""
        self.ax.clear()
        self.ax.set_title("数据图表")
        self.canvas.draw()
        self.data_buffer.clear()
        self.status_var.set("已重置")

    def run(self):
        """运行应用"""
        self.root.mainloop()


if __name__ == "__main__":
    app = DataViewer()
    app.run()
