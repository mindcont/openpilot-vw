#!/usr/bin/env python3
"""
横向控制(转向)可行性核查:从 CAN 抓包判断车辆是否具备 openpilot 控横向的前提。

关键判据(基于 opendbc VW MQB interface.py / carcontroller.py):
  - HCA_01 (0x126) 在相机总线出现 → 有原厂 R242 相机(车道保持 Lane Assist)
    → STOCK_HCA_PRESENT,openpilot 可拦截并替换其转向报文
  - LDW_02 在相机总线 → 原厂车道偏离警告
  - LH_EPS_03.EPS_HCA_Status → EPS 是否支持/就绪 HCA 转向注入
  - networkLocation 判断:bus0 有 Airbag_01/LWI_01/ESP_19/ESP_21 → gateway

用法:
  python3 check_lateral_deps.py <csv> <dbc>
"""
import csv
import sys
import cantools

# (消息名, 关注信号或用途)
LAT_MSGS = {
    "HCA_01":    "原厂车道保持转向报文(R242相机发) ★控横向前提",
    "LDW_02":    "原厂车道偏离警告(相机发)",
    "LH_EPS_03": "EPS 状态(EPS_HCA_Status 决定是否接受转向注入)",
}
# networkLocation=gateway 判据消息(interface.py: fingerprint[1] 命中即 gateway)
NETLOC_MSGS = {"Airbag_01": 0x40, "LWI_01": 0x86, "ESP_19": 0xB2, "ESP_21": 0xFD}


def main(csv_path, dbc_path):
    db = cantools.database.load_file(dbc_path, strict=False)
    id_to_msg = {m.frame_id: m for m in db.messages}
    name_to_id = {m.name: m.frame_id for m in db.messages}

    bus_addrs = {0: set(), 1: set(), 2: set()}
    eps_hca_status = []
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
            if addr == name_to_id.get("LH_EPS_03") and bus == 0:
                msg = id_to_msg[addr]
                data = bytes.fromhex(row[3][2:])
                if len(data) >= msg.length:
                    try:
                        dec = db.decode_message(addr, data[:msg.length], decode_choices=True)
                        eps_hca_status.append(str(dec.get("EPS_HCA_Status")))
                    except Exception:
                        pass

    print("=" * 74)
    print("横向控制(转向)可行性核查")
    print("=" * 74)

    print("\n【1】原厂车道保持相关报文在各总线的存在情况")
    print(f"{'消息':12s} {'ID':>6s}  bus0 bus1 bus2  说明")
    print("-" * 74)
    for name, desc in LAT_MSGS.items():
        mid = name_to_id.get(name)
        if mid is None:
            print(f"{name:12s} {'N/A':>6s}  DBC无定义  {desc}")
            continue
        b = [("✓" if mid in bus_addrs[i] else "·") for i in (0, 1, 2)]
        print(f"{name:12s} {mid:>6d}  {b[0]:4s} {b[1]:4s} {b[2]:4s}  {desc}")

    print("\n【2】EPS_HCA_Status 取值(是否就绪接受转向注入)")
    if eps_hca_status:
        uniq = list(dict.fromkeys(eps_hca_status))
        print(f"    取值: {uniq}")
        print("    说明: DISABLED=EPS未配置车道保持(拒绝转向); initializing/READY/ACTIVE=支持")
    else:
        print("    未解析到 LH_EPS_03")

    print("\n【3】网络位置(networkLocation)判断")
    hit = [n for n, mid in NETLOC_MSGS.items() if mid in bus_addrs[0]]
    netloc = "gateway" if hit else "fwdCamera"
    print(f"    bus0 命中判据消息: {hit or '无'}")
    print(f"    → networkLocation = {netloc}")
    print("    (gateway 才支持 openpilot 纵向 alpha_long;控横向需相机侧 harness)")

    print("\n" + "=" * 74)
    print("结论")
    print("=" * 74)
    hca_present = name_to_id.get("HCA_01") in (bus_addrs[0] | bus_addrs[1] | bus_addrs[2])
    if hca_present:
        print("  ✓ 总线存在 HCA_01 → 车辆有原厂车道保持相机(Lane Assist 硬件在位)")
        print("    横向控制前提【具备】(仍需: 可写 panda + 相机中间人 harness + EPS 就绪)")
    else:
        print("  ✗ 总线未见 HCA_01 → 未检测到原厂车道保持相机")
        print("    横向控制前提【存疑】: 需确认车辆是否有原厂车道保持功能")
    print("  注: 最终以车辆配置单/EPS 编码为准,静止抓包仅供参考。")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
