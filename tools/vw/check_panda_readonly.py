#!/usr/bin/env python3
"""只读防线（第二道硬件闸门）—— 核实 panda 固件处于只读安全模式。

设计背景见 learn-docs/环境搭建与容器部署.md 第十五节；
接入真实 CAN 场景下 ELM327 阶段风险的复核见
learn-docs/车型适配/CAN接入实车任务清单.md 「零、R2」。

为什么需要这道独立核实：
  openpilot 侧的 `passive`、启动脚本里的 `PASSIVE`/`NOBOARD` 环境变量都只是软件推断，
  真正决定 panda 会不会把转向/加速指令发上 CAN 总线的，是 panda 固件当前的
  SafetyModel。本脚本不依赖任何软件推断，直接问 panda 固件要 health 包，
  断言其安全模式为完全静默（silent / noOutput）且 controls_allowed == 0。

关于 ELM327 模式（R2 复核发现，2026-07 新增）：
  真实 CAN 场景下 `pandad` 上电后默认把 panda 切到 `ELM327` 模式（用于固件查询
  指纹），且因为本项目 `OpenpilotEnabledToggle=False` 会让 `card.py` 里
  `self.CP.passive` 恒为 `True`，导致 `ControlsReady` 永远不会被置位，
  `pandad` 的 `fetchCarParams()` 永远等不到条件满足，安全模式**永远停留在
  ELM327，不会被切换到真实车型的 safety mode**——所以不用担心切到会发送转向
  /加速指令的车型模式。但 `opendbc_repo/opendbc/safety/modes/elm327.h` 的
  `elm327_tx_hook` 允许发送 ISO 15765-4 标准诊断帧（8 字节，地址在
  0x600-0x6FF/0x700-0x7FF/UDS 专用地址范围内），这不是"完全不发任何东西"，
  严格来说偏离了纯只读目标（虽然不会误发正常行驶用的转向/加速报文）。
  `SKIP_FW_QUERY=1` 只能阻止 openpilot 软件层主动调用发送这些诊断请求，
  不能阻止固件本身处于允许发送诊断帧的安全模式。
  故本脚本把 `elm327` 单独归为一类，不计入"完全只读"，需要人工确认是否可接受
  （若只是被动监听，从未看到实际诊断帧发出，通常可接受；若要更严格，需评估
  R3 的物理层防线）。

用法：
  python3 tools/vw/check_panda_readonly.py

退出码：
  0  panda 处于完全静默安全模式（silent/noOutput），可放行观察
  1  panda 处于 ELM327 或其他可能可写状态，或读取失败 —— 需人工确认/现场排查

字段来源（已核实）：
  health()['safety_mode'] / ['controls_allowed']  -> panda/python/__init__.py:516-518
  SafetyModel 枚举值 silent@0/elm327@3/noOutput@19 -> opendbc_repo/opendbc/car/car.capnp
"""
import sys

# car.capnp SafetyModel: silent@0, noOutput@19（“like silent but without silent CAN TXs”）
SILENT = 0
ELM327 = 3
NO_OUTPUT = 19
READONLY_MODES = {SILENT: "silent", NO_OUTPUT: "noOutput"}
# 单独归类：ELM327 允许发送标准诊断帧，不算"完全静默"，但也不是转向/加速控制模式
CAUTION_MODES = {ELM327: "elm327"}


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
  if mode in READONLY_MODES:
    mode_name = READONLY_MODES[mode]
  elif mode in CAUTION_MODES:
    mode_name = CAUTION_MODES[mode]
  else:
    mode_name = f"未知/非只读(={mode})"

  print(f"  safety_mode      = {mode} ({mode_name})")
  print(f"  controls_allowed = {controls_allowed}")

  if mode in READONLY_MODES and controls_allowed == 0:
    print("✓ 完全静默 OK：panda 固件不会向 CAN 总线发送任何数据，可放行观察")
    return 0

  if mode in CAUTION_MODES and controls_allowed == 0:
    print("⚠️  ELM327 模式：固件不会发送转向/加速等控制指令（这是接入真实 CAN 后")
    print("    的预期初始状态，OpenpilotEnabledToggle=False 会让它永久停在这一步，")
    print("    不会被切到真实车型的可控 safety mode）。但该模式允许发送标准 ISO")
    print("    15765-4 诊断帧（8字节，地址 0x600-0x6FF/0x700-0x7FF/UDS专用范围），")
    print("    不是绝对意义上的'零发送'。若要更严格的只读保证，需评估 R3 物理层")
    print("    防线（learn-docs/车型适配/CAN接入实车任务清单.md）。")
    return 1

  print("⚠️  panda 可能处于可写状态！禁止上路观察，请现场排查：")
  if mode not in READONLY_MODES and mode not in CAUTION_MODES:
    print(f"    - safety_mode={mode} 不是 silent(0)/elm327(3)/noOutput(19) 中任何一种")
  if controls_allowed != 0:
    print(f"    - controls_allowed={controls_allowed} 非 0，固件认为可下发控制")
  print("    参考只读防线第一道：启动前 Params().put_bool('OpenpilotEnabledToggle', False)")
  return 1


if __name__ == "__main__":
  sys.exit(main())
