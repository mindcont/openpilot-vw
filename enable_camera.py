#!/usr/bin/env python3
"""
启用 openpilot 摄像头进程
设置必要的参数来启动 webcamerad 进程
"""

import sys
import os
sys.path.append('/home/wio/openpilot')

from openpilot.common.params import Params

def enable_camera():
    print("=== 启用 openpilot 摄像头进程 ===")
    
    params = Params()
    
    # 启用驾驶员视图模式，这会触发摄像头进程启动
    params.put_bool("IsDriverViewEnabled", True)
    print("✓ 已启用驾驶员视图模式 (IsDriverViewEnabled = True)")
    
    # 检查当前设置
    print("\n当前摄像头相关设置:")
    print(f"IsDriverViewEnabled: {params.get_bool('IsDriverViewEnabled')}")
    print(f"USE_WEBCAM 环境变量: {os.getenv('USE_WEBCAM', '未设置')}")
    
    print("\n摄像头进程启动条件:")
    print("- webcamerad: 需要 USE_WEBCAM=1 且 (started=True 或 IsDriverViewEnabled=True)")
    print("- camerad: 需要 USE_WEBCAM 未设置 且 (started=True 或 IsDriverViewEnabled=True)")
    
    print("\n✅ 摄像头已配置完成！")
    print("现在启动 openpilot 时应该会看到 webcamerad 进程")

if __name__ == "__main__":
    enable_camera()