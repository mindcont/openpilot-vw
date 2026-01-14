#!/usr/bin/env python3
import json
import importlib.util
from pathlib import Path

# openpilot 根目录（假设从 repo 根运行）
ROOT = Path(__file__).resolve().parents[1]
CAR_DIR = ROOT / "opendbc" / "car"

# ========== 1. 读取你的 fingerprint ==========
def load_my_fingerprint(path):
    with open(path, "r") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return {int(k, 16): v for k, v in data.items()}
    elif isinstance(data, list):
        return {int(item["id"], 16): item["dlc"] for item in data}
    else:
        raise ValueError("Unknown fingerprint format")

# ========== 2. 动态加载 values.py ==========
def load_values_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_all_car_fingerprints():
    car_fps = {}

    for brand_dir in CAR_DIR.iterdir():
        if not brand_dir.is_dir():
            continue

        values_py = brand_dir / "values.py"
        if not values_py.exists():
            continue

        try:
            values = load_values_module(values_py)
        except Exception:
            continue

        if not hasattr(values, "FINGERPRINTS"):
            continue

        for car, fps_list in values.FINGERPRINTS.items():
            car_fps.setdefault(car, []).extend(fps_list)

    return car_fps

# ========== 3. 相似度计算 ==========
def fingerprint_similarity(my_fp, car_fp):
    my_ids = set(my_fp.keys())
    car_ids = set(car_fp.keys())

    inter = my_ids & car_ids
    union = my_ids | car_ids
    if not union:
        return 0.0

    id_score = len(inter) / len(union)

    dlc_match = sum(
        1 for cid in inter if my_fp[cid] == car_fp[cid]
    )
    dlc_score = dlc_match / max(1, len(inter))

    return 0.7 * id_score + 0.3 * dlc_score

# ========== 4. 主流程 ==========
def main():
    my_fp = load_my_fingerprint("fingerprint.json")
    all_car_fps = load_all_car_fingerprints()

    print(f"Loaded fingerprints for {len(all_car_fps)} cars")

    scores = []
    for car, fps_list in all_car_fps.items():
        best = max(
            fingerprint_similarity(my_fp, fp)
            for fp in fps_list
        )
        if best > 0:
            scores.append((car, best))

    scores.sort(key=lambda x: x[1], reverse=True)

    print("\nTop similar cars:")
    for car, score in scores[:15]:
        print(f"{car:35s} score={score:.3f}")

if __name__ == "__main__":
    main()
