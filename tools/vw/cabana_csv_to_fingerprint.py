import csv
import json
from collections import defaultdict

# ===== 配置区 =====
CSV_FILE = "test.csv"          # Cabana 导出的 CSV
MIN_HZ = 5                    # 最低频率阈值（指纹建议 ≥5Hz）
EXTENDED_SHIFT = 1            # Cabana addr 右移位数
OUTPUT_JSON = "fingerprint.json"

# ===== 数据容器 =====
timestamps = defaultdict(list)
dlc_map = {}

# ===== 读取 CSV =====
with open(CSV_FILE, newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            t = float(row["time"])
            addr_raw = int(row["addr"], 16)
            data_hex = row["data"].replace("0x", "")

            # 还原真实 CAN ID（处理扩展帧）
            can_id = addr_raw >> EXTENDED_SHIFT

            # DLC = data 字节数
            dlc = len(data_hex) // 2

            timestamps[can_id].append(t)
            dlc_map[can_id] = max(dlc_map.get(can_id, 0), dlc)

        except Exception:
            continue

# ===== 计算频率 =====
fingerprint = {}
report = []

for can_id, times in timestamps.items():
    if len(times) < 2:
        continue

    duration = max(times) - min(times)
    hz = len(times) / duration if duration > 0 else 0

    if hz >= MIN_HZ:
        fingerprint[f"0x{can_id:X}"] = dlc_map[can_id]
        report.append((can_id, dlc_map[can_id], hz))

# ===== 输出 fingerprint.json =====
with open(OUTPUT_JSON, "w") as f:
    json.dump(fingerprint, f, indent=2)

# ===== 打印报告 =====
print("===== CAN Fingerprint Summary =====")
for can_id, dlc, hz in sorted(report):
    print(f"ID: 0x{can_id:08X}  DLC: {dlc}  Freq: {hz:.1f} Hz")

print(f"\nSaved fingerprint to {OUTPUT_JSON}")
print(f"Total CAN IDs: {len(fingerprint)}")
