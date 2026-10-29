"""Create the reproducible demonstration workpaper without overwriting edits."""
import csv

from inventory import DATA_PATH, FIELDS


def generate():
    if DATA_PATH.exists():
        print(f"資料已存在，保留原檔：{DATA_PATH}")
        return
    rows = []

    def add(rid, sheet, month, item, category, scope, activity, unit, factor, factor_unit, doc):
        rows.append(dict(zip(FIELDS, [rid, sheet, month, item, category, scope, str(activity), unit,
                                      str(factor), factor_unit, doc, "自行模擬，非官方數據／無實體憑證", "DEMO-114-v1"])))

    electricity = [68000, 62500, 70500, 72800, 78100, 86400, 92500, 95800, 88300, 79400, 71600, 68800]
    gasoline = [210, 185, 224, 198, 235, 242, 226, 218, 247, 231, 202, 215]
    for i, quantity in enumerate(electricity, 1):
        add(f"ELE-{i:02d}", "用電底稿", f"114/{i:02d}", "辦公室外購電力", "2", "Scope 2", quantity,
            "kWh", "0.47", "kgCO₂e/kWh", f"模擬電費單-E114{i:02d}")
    for i, quantity in enumerate(gasoline, 1):
        add(f"FUEL-{i:02d}", "燃料底稿", f"114/{i:02d}", "公務車汽油", "1", "Scope 1", quantity,
            "L", "2.3", "kgCO₂e/L", f"模擬加油彙總-F114{i:02d}")
    for i, quantity in [(6, "1.2"), (12, "0.8")]:
        add(f"REF-{i:02d}", "冷媒底稿", f"114/{i:02d}", "空調冷媒補充（示範視為逸散量）", "1", "Scope 1", quantity,
            "kg", "675", "kgCO₂e/kg", f"模擬冷媒維修單-R114{i:02d}")
    for i, quantity in [(2, 1230), (3, 1860), (4, 980), (6, 2050), (7, 1620), (9, 2310), (10, 1840), (12, 1420)]:
        add(f"TRAVEL-{i:02d}", "差旅底稿", f"114/{i:02d}", "員工商務鐵路差旅", "3", "Scope 3 / 類別6", quantity,
            "人公里", "0.032", "kgCO₂e/人公里", f"模擬差旅清冊-T114{i:02d}")
    DATA_PATH.parent.mkdir(exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"已建立 {len(rows)} 筆模擬資料：{DATA_PATH}")


if __name__ == "__main__":
    generate()
