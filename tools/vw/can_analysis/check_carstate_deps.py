#!/usr/bin/env python3
"""
检查 opendbc VW MQB carstate.py 依赖的所有 CAN 消息是否都在抓包数据中，
用于评估接入真实 CAN 后 carState 能否完整产出。

用法:
  python3 check_carstate_deps.py <csv> <dbc>

CSV 格式: time,addr,bus,data  (cabana 导出)。依赖: cantools
分析结论见: learn-docs/车型适配/第二阶段_接入CAN可行性评估.md
"""
import csv
import sys
import cantools

# carstate.py MQB 分支 + 共享逻辑 依赖的消息（含各字段用途）
DEPS = {
    "ESP_19":      "车速(四轮速→vEgo) ★核心",
    "Kombi_01":    "仪表车速/手刹",
    "LWI_01":      "方向盘角度/转速 ★核心",
    "LH_EPS_03":   "转向力矩/EPS状态 ★核心",
    "Motor_20":    "油门",
    "Motor_14":    "刹车踏板",
    "ESP_05":      "制动压力/刹车",
    "ESP_21":      "ESP状态/驻停",
    "Airbag_02":   "安全带 (AB_Gurtschloss_FA)",
    "Gateway_72":  "车门",
    "Gateway_73":  "档位 (GE_Fahrstufe) ★核心",
    "Blinkmodi_02":"转向灯",
    "TSK_06":      "巡航状态(TSK_Status)",
    "ACC_02":      "ACC设定速度/时距",
    "ACC_06":      "ACC类型",
    "ACC_10":      "stock FCW/AEB",
    "GRA_ACC_01":  "巡航按钮透传",
}


def main(csv_path, dbc_path):
    db = cantools.database.load_file(dbc_path, strict=False)
    name_to_id = {m.name: m.frame_id for m in db.messages}

    bus_addrs = {0: set(), 1: set(), 2: set()}
    with open(csv_path) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            if len(row) < 4:
                continue
            addr = int(row[1], 16)
            bus = int(row[2])
            if bus in bus_addrs:
                bus_addrs[bus].add(addr)

    print(f"{'消息':14s} {'ID':>6s}  {'bus0':5s}{'bus1':5s}{'bus2':5s}  用途")
    print("-" * 72)
    missing = []
    for name, desc in DEPS.items():
        mid = name_to_id.get(name)
        if mid is None:
            print(f"{name:14s} {'N/A':>6s}  DBC中无此消息!  {desc}")
            missing.append(name)
            continue
        b0 = "✓" if mid in bus_addrs[0] else "·"
        b1 = "✓" if mid in bus_addrs[1] else "·"
        b2 = "✓" if mid in bus_addrs[2] else "·"
        present = any(mid in bus_addrs[b] for b in bus_addrs)
        if not present:
            missing.append(name)
        print(f"{name:14s} {mid:>6d}  {b0:5s}{b1:5s}{b2:5s}  {desc}")

    print("\n" + "=" * 72)
    if missing:
        print(f"⚠️ 缺失消息 ({len(missing)}): {missing}")
        print("   → car 进程解析 carState 时这些字段将用默认值，可能触发 can invalid")
    else:
        print("✅ carstate.py 依赖的全部消息都在总线上，carState 可完整产出")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
