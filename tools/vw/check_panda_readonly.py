#!/usr/bin/env python3
"""只读防线（第二道硬件闸门）—— 核实 panda 固件处于只读安全模式。

设计背景见 learn-docs/环境搭建与容器部署.md 第十五节。

为什么需要这道独立核实：
  openpilot 侧的 `passive`、启动脚本里的 `PASSIVE`/`NOBOARD` 环境变量都只是软件推断，
  真正决定 panda 会不会把转向/加速指令发上 CAN 总线的，是 panda 固件当前的
  SafetyModel。本脚本不依赖任何软件推断，直接问 panda 固件要 health 包，
  断言其安全模式为只读（silent / noOutput）且 controls_allowed == 0。

用法：
  python3 tools/vw/check_panda_readonly.py

退出码：
  0  panda 处于只读态，可放行观察
  1  panda 可能可写，或读取失败 —— 禁止上路，需现场排查

字段来源（已核实）：
  health()['safety_mode'] / ['controls_allowed']  -> panda/python/__init__.py:516-518
  SafetyModel 枚举值 silent@0 / noOutput@19        -> opendbc_repo/opendbc/car/car.capnp:603,622
"""
import sys

# car.capnp SafetyModel: silent@0, noOutput@19（“like silent but without silent CAN TXs”）
SILENT = 0
NO_OUTPUT = 19
READONLY_MODES = {SILENT: "silent", NO_OUTPUT: "noOutput"}


def main() -> int:
  try:
    from panda import Panda
  except ImportError:
    print("✗ 无法导入 panda 库；请在 openpilot 虚拟环境中运行本脚本")
    return 1

  try:
    p = Panda()
  except Exception as e:
    print(f"✗ 未能连接 panda（{e}）；确认已通过 USB 接入且未被其他进程占用")
    return 1

  try:
    h = p.health()
  except Exception as e:
    print(f"✗ 读取 panda health 失败（{e}）")
    return 1

  mode = h.get("safety_mode")
  controls_allowed = h.get("controls_allowed")
  mode_name = READONLY_MODES.get(mode, f"非只读(={mode})")

  print(f"  safety_mode      = {mode} ({mode_name})")
  print(f"  controls_allowed = {controls_allowed}")

  ok = mode in READONLY_MODES and controls_allowed == 0
  if ok:
    print("✓ 只读 OK：panda 固件不会向 CAN 总线下发控制指令，可放行观察")
    return 0

  print("⚠️  panda 可能处于可写状态！禁止上路观察，请现场排查：")
  if mode not in READONLY_MODES:
    print(f"    - safety_mode={mode} 不是 silent(0)/noOutput(19)")
  if controls_allowed != 0:
    print(f"    - controls_allowed={controls_allowed} 非 0，固件认为可下发控制")
  print("    参考只读防线第一道：启动前 Params().put_bool('OpenpilotEnabledToggle', False)")
  return 1


if __name__ == "__main__":
  sys.exit(main())
