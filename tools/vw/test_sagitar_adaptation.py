#!/usr/bin/env python3
"""大众速腾车型识别测试脚本"""

import sys
import os
sys.path.append('/home/wio/openpilot')

def test_sagitar_recognition():
    """测试大众速腾车型识别"""
    try:
        from opendbc.car.volkswagen.values import CAR
        
        # 检查车型是否已定义
        if hasattr(CAR, 'VOLKSWAGEN_SAGITAR_MK8'):
            print("✅ 大众速腾车型定义已添加")
            
            # 获取车型配置
            sagitar = CAR.VOLKSWAGEN_SAGITAR_MK8
            print(f"车型配置: {sagitar}")
            
            return True
        else:
            print("❌ 大众速腾车型定义未找到")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_fingerprint_loading():
    """测试指纹数据加载"""
    try:
        from opendbc.car.volkswagen.fingerprints import FW_VERSIONS
        
        if CAR.VOLKSWAGEN_SAGITAR_MK8 in FW_VERSIONS:
            print("✅ 指纹数据已添加")
            fw_data = FW_VERSIONS[CAR.VOLKSWAGEN_SAGITAR_MK8]
            print(f"固件版本数量: {len(fw_data)}")
            return True
        else:
            print("❌ 指纹数据未找到")
            return False
            
    except Exception as e:
        print(f"❌ 指纹测试失败: {e}")
        return False

if __name__ == "__main__":
    print("开始测试大众速腾车型适配...")
    
    success = True
    success &= test_sagitar_recognition()
    success &= test_fingerprint_loading()
    
    if success:
        print("🎉 所有测试通过!")
    else:
        print("❌ 部分测试失败，请检查配置")
