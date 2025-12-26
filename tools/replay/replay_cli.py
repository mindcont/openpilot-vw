#!/usr/bin/env python3
"""
openpilot Replay 中文命令行界面
支持配置切换和中文显示的交互式回放工具
"""

import os
import sys
import argparse
import json
from pathlib import Path
from typing import Dict, Any

class ReplayConfig:
    """回放配置管理"""
    
    def __init__(self):
        self.config_file = Path.home() / ".openpilot_replay_config.json"
        self.default_config = {
            "language": "zh",  # zh/en
            "default_speed": 1.0,
            "auto_loop": True,
            "show_debug": False,
            "cache_segments": 5,
            "preferred_source": "auto",  # auto/internal/api/ci
            "video_output": True,
            "data_dir": "",
        }
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 合并默认配置
                return {**self.default_config, **config}
            except:
                pass
        return self.default_config.copy()
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def get(self, key: str, default=None):
        """获取配置值"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """设置配置值"""
        self.config[key] = value
        self.save_config()

class ReplayCLI:
    """Replay 命令行界面"""
    
    def __init__(self):
        self.config = ReplayConfig()
        self.texts = self.load_texts()
    
    def load_texts(self) -> Dict[str, Dict[str, str]]:
        """加载多语言文本"""
        return {
            "zh": {
                "title": "=== openpilot 回放工具 ===",
                "route_prompt": "请输入路由名称 (或输入 'help' 查看帮助): ",
                "help_title": "\n=== 帮助信息 ===",
                "help_examples": """
示例路由格式:
  a2a0ccea32023010|2023-07-27--13-01-19     # 完整路由
  a2a0ccea32023010|2023-07-27--13-01-19/0   # 特定段
  a2a0ccea32023010|2023-07-27--13-01-19/0:5 # 段范围
  --demo                                      # 演示路由
  
特殊命令:
  config  - 配置设置
  exit    - 退出程序
  help    - 显示帮助
                """,
                "config_title": "\n=== 配置设置 ===",
                "config_options": """
1. 语言设置 (当前: {language})
2. 默认播放速度 (当前: {speed}x)
3. 自动循环 (当前: {loop})
4. 显示调试信息 (当前: {debug})
5. 缓存段数 (当前: {cache})
6. 数据源 (当前: {source})
7. 视频输出 (当前: {video})
8. 数据目录 (当前: {data_dir})
0. 返回主菜单
                """,
                "select_option": "请选择选项 (0-8): ",
                "invalid_option": "无效选项，请重新选择。",
                "language_options": "\n语言选项:\n1. 中文 (zh)\n2. English (en)\n选择 (1-2): ",
                "speed_prompt": "输入播放速度 (0.1-5.0): ",
                "cache_prompt": "输入缓存段数 (1-20): ",
                "data_dir_prompt": "输入数据目录路径 (留空使用默认): ",
                "source_options": "\n数据源选项:\n1. 自动 (auto)\n2. 内部 (internal)\n3. API (api)\n4. CI (ci)\n选择 (1-4): ",
                "toggle_prompt": "切换为 {value} (y/n): ",
                "config_updated": "配置已更新: {key} = {value}",
                "starting_replay": "正在启动回放: {route}",
                "replay_options": "回放选项: {options}",
                "error": "错误: {message}",
                "goodbye": "再见！",
            },
            "en": {
                "title": "=== openpilot Replay Tool ===",
                "route_prompt": "Enter route name (or 'help' for help): ",
                "help_title": "\n=== Help Information ===",
                "help_examples": """
Route format examples:
  a2a0ccea32023010|2023-07-27--13-01-19     # Full route
  a2a0ccea32023010|2023-07-27--13-01-19/0   # Specific segment
  a2a0ccea32023010|2023-07-27--13-01-19/0:5 # Segment range
  --demo                                      # Demo route
  
Special commands:
  config  - Configuration settings
  exit    - Exit program
  help    - Show help
                """,
                "config_title": "\n=== Configuration Settings ===",
                "config_options": """
1. Language (current: {language})
2. Default speed (current: {speed}x)
3. Auto loop (current: {loop})
4. Show debug (current: {debug})
5. Cache segments (current: {cache})
6. Data source (current: {source})
7. Video output (current: {video})
8. Data directory (current: {data_dir})
0. Back to main menu
                """,
                "select_option": "Select option (0-8): ",
                "invalid_option": "Invalid option, please try again.",
                "language_options": "\nLanguage options:\n1. 中文 (zh)\n2. English (en)\nSelect (1-2): ",
                "speed_prompt": "Enter playback speed (0.1-5.0): ",
                "cache_prompt": "Enter cache segments (1-20): ",
                "data_dir_prompt": "Enter data directory path (empty for default): ",
                "source_options": "\nData source options:\n1. Auto (auto)\n2. Internal (internal)\n3. API (api)\n4. CI (ci)\nSelect (1-4): ",
                "toggle_prompt": "Toggle to {value} (y/n): ",
                "config_updated": "Configuration updated: {key} = {value}",
                "starting_replay": "Starting replay: {route}",
                "replay_options": "Replay options: {options}",
                "error": "Error: {message}",
                "goodbye": "Goodbye!",
            }
        }
    
    def t(self, key: str, **kwargs) -> str:
        """获取本地化文本"""
        lang = self.config.get("language", "zh")
        text = self.texts.get(lang, self.texts["zh"]).get(key, key)
        return text.format(**kwargs) if kwargs else text
    
    def show_help(self):
        """显示帮助信息"""
        print(self.t("help_title"))
        print(self.t("help_examples"))
    
    def configure_language(self):
        """配置语言"""
        print(self.t("language_options"))
        try:
            choice = input().strip()
            if choice == "1":
                self.config.set("language", "zh")
                print(self.t("config_updated", key="语言", value="中文"))
            elif choice == "2":
                self.config.set("language", "en")
                print(self.t("config_updated", key="Language", value="English"))
            else:
                print(self.t("invalid_option"))
        except (ValueError, KeyboardInterrupt):
            pass
    
    def configure_speed(self):
        """配置播放速度"""
        try:
            speed = float(input(self.t("speed_prompt")))
            if 0.1 <= speed <= 5.0:
                self.config.set("default_speed", speed)
                print(self.t("config_updated", key="播放速度", value=f"{speed}x"))
            else:
                print(self.t("error", message="速度必须在 0.1-5.0 之间"))
        except (ValueError, KeyboardInterrupt):
            print(self.t("error", message="无效的速度值"))
    
    def configure_cache(self):
        """配置缓存段数"""
        try:
            cache = int(input(self.t("cache_prompt")))
            if 1 <= cache <= 20:
                self.config.set("cache_segments", cache)
                print(self.t("config_updated", key="缓存段数", value=cache))
            else:
                print(self.t("error", message="缓存段数必须在 1-20 之间"))
        except (ValueError, KeyboardInterrupt):
            print(self.t("error", message="无效的缓存段数"))
    
    def configure_data_dir(self):
        """配置数据目录"""
        try:
            data_dir = input(self.t("data_dir_prompt")).strip()
            self.config.set("data_dir", data_dir)
            print(self.t("config_updated", key="数据目录", value=data_dir or "默认"))
        except KeyboardInterrupt:
            pass
    
    def configure_source(self):
        """配置数据源"""
        print(self.t("source_options"))
        try:
            choice = input().strip()
            sources = {"1": "auto", "2": "internal", "3": "api", "4": "ci"}
            if choice in sources:
                source = sources[choice]
                self.config.set("preferred_source", source)
                print(self.t("config_updated", key="数据源", value=source))
            else:
                print(self.t("invalid_option"))
        except (ValueError, KeyboardInterrupt):
            pass
    
    def toggle_boolean(self, key: str, name: str):
        """切换布尔值配置"""
        current = self.config.get(key, False)
        new_value = not current
        try:
            confirm = input(self.t("toggle_prompt", value="启用" if new_value else "禁用")).strip().lower()
            if confirm in ['y', 'yes', '是', '1']:
                self.config.set(key, new_value)
                print(self.t("config_updated", key=name, value="启用" if new_value else "禁用"))
        except KeyboardInterrupt:
            pass
    
    def show_config_menu(self):
        """显示配置菜单"""
        while True:
            print(self.t("config_title"))
            print(self.t("config_options",
                language=self.config.get("language", "zh"),
                speed=self.config.get("default_speed", 1.0),
                loop="启用" if self.config.get("auto_loop", True) else "禁用",
                debug="启用" if self.config.get("show_debug", False) else "禁用",
                cache=self.config.get("cache_segments", 5),
                source=self.config.get("preferred_source", "auto"),
                video="启用" if self.config.get("video_output", True) else "禁用",
                data_dir=self.config.get("data_dir", "默认") or "默认"
            ))
            
            try:
                choice = input(self.t("select_option")).strip()
                
                if choice == "0":
                    break
                elif choice == "1":
                    self.configure_language()
                elif choice == "2":
                    self.configure_speed()
                elif choice == "3":
                    self.toggle_boolean("auto_loop", "自动循环")
                elif choice == "4":
                    self.toggle_boolean("show_debug", "调试信息")
                elif choice == "5":
                    self.configure_cache()
                elif choice == "6":
                    self.configure_source()
                elif choice == "7":
                    self.toggle_boolean("video_output", "视频输出")
                elif choice == "8":
                    self.configure_data_dir()
                else:
                    print(self.t("invalid_option"))
                    
            except KeyboardInterrupt:
                break
    
    def build_replay_command(self, route: str) -> str:
        """构建回放命令"""
        cmd_parts = ["tools/replay/replay"]
        
        # 路由参数
        if route == "--demo":
            cmd_parts.append("--demo")
        else:
            cmd_parts.append(f'"{route}"')
        
        # 配置参数
        speed = self.config.get("default_speed", 1.0)
        if speed != 1.0:
            cmd_parts.append(f"-x {speed}")
        
        cache = self.config.get("cache_segments", 5)
        if cache != 5:
            cmd_parts.append(f"-c {cache}")
        
        if not self.config.get("auto_loop", True):
            cmd_parts.append("--no-loop")
        
        if not self.config.get("video_output", True):
            cmd_parts.append("--no-vipc")
        
        data_dir = self.config.get("data_dir", "")
        if data_dir:
            cmd_parts.append(f'--data_dir "{data_dir}"')
        
        source = self.config.get("preferred_source", "auto")
        if source != "auto":
            cmd_parts.append(f"--{source}")
        
        return " ".join(cmd_parts)
    
    def start_replay(self, route: str):
        """启动回放"""
        try:
            cmd = self.build_replay_command(route)
            print(self.t("starting_replay", route=route))
            print(self.t("replay_options", options=cmd))
            
            # 执行回放命令
            os.system(cmd)
            
        except Exception as e:
            print(self.t("error", message=str(e)))
    
    def run(self):
        """运行主循环"""
        print(self.t("title"))
        
        while True:
            try:
                route = input(self.t("route_prompt")).strip()
                
                if not route:
                    continue
                elif route.lower() in ['exit', 'quit', '退出']:
                    print(self.t("goodbye"))
                    break
                elif route.lower() in ['help', '帮助']:
                    self.show_help()
                elif route.lower() in ['config', '配置']:
                    self.show_config_menu()
                else:
                    self.start_replay(route)
                    
            except KeyboardInterrupt:
                print(f"\n{self.t('goodbye')}")
                break
            except EOFError:
                break

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="openpilot Replay 中文命令行界面")
    parser.add_argument("--route", help="直接指定路由名称")
    parser.add_argument("--config", action="store_true", help="打开配置菜单")
    
    args = parser.parse_args()
    
    cli = ReplayCLI()
    
    if args.config:
        cli.show_config_menu()
    elif args.route:
        cli.start_replay(args.route)
    else:
        cli.run()

if __name__ == "__main__":
    main()