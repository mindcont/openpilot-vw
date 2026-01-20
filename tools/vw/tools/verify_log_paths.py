#!/usr/bin/env python3
"""
验证日志目录配置脚本
"""

import os
import sys
sys.path.append('/home/wio/openpilot')

from openpilot.system.hardware.hw import Paths

def verify_log_paths():
    print("=== openpilot 日志目录配置验证 ===")
    
    # 检查各个路径
    paths = {
        "swaglog_root": Paths.swaglog_root(),
        "log_root": Paths.log_root(), 
        "persist_root": Paths.persist_root(),
        "stats_root": Paths.stats_root(),
        "comma_home": Paths.comma_home()
    }
    
    for name, path in paths.items():
        exists = os.path.exists(path)
        writable = os.access(path, os.W_OK) if exists else False
        print(f"{name:15}: {path}")
        print(f"{'':15}  存在: {exists}, 可写: {writable}")
        
        if not exists:
            try:
                os.makedirs(path, exist_ok=True)
                print(f"{'':15}  已创建目录")
            except Exception as e:
                print(f"{'':15}  创建失败: {e}")
        print()
    
    # 检查环境变量
    print("=== 环境变量 ===")
    env_vars = ['PC', 'LOG_ROOT', 'LOGPRINT']
    for var in env_vars:
        value = os.environ.get(var, '未设置')
        print(f"{var}: {value}")

if __name__ == "__main__":
    verify_log_paths()