#!/usr/bin/env python3
"""
纯监听 CAN 总线活跃度（不启动 openpilot，不改变 panda 当前 safety_mode，
不调用任何 can_send）。

用途：CAN 接入实车任务清单「三、Day1」步骤 6/10 —— 在车辆钥匙 ON、openpilot
未启动/已启动两个时刻分别跑一次，对比总线上出现的地址集合是否一致（不应
多出任何新地址）。

设计要点：
  - 只调用 panda.can_recv()，从不调用 panda.can_send()/can_send_many()，
    物理上不可能主动发送任何数据
  - 不修改 panda 的 safety_mode（当前是什么模式就保持什么模式），避免
    验证过程本身改变了要验证的状态
  - 固定时长自动退出，避免误留后台进程

用法：
  python3 tools/vw/can_analysis/passive_listen.py [seconds]  # 默认 15 秒

输出：
  各 bus 上出现的地址集合、每个地址的帧数统计，可用于与基线（之前抓包报告
  记录的地址列表）比对是否有新增地址。
"""
import sys
import time
from collections import defaultdict


def main(duration: float):
  try:
    from panda import Panda
  except ImportError:
    print("✗ 无法导入 panda 库；请在 openpilot 虚拟环境中运行本脚本")
    return 1

  try:
    p = Panda()
  except Exception as e:
    print(f"✗ 未能连接 panda（{e}）")
    return 1

  h = p.health()
  print(f"[监听前] safety_mode={h.get('safety_mode')}  controls_allowed={h.get('controls_allowed')}  "
        f"voltage={h.get('voltage')}mV  ignition_line={h.get('ignition_line')}")
  print(f"[监听中] 纯 RX，不发送任何数据，持续 {duration:.0f} 秒 ...")

  bus_addrs: dict[int, set[int]] = defaultdict(set)
  bus_counts: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
  total = 0

  start = time.monotonic()
  while time.monotonic() - start < duration:
    try:
      msgs = p.can_recv()
    except Exception as e:
      print(f"✗ can_recv 失败: {e}")
      break
    for addr, dat, bus in msgs:
      bus_addrs[bus].add(addr)
      bus_counts[bus][addr] += 1
      total += 1
    time.sleep(0.001)

  h_after = p.health()
  print(f"[监听后] safety_mode={h_after.get('safety_mode')}  controls_allowed={h_after.get('controls_allowed')}  "
        f"voltage={h_after.get('voltage')}mV  ignition_line={h_after.get('ignition_line')}")

  print(f"\n共收到 {total} 帧，涉及总线: {sorted(bus_addrs.keys())}")
  for bus in sorted(bus_addrs):
    addrs = sorted(bus_addrs[bus])
    print(f"\nbus {bus}: {len(addrs)} 种地址")
    print(f"  地址列表(hex): {[hex(a) for a in addrs]}")

  if total == 0:
    print("\n⚠️  0 帧收到 —— 接线可能不通，或车辆未上电/未点火，或 bus 配置不对")
    return 1

  # 安全态未发生变化才算通过
  if h.get('safety_mode') != h_after.get('safety_mode') or h.get('controls_allowed') != h_after.get('controls_allowed'):
    print("\n⚠️  监听前后 safety_mode/controls_allowed 发生变化，需要排查")
    return 1

  print("\n✓ 监听完成，safety_mode/controls_allowed 全程未变化")
  return 0


if __name__ == "__main__":
  duration = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0
  sys.exit(main(duration))
