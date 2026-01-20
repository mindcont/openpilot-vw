#!/usr/bin/env python3
"""
大众速腾车型适配工具
用于快速添加24款大众速腾的openpilot支持
"""

import json
import os
import sys
from pathlib import Path

# openpilot路径
OPENPILOT_ROOT = Path("/home/wio/openpilot")
VW_PATH = OPENPILOT_ROOT / "opendbc_repo/opendbc/car/volkswagen"

class SagitarAdapter:
    def __init__(self):
        self.fingerprint_data = {}
        self.fw_versions = {}
        
    def collect_fingerprint(self, input_file=None):
        """采集或加载CAN指纹数据"""
        if input_file and os.path.exists(input_file):
            with open(input_file, 'r') as f:
                self.fingerprint_data = json.load(f)
            print(f"✅ 已加载指纹数据: {input_file}")
        else:
            # 示例指纹数据（需要从实车采集替换）
            self.fingerprint_data = {
                "0x1A0": 8,  # Bremse_1
                "0x86": 8,   # LWI_01  
                "0xB2": 8,   # ESP_19
                "0xFD": 8,   # ESP_21
                "0x6B8": 8,  # Kombi_03
                "0x30F": 8,  # SWA_01
                "0xAD": 8,   # Getriebe_11
                "0x40": 8,   # Airbag_01
                # 需要添加更多实车数据
            }
            print("⚠️  使用示例指纹数据，请替换为实车采集数据")
    
    def collect_firmware_versions(self):
        """设置固件版本数据（需要从实车采集）"""
        self.fw_versions = {
            "engine": [
                "b'\\xf1\\x8704E906024XX\\xf1\\x89XXXX'",  # 需要实车数据
            ],
            "srs": [
                "b'\\xf1\\x875Q0959655XX\\xf1\\x89XXXX\\xf1\\x82\\xXXXXXXXXXXXXXXXXXXXXXXXXXXXX'",
            ],
            "eps": [
                "b'\\xf1\\x875Q0909144XX\\xf1\\x89XXXX\\xf1\\x82\\xXXXXXXXXXXXX'",
            ],
        }
        print("⚠️  使用示例固件版本，请替换为实车采集数据")
    
    def generate_values_py_code(self):
        """生成values.py的代码片段"""
        code = '''
# 在 CAR 类中添加以下定义
VOLKSWAGEN_SAGITAR_MK8 = VolkswagenMQBPlatformConfig(
    [
        VWCarDocs("Volkswagen Sagitar 2024", "24款大众速腾（仅显示模式）"),
    ],
    VolkswagenCarSpecs(
        mass=1400,           # 车重(kg) - 需要实测
        wheelbase=2.69,      # 轴距(m) - 查阅规格书  
        steerRatio=15.6,     # 转向比 - 需要实测
        minSteerSpeed=0.4,   # 最小转向速度
    ),
    chassis_codes={"FT"},    # 底盘代码 - 从VIN码获取
    wmis={WMI.SAIC_VOLKSWAGEN},  # 上汽大众
)
'''
        return code
    
    def generate_fingerprints_py_code(self):
        """生成fingerprints.py的代码片段"""
        code = f'''
# 在 FW_VERSIONS 字典中添加以下条目
CAR.VOLKSWAGEN_SAGITAR_MK8: {{
    (Ecu.engine, 0x7e0, None): [
        {self.fw_versions.get("engine", ["# 需要实车采集"])[0]},
    ],
    (Ecu.srs, 0x715, None): [
        {self.fw_versions.get("srs", ["# 需要实车采集"])[0]},
    ],
    (Ecu.eps, 0x712, None): [
        {self.fw_versions.get("eps", ["# 需要实车采集"])[0]},
    ],
    # 注意: 速腾无ACC，通常没有fwdRadar
}},
'''
        return code
    
    def generate_interface_py_code(self):
        """生成interface.py的代码片段"""
        code = '''
# 在 _get_params 方法中添加以下代码
if candidate == CAR.VOLKSWAGEN_SAGITAR_MK8:
    # 仅显示模式配置
    ret.dashcamOnly = True
    ret.openpilotLongitudinalControl = False
    ret.pcmCruise = True
    ret.radarUnavailable = True
    
    # 禁用转向控制
    ret.steerControlType = structs.CarParams.SteerControlType.none
    
    # 网络配置（需要根据实车确定）
    ret.networkLocation = NetworkLocation.fwdCamera
    
    # 传输类型（根据实车配置）
    ret.transmissionType = TransmissionType.automatic
    
    # 安全配置
    safety_configs = [get_safety_config(structs.CarParams.SafetyModel.volkswagen)]
    ret.safetyConfigs = safety_configs
'''
        return code
    
    def create_patch_files(self):
        """创建补丁文件"""
        patch_dir = Path("sagitar_patches")
        patch_dir.mkdir(exist_ok=True)
        
        # values.py 补丁
        with open(patch_dir / "values_py_patch.txt", 'w') as f:
            f.write(self.generate_values_py_code())
        
        # fingerprints.py 补丁  
        with open(patch_dir / "fingerprints_py_patch.txt", 'w') as f:
            f.write(self.generate_fingerprints_py_code())
        
        # interface.py 补丁
        with open(patch_dir / "interface_py_patch.txt", 'w') as f:
            f.write(self.generate_interface_py_code())
        
        print(f"✅ 补丁文件已创建在 {patch_dir} 目录")
    
    def apply_patches(self, dry_run=True):
        """应用补丁到实际文件"""
        if dry_run:
            print("🔍 预览模式 - 不会修改实际文件")
            return
        
        # 备份原文件
        backup_dir = Path("backup_original")
        backup_dir.mkdir(exist_ok=True)
        
        files_to_backup = [
            VW_PATH / "values.py",
            VW_PATH / "fingerprints.py", 
            VW_PATH / "interface.py"
        ]
        
        for file_path in files_to_backup:
            if file_path.exists():
                backup_path = backup_dir / file_path.name
                import shutil
                shutil.copy2(file_path, backup_path)
                print(f"✅ 已备份: {file_path} -> {backup_path}")
        
        print("⚠️  请手动将补丁内容添加到相应文件中")
        print("⚠️  建议先在测试环境中验证")
    
    def generate_test_script(self):
        """生成测试脚本"""
        test_code = '''#!/usr/bin/env python3
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
'''
        
        with open("test_sagitar_adaptation.py", 'w') as f:
            f.write(test_code)
        
        os.chmod("test_sagitar_adaptation.py", 0o755)
        print("✅ 测试脚本已创建: test_sagitar_adaptation.py")
    
    def run(self):
        """运行适配流程"""
        print("🚗 大众速腾车型适配工具")
        print("=" * 50)
        
        # 1. 采集数据
        print("\n1. 采集指纹数据...")
        self.collect_fingerprint()
        
        print("\n2. 设置固件版本...")
        self.collect_firmware_versions()
        
        # 2. 生成代码
        print("\n3. 生成补丁文件...")
        self.create_patch_files()
        
        # 3. 生成测试脚本
        print("\n4. 生成测试脚本...")
        self.generate_test_script()
        
        # 4. 显示下一步操作
        print("\n📋 下一步操作:")
        print("1. 从实车采集准确的CAN指纹和固件版本数据")
        print("2. 将 sagitar_patches/ 目录中的代码添加到对应文件")
        print("3. 运行 test_sagitar_adaptation.py 验证配置")
        print("4. 编译openpilot: scons -j8")
        print("5. 实车测试验证功能")
        
        print("\n⚠️  重要提醒:")
        print("- 仅实现显示功能，不进行车辆控制")
        print("- 请在安全环境下测试")
        print("- 建议先备份原始文件")

def main():
    """主函数"""
    adapter = SagitarAdapter()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--fingerprint" and len(sys.argv) > 2:
            # 从文件加载指纹数据
            adapter.collect_fingerprint(sys.argv[2])
        elif sys.argv[1] == "--apply":
            # 应用补丁（实际修改文件）
            adapter.apply_patches(dry_run=False)
        elif sys.argv[1] == "--help":
            print("用法:")
            print("  python sagitar_adapter.py                    # 运行完整适配流程")
            print("  python sagitar_adapter.py --fingerprint FILE # 从文件加载指纹")
            print("  python sagitar_adapter.py --apply            # 应用补丁到文件")
            print("  python sagitar_adapter.py --help             # 显示帮助")
            return
    
    adapter.run()

if __name__ == "__main__":
    main()