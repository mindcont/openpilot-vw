#!/usr/bin/env python
"""
网络摄像头图像变换可视化工具

该模块用于将网络摄像头的图像变换到 EON 设备的相机视角，
通过透视变换实现不同相机内参之间的图像转换。
主要用于调试和可视化网络摄像头与 openpilot 系统的兼容性。
"""

import numpy as np

# 从 common.transformations/camera.py 复制的相机参数

# EON 后置相机焦距 (像素)
eon_focal_length = 910.0
# EON 前置相机焦距 (像素)
eon_dcam_focal_length = 860.0

# 网络摄像头焦距 (像素)，经过缩放调整
webcam_focal_length = -908.0/1.5

# EON 后置相机内参矩阵
# 格式: [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]
# fx, fy: 焦距 (像素)
# cx, cy: 主点坐标 (像素)
eon_intrinsics = np.array([
  [eon_focal_length,   0.,   1164/2.],  # fx=910, cx=582
  [  0.,  eon_focal_length,  874/2.],   # fy=910, cy=437
  [  0.,    0.,     1.]])               # 齐次坐标

# EON 前置相机内参矩阵
eon_dcam_intrinsics = np.array([
  [eon_dcam_focal_length,   0,   1152/2.],  # fx=860, cx=576
  [  0,  eon_dcam_focal_length,  864/2.],   # fy=860, cy=432
  [  0,    0,     1]])                      # 齐次坐标

# 网络摄像头内参矩阵 (经过 1.5 倍缩放)
webcam_intrinsics = np.array([
  [webcam_focal_length,   0.,   1280/2/1.5],  # fx=-605.3, cx=426.7
  [  0.,  webcam_focal_length,  720/2/1.5],   # fy=-605.3, cy=240
  [  0.,    0.,     1.]])                     # 齐次坐标

if __name__ == "__main__":
  """
  主程序：实时显示网络摄像头图像的透视变换效果

  功能：
  1. 计算从网络摄像头到 EON 相机的变换矩阵
  2. 实时捕获网络摄像头图像
  3. 应用透视变换并显示结果
  """
  import cv2  # pylint: disable=import-error

  # 计算变换矩阵
  # 变换矩阵 = 目标内参 × 源内参的逆矩阵
  trans_webcam_to_eon_rear = np.dot(eon_intrinsics, np.linalg.inv(webcam_intrinsics))
  trans_webcam_to_eon_front = np.dot(eon_dcam_intrinsics, np.linalg.inv(webcam_intrinsics))

  print("网络摄像头到 EON 后置相机的变换矩阵:")
  print(trans_webcam_to_eon_rear)
  print("网络摄像头到 EON 前置相机的变换矩阵:")
  print(trans_webcam_to_eon_front)

  # 初始化摄像头 (设备索引 1)
  cap = cv2.VideoCapture(1)
  # 设置摄像头分辨率
  cap.set(cv2.CAP_PROP_FRAME_WIDTH, 853)   # 宽度
  cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)  # 高度

  # 主循环：实时图像处理和显示
  while (True):
    ret, img = cap.read()  # 读取一帧图像
    if ret:
      # 应用透视变换
      # 注释掉的是后置相机变换，当前使用前置相机变换
      # img = cv2.warpPerspective(img, trans_webcam_to_eon_rear, (1164,874), borderMode=cv2.BORDER_CONSTANT, borderValue=0)
      img = cv2.warpPerspective(
          img,                           # 输入图像
          trans_webcam_to_eon_front,     # 变换矩阵
          (1164, 874),                   # 输出图像尺寸 (宽, 高)
          borderMode=cv2.BORDER_CONSTANT, # 边界填充模式
          borderValue=0                  # 填充值 (黑色)
      )

      # 打印图像尺寸信息 (覆盖上一行)
      print(f"图像尺寸: {img.shape}", end='\r')

      # 显示变换后的图像
      cv2.imshow('预览窗口', img)

      # 等待 10ms，检查是否有按键按下
      if cv2.waitKey(10) & 0xFF == ord('q'):  # 按 'q' 键退出
        break

  # 释放资源
  cap.release()
  cv2.destroyAllWindows()
