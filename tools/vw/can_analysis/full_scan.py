#!/usr/bin/env python3
"""
全量解析测试 + 关键信号评估（含 ACC 前车雷达相关消息）。
对三条总线做覆盖统计，并评估车道预测所需信号的可获取性。

用法:
  python3 full_scan.py <csv> <dbc>

CSV 格式: time,addr,bus,data  (cabana 导出)。依赖: cantools
"""
import csv
import sys
import cantools
from collections import defaultdict

RADAR_MSGS = ["ACC_02", "ACC_06", "ACC_07", "ACC_04", "ACC_10",
              "TSK_06", "TSK_08", "GRA_ACC_01"]

# (消息名, 信号名, 含义)
KEY_SIGNALS = [
    ("ESP_21",  "ESP_v_Signal",        "车速(km/h)"),
    ("ESP_02",  "ESP_Gierrate",        "横摆角速度"),
    ("LWI_01",  "LWI_Lenkradwinkel",   "方向盘角度"),
    ("LH_EPS_03","EPS_Berechneter_LW", "EPS计算转向角"),
    ("LH_EPS_03","EPS_Lenkmoment",     "转向力矩"),
    ("Getriebe_11","GE_Fahrstufe",     "档位"),
    ("Motor_20","MO_Fahrpedalrohwert_01","油门踏板"),
    ("ESP_05",  "ESP_Fahrer_bremst",   "驾驶员刹车"),
    ("ESP_05",  "ESP_Bremsdruck",      "制动压力"),
]


def main(csv_path, dbc_path):
    db = cantools.database.load_file(dbc_path, strict=False)
    id_to_msg = {m.frame_id: m for m in db.messages}
    name_to_msg = {m.name: m for m in db.messages}

    # --- 第一步：ACC/雷达消息信号定义 ---
    print("=" * 72)
    print("第一步：ACC / 前雷达相关消息的信号定义")
    print("=" * 72)
    for name in RADAR_MSGS:
        m = name_to_msg.get(name)
        if not m:
            print(f"\n### {name}: DBC 中不存在")
            continue
        sender = m.senders[0] if m.senders else "?"
        print(f"\n### {name} (ID {m.frame_id}=0x{m.frame_id:X}, 发送者 {sender})")
        for s in m.signals:
            unit = s.unit or ""
            low = s.name.lower()
            tag = ""
            if any(k in low for k in ["abstand", "distanz", "ziel", "objekt", "voraus", "collision"]):
                tag = "  ★距离/目标"
            print(f"    {s.name:34s} {str(unit):22s}{tag}")

    # --- 第二步：全量三总线统计 ---
    print("\n" + "=" * 72)
    print("第二步：全量三总线解析统计")
    print("=" * 72)
    bus_addr_count = defaultdict(lambda: defaultdict(int))
    with open(csv_path) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            if len(row) < 4:
                continue
            addr = int(row[1], 16)
            bus = int(row[2])
            bus_addr_count[bus][addr] += 1

    radar_ids = {name_to_msg[n].frame_id for n in RADAR_MSGS if n in name_to_msg}
    for bus in sorted(bus_addr_count):
        addrs = bus_addr_count[bus]
        std = {a for a in addrs if a <= 0x7FF}
        ext = {a for a in addrs if a > 0x7FF}
        matched = std & set(id_to_msg)
        print(f"\nbus {bus}: 标准帧 {len(std)} 种(可解析 {len(matched)}), 扩展帧 {len(ext)} 种")
        present = sorted(radar_ids & set(addrs))
        if present:
            names = [f"{id_to_msg[i].name}({bus_addr_count[bus][i]}帧)" for i in present]
            print(f"        ACC/雷达消息出现: {', '.join(names)}")
        else:
            print(f"        ACC/雷达消息出现: 无")

    # --- 第三步：关键信号评估 ---
    print("\n" + "=" * 72)
    print("第三步：车道预测关键信号评估（bus 0）")
    print("=" * 72)
    want_ids = {name_to_msg[n].frame_id for n, _, _ in KEY_SIGNALS if n in name_to_msg}
    sig_vals = defaultdict(list)
    with open(csv_path) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            if len(row) < 4:
                continue
            addr = int(row[1], 16)
            bus = int(row[2])
            if bus != 0 or addr not in want_ids:
                continue
            msg = id_to_msg[addr]
            data = bytes.fromhex(row[3][2:])
            if len(data) < msg.length:
                data = data + b"\x00" * (msg.length - len(data))
            try:
                dec = db.decode_message(addr, data[:msg.length], decode_choices=False)
                for sig, v in dec.items():
                    sig_vals[(msg.name, sig)].append(v)
            except Exception:
                pass

    print(f"\n{'信号':40s} {'状态':6s} {'值范围/说明'}")
    print("-" * 72)
    for msgname, signame, meaning in KEY_SIGNALS:
        if msgname not in name_to_msg:
            print(f"{meaning:20s}{msgname}.{signame:22s} DBC无此消息")
            continue
        vals = sig_vals.get((msgname, signame))
        if not vals:
            appeared = name_to_msg[msgname].frame_id in bus_addr_count[0]
            note = "消息出现但信号未解出" if appeared else "消息未在bus0出现"
            print(f"{meaning:20s}{msgname}.{signame:22s} ✗缺失   {note}")
            continue
        numeric = [v for v in vals if isinstance(v, (int, float))]
        if numeric:
            print(f"{meaning:20s}{msgname}.{signame:22s} ✓可获取 min={min(numeric):.3f} max={max(numeric):.3f} ({len(vals)}帧)")
        else:
            uniq = list(dict.fromkeys(str(v) for v in vals))[:4]
            print(f"{meaning:20s}{msgname}.{signame:22s} ✓可获取 {uniq}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
