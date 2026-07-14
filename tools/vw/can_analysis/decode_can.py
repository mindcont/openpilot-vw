#!/usr/bin/env python3
"""
关键信号解析：用指定 DBC 解析 CAN 抓包 CSV，展示车辆核心信号
（车速/方向盘/档位/转速/刹车等），并统计每个信号的取值范围。

用法:
  python3 decode_can.py <csv> <dbc> [bus]
  python3 decode_can.py <csv> <dbc> [bus] --series <消息名>.<信号名>

不带 --series 时打印全部关键信号的 min/max 摘要（有变化会标 "<-- 有变化"）。
带 --series 时打印该信号完整的 (时间, 数值) 序列，用于动态验证场景
（比如转方向盘/挂挡时确认数值随操作实时正确变化，而不只是看一个 min/max 摘要），
见 learn-docs/车型适配/CAN数据抓取解析验证清单.md。

CSV 格式: time,addr,bus,data  (cabana 导出)
默认 bus=0（动力总成 CAN）。依赖: cantools
"""
import csv
import sys
import cantools
from collections import defaultdict

# 关注的关键消息（车辆静止/行驶状态下有意义的）
KEY_MSGS = {
    "ESP_02", "ESP_05", "ESP_21", "ESP_10", "ESP_19",
    "LWI_01", "LH_EPS_03",
    "Getriebe_11", "Getriebe_12",
    "Motor_18", "Motor_20", "Motor_14",
    "EPB_01", "Kombi_01", "Airbag_01",
    "Blinkmodi_02", "Gateway_72",
}


def fmt(v):
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def main(csv_path, dbc_path, bus_filter=0, series_target=None):
    db = cantools.database.load_file(dbc_path, strict=False)
    id_to_msg = {m.frame_id: m for m in db.messages}

    msg_frames = defaultdict(list)
    matched_ids = set()

    with open(csv_path) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            if len(row) < 4:
                continue
            t = float(row[0])
            addr = int(row[1], 16)
            bus = int(row[2])
            if bus != bus_filter or addr > 0x7FF:
                continue
            msg = id_to_msg.get(addr)
            if msg is None:
                continue
            data = bytes.fromhex(row[3][2:])
            if len(data) < msg.length:
                data = data + b"\x00" * (msg.length - len(data))
            try:
                decoded = db.decode_message(addr, data[:msg.length], decode_choices=True)
                matched_ids.add(addr)
                msg_frames[msg.name].append((t, decoded))
            except Exception:
                pass

    if series_target:
        msg_name, _, sig_name = series_target.partition(".")
        frames = msg_frames.get(msg_name)
        if not frames:
            print(f"未找到消息 {msg_name}（bus {bus_filter} 上没有解析出这条消息）")
            return
        t0 = frames[0][0]
        print(f"# {msg_name}.{sig_name} 时间序列（共 {len(frames)} 帧，t0={t0:.3f}）")
        print(f"{'t(s)':>10s}  {'t-t0(s)':>10s}  {sig_name}")
        for t, dec in frames:
            if sig_name not in dec:
                print(f"信号 {sig_name} 不在 {msg_name} 中，可选: {list(dec.keys())}")
                return
            print(f"{t:10.3f}  {t - t0:10.3f}  {fmt(dec[sig_name])}")
        return

    print(f"bus {bus_filter} 成功解析 {len(matched_ids)} 种消息\n")
    print("=" * 70)
    print("关键信号解析结果")
    print("=" * 70)

    for name in sorted(KEY_MSGS):
        frames = msg_frames.get(name)
        if not frames:
            continue
        print(f"\n### {name}  ({len(frames)} 帧)")
        last = frames[-1][1]
        sig_vals = defaultdict(list)
        for _, dec in frames:
            for k, v in dec.items():
                sig_vals[k].append(v)
        for sig, vals in sig_vals.items():
            numeric = [v for v in vals if isinstance(v, (int, float))]
            if numeric:
                vmin, vmax = min(numeric), max(numeric)
                changed = "  <-- 有变化" if vmax != vmin else ""
                print(f"  {sig:32s} = {fmt(last[sig]):>12s}  [min {fmt(vmin)}, max {fmt(vmax)}]{changed}")
            else:
                uniq = list(dict.fromkeys(str(v) for v in vals))
                print(f"  {sig:32s} = {str(last[sig]):>12s}  取值: {uniq[:4]}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    args = sys.argv[1:]
    series = None
    if "--series" in args:
        idx = args.index("--series")
        series = args[idx + 1]
        del args[idx:idx + 2]
    bus = int(args[2]) if len(args) > 2 else 0
    main(args[0], args[1], bus, series)
