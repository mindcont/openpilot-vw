#!/usr/bin/env python3
"""
DBC 匹配度分析：比较 CAN 抓包 CSV 与多个 DBC 的地址覆盖率，帮助选出最合适的 DBC。

用法:
  python3 analyze_match.py <csv> <dbc1> [dbc2 ...]

CSV 格式: time,addr,bus,data  (cabana 导出)
依赖: cantools
"""
import csv
import sys
import cantools
from collections import defaultdict


def main(csv_path, dbc_paths):
    # 统计每条总线上每个 addr 的出现次数（只看标准帧 <= 0x7FF）
    bus_addr = defaultdict(lambda: defaultdict(int))
    with open(csv_path) as f:
        r = csv.reader(f)
        next(r)  # header
        for row in r:
            if len(row) < 4:
                continue
            addr = int(row[1], 16)
            bus = int(row[2])
            if addr <= 0x7FF:  # 标准帧
                bus_addr[bus][addr] += 1

    print("=== 各总线标准帧统计 ===")
    for bus in sorted(bus_addr):
        print(f"bus {bus}: {len(bus_addr[bus])} 个不同标准帧地址, 共 {sum(bus_addr[bus].values())} 帧")

    for dbc_file in dbc_paths:
        try:
            db = cantools.database.load_file(dbc_file, strict=False)
        except Exception as e:
            print(f"\n=== {dbc_file} 加载失败: {e} ===")
            continue
        dbc_ids = {m.frame_id for m in db.messages}
        print(f"\n=== {dbc_file} ({len(dbc_ids)} 消息) ===")
        for bus in sorted(bus_addr):
            addrs = set(bus_addr[bus].keys())
            matched = addrs & dbc_ids
            cov = 100.0 * len(matched) / len(addrs) if addrs else 0
            print(f"  bus {bus}: 匹配 {len(matched)}/{len(addrs)} 地址 ({cov:.0f}%)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2:])
