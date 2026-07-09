#!/usr/bin/env python3
"""
ACC 前车雷达距离信号专项评估：检查前雷达/ACC 报文能提供哪些距离相关信息，
判断 ACC 功能是否编码启用、前车距离是否可获取。

用法:
  python3 acc_radar.py <csv> <dbc>

CSV 格式: time,addr,bus,data  (cabana 导出)。依赖: cantools

背景（24 款速腾中配）：车辆物理装有前雷达传感器，但 ACC 功能未编码启用，
预期所有距离/目标信号为空值（ACC_Typ=ACC_nicht_codiert）。
"""
import csv
import sys
import cantools
from collections import defaultdict

# ACC/雷达距离相关信号（消息名, 信号名, 含义）
ACC_SIGNALS = [
    ("ACC_02", "ACC_Relevantes_Objekt",       "是否检测到相关前车目标"),
    ("ACC_02", "ACC_Abstandsindex",           "前车距离指数(1-1021,仪表距离条)"),
    ("ACC_02", "ACC_Wunschgeschw_02",         "ACC设定目标车速(km/h)"),
    ("ACC_02", "ACC_Gesetzte_Zeitluecke",     "设定跟车时距档位"),
    ("ACC_02", "ACC_Anzeige_Zeitluecke",      "显示跟车时距"),
    ("ACC_04", "ACC_Abstand_Abstandswarner",  "距离警告器-前车距离等级"),
    ("ACC_04", "ACC_Zeitluecke_Abstandswarner","距离警告器-时距(秒)"),
    ("ACC_04", "ACC_Texte_Abstandswarner",    "距离警告器文本状态"),
    ("ACC_07", "ACC_Anhalteweg",              "预计停车距离(米)"),
    ("ACC_10", "PCF_Time_to_collision",       "预碰撞TTC(秒)"),
    ("ACC_06", "ACC_Status_ACC",              "ACC系统状态"),
    ("ACC_06", "ACC_Typ",                     "ACC类型(是否编码)"),
    ("TSK_08", "TSK_aktives_System",          "前雷达激活的系统"),
    ("TSK_08", "TSK_Status_EA",               "紧急辅助状态"),
    ("GRA_ACC_01","GRA_Hauptschalter",        "巡航主开关"),
]


def main(csv_path, dbc_path):
    db = cantools.database.load_file(dbc_path, strict=False)
    id_to_msg = {m.frame_id: m for m in db.messages}
    name_to_msg = {m.name: m for m in db.messages}

    want_ids = {name_to_msg[n].frame_id for n, _, _ in ACC_SIGNALS if n in name_to_msg}
    sig_vals = defaultdict(list)
    msg_count = defaultdict(int)

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
            msg_count[msg.name] += 1
            data = bytes.fromhex(row[3][2:])
            if len(data) < msg.length:
                data = data + b"\x00" * (msg.length - len(data))
            try:
                dec = db.decode_message(addr, data[:msg.length], decode_choices=True)
                for sig, v in dec.items():
                    sig_vals[(msg.name, sig)].append(v)
            except Exception:
                pass

    print("=" * 74)
    print("ACC / 前车雷达距离信号评估（bus 0）")
    print("=" * 74)
    print(f"\n{'含义':32s} {'状态':7s} 值范围/取值")
    print("-" * 74)
    for msgname, signame, meaning in ACC_SIGNALS:
        if msgname not in name_to_msg:
            print(f"{meaning:32s} DBC无消息 {msgname}")
            continue
        vals = sig_vals.get((msgname, signame))
        if not vals:
            print(f"{meaning:32s} ✗缺失   {msgname}.{signame} 未解出")
            continue
        numeric = [v for v in vals if isinstance(v, (int, float))]
        if numeric:
            vmin, vmax = min(numeric), max(numeric)
            chg = " 有变化" if vmax != vmin else ""
            print(f"{meaning:32s} ✓可获取 [{vmin:.3f}, {vmax:.3f}]{chg}  ({msgname}.{signame})")
        else:
            uniq = list(dict.fromkeys(str(v) for v in vals))[:5]
            print(f"{meaning:32s} ✓可获取 {uniq}  ({msgname}.{signame})")

    print("\n消息出现帧数:", dict(msg_count))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
