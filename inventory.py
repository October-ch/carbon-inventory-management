"""Simulated inventory and explicit report-to-workpaper lineage.

Every coefficient is a demonstration value, not an approved reporting factor.
All arithmetic uses Decimal; rounding is applied only when displaying results.
"""

import csv
import io
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "模擬盤查底稿.csv"
FIELDS = ["row_id", "sheet", "month", "item", "category", "scope", "activity", "unit", "factor", "factor_unit", "document", "source", "factor_version"]
SHEETS = ["用電底稿", "燃料底稿", "冷媒底稿", "差旅底稿"]
EDITABLE = {"activity", "factor"}
NARRATIVE_LABELS = {"company": "企業簡介", "boundary": "盤查邊界說明", "materiality": "重大性與變動說明", "actions": "減量措施說明"}
DEFAULT_NARRATIVES = {
    "company": "澄源科技股份有限公司為虛構企業，本案例假設其營運活動包括辦公室用電、公務車使用、空調設備維護及員工差旅。本報告為資料連動功能展示，非實際企業之盤查聲明。",
    "boundary": "模擬組織以營運控制方式界定單一營運據點，期間為 114 年 1 月至 12 月。本原型示範類別 1、2 及部分類別 3 的資料追溯；間接排放顯著性評估與其他排放源完整性仍待補齊。",
    "materiality": "本期示範盤查總量為 {{total}} tCO₂e，其中輸入能源間接排放為 {{cat:2}} tCO₂e。尚未提供前期資料，不計算跨期變動率；重大性與排放源完整性仍待人工評估。",
    "actions": "本示範尚未蒐集已執行減量措施及實際成效，故不填列減量量或宣稱減量成果。",
}


def dec(value):
    return Decimal(str(value))


def number(value, places=3):
    return f"{dec(value):,.{places}f}"


def load_rows():
    with DATA_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    validate_rows(rows)
    return rows


def validate_rows(rows):
    ids = set()
    for row in rows:
        if row["row_id"] in ids:
            raise ValueError("底稿 row_id 不可重複")
        ids.add(row["row_id"])
        if row["sheet"] not in SHEETS:
            raise ValueError("未知底稿工作表")
        for field in EDITABLE:
            try:
                value = dec(row[field])
            except (InvalidOperation, ValueError):
                raise ValueError("活動量與係數須為有效數字")
            if not value.is_finite() or value < 0 or value > Decimal("1e12"):
                raise ValueError("活動量與係數須介於 0 與 1,000,000,000,000")


def apply_edit(rows, event):
    """Validate untrusted component events before changing session data."""
    if event.get("field") not in EDITABLE:
        raise ValueError("只能修改活動量或排放係數")
    updated = [dict(row) for row in rows]
    row = next((r for r in updated if r["row_id"] == event.get("row_id")), None)
    if row is None:
        raise ValueError("找不到底稿列")
    old_value = row[event["field"]]
    row[event["field"]] = str(event.get("value", ""))
    validate_rows(updated)
    return updated, old_value


def emission(row):
    # Factors are already expressed in kg CO2e; do not multiply GWP again.
    return dec(row["activity"]) * dec(row["factor"]) / Decimal(1000)


def csv_bytes(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDS + ["emissions_tco2e", "source_book", "source_sheet", "source_excel_row"])
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "emissions_tco2e": str(emission(row))})
    return output.getvalue().encode("utf-8-sig")


def build_payload(rows, selected="total", revision=0, narratives=None, source_name=None, language="zh-TW"):
    metrics = {}
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["sheet"]].append(row)

    def metric(key, label, value, unit, dependencies, formula, field="emissions", places=3):
        metrics[key] = {
            "id": key, "label": label, "value": number(value, places), "unit": unit,
            "rows": [r["row_id"] for r in dependencies], "field": field,
            "formula": formula, "raw_value": str(value),
        }
        return key

    def token(key):
        m = metrics[key]
        return (f'<button class="report-number" data-metric="{escape(key, quote=True)}" '
                f'title="查看底稿：{escape(m["label"], quote=True)}">{m["value"]}'
                '<span class="link-mark" aria-hidden="true">↗</span></button>')

    def narrative(key):
        text = (narratives or DEFAULT_NARRATIVES).get(key, DEFAULT_NARRATIVES[key])
        if not isinstance(text, str) or len(text) > 6000:
            raise ValueError("每段報告文字須為 6,000 字以內")
        parts = re.split(r"(\{\{[^{}]+\}\})", text)
        rendered = []
        for part in parts:
            if part.startswith("{{") and part.endswith("}}"):
                metric_id = part[2:-2].strip()
                if metric_id not in metrics:
                    raise ValueError(f"未知報告欄位：{metric_id}")
                rendered.append(token(metric_id))
            else:
                rendered.append(escape(part).replace("\n", "<br>"))
        return "".join(rendered)

    total = sum((emission(r) for r in rows), Decimal(0))
    metric("total", "盤查排放總量", total, "tCO₂e", rows, "Σ 各底稿列排放量（未先四捨五入）")
    group_totals = {}
    for sheet in SHEETS:
        rs = grouped[sheet]
        value = sum((emission(r) for r in rs), Decimal(0))
        group_totals[sheet] = value
        metric(f"sum:{sheet}", sheet.replace("底稿", "") + "排放量", value, "tCO₂e", rs,
               "Σ（各筆活動量 × 該筆係數 ÷ 1,000）")
        metric(f"qty:{sheet}", sheet.replace("底稿", "") + "活動量合計",
               sum((dec(r["activity"]) for r in rs), Decimal(0)), rs[0]["unit"], rs,
               "Σ 該工作表各筆活動量", "activity", 2)
    for cat, name in [("1", "直接排放"), ("2", "輸入能源間接排放"), ("3", "運輸間接排放")]:
        rs = [r for r in rows if r["category"] == cat]
        value = sum((emission(r) for r in rs), Decimal(0))
        metric("cat:" + cat, name, value, "tCO₂e", rs, "Σ 該類別各筆排放量")
        if total:
            metric("share:" + cat, name + "占本示範盤查總量比例", value / total * 100, "%", rows,
                   "該類別未四捨五入排放量 ÷ 全部未四捨五入排放量 × 100", "emissions", 2)
    for r in rows:
        rid = r["row_id"]
        metric(f"row:{rid}", r["month"] + " " + r["item"] + "排放量", emission(r), "tCO₂e", [r],
               f'{r["activity"]} {r["unit"]} × {r["factor"]} {r["factor_unit"]} ÷ 1,000')
        metric(f"activity:{rid}", r["month"] + " " + r["item"] + "活動量", dec(r["activity"]), r["unit"], [r],
               "底稿原始活動量", "activity", 2)
        metric(f"factor:{rid}", r["month"] + " " + r["item"] + "係數", dec(r["factor"]), r["factor_unit"], [r],
               "底稿採用的模擬係數（已含 CO₂e 換算）", "factor", 4)

    category_rows = ""
    names = {"1": "直接排放及移除", "2": "輸入能源間接排放", "3": "運輸間接排放"}
    for cat in names:
        share = token("share:" + cat) + "%" if total else "—（總量為零）"
        category_rows += f'<tr><td>類別 {cat}</td><td>{names[cat]}</td><td>{token("cat:" + cat)}</td><td>{share}</td></tr>'

    source_rows = "".join(
        f'<tr><td>{escape(sheet.replace("底稿", ""))}</td><td>{token("qty:"+sheet)} {escape(grouped[sheet][0]["unit"])}</td>'
        f'<td>{token("sum:"+sheet)}</td></tr>' for sheet in SHEETS
    )
    details = []
    for sheet in SHEETS:
        body = "".join(
            f'<tr><td>{escape(r["month"])}</td><td>{escape(r["item"])}</td>'
            f'<td>{token("activity:"+r["row_id"])}</td><td>{escape(r["unit"])}</td>'
            f'<td>{token("factor:"+r["row_id"])}</td><td>{token("row:"+r["row_id"])}</td></tr>'
            for r in grouped[sheet]
        )
        details.append(f'<h3>{escape(sheet.replace("底稿", ""))}計算明細</h3><table><thead><tr><th>期間</th><th>項目</th><th>活動量</th><th>單位</th><th>係數¹</th><th>tCO₂e</th></tr></thead><tbody>{body}</tbody></table>')

    report = f"""
    <article class="paper">
      <div class="paper-topline">模擬企業 · 盤查報告草稿 <span>114 年度</span></div>
      <div class="report-label">GREENHOUSE GAS INVENTORY</div>
      <h1>溫室氣體盤查報告書</h1>
      <p class="subtitle">澄源科技股份有限公司（虛構）｜民國 114 年度</p>
      <div class="draft-note">模擬資料 · 未經查證<br>依提供 PDF 之章節結構編製互動示範；內容與數字由模擬底稿產生。</div>
      <section id="report-summary"><div class="chapter">報告摘要 / 可點選數值追溯來源</div><h2>年度盤查結果</h2>
      <p>本示範涵蓋營運據點之用電、車用燃料、冷媒補充及商務差旅。114 年度納入示範之排放總量為 {token("total")} tCO₂e。</p>
      <table><thead><tr><th>ISO 類別</th><th>排放項目</th><th>排放量 tCO₂e</th><th>占本示範總量</th></tr></thead><tbody>{category_rows}</tbody></table>
      <p class="footnote">總量僅代表本示範邊界，不代表完整企業排放；類別 4–6 未評估，並非零排放。占比使用未四捨五入數值計算。</p></section>
      <section id="report-company"><div class="chapter">第一章 / 企業簡介</div><h2>組織概況</h2>
      <p>{narrative("company")}</p></section>
      <section id="report-boundary"><div class="chapter">第二章 / 盤查邊界設定</div><h2>組織範圍與報告期間</h2>
      <p>{narrative("boundary")}</p>
      <p>底稿保留 ISO 類別與 GHG Protocol Scope 標記。差旅於此案例標記為 ISO 類別 3 與 GHG Protocol Scope 3／類別 6，對照限於本案例所述活動。</p></section>
      <section id="report-sources"><div class="chapter">第三章 / 排放源鑑別</div><h2>排放源與待補鑑別</h2>
      <p>本示範納入用電、燃料、冷媒與差旅，未執行完整排放源鑑別及間接排放顯著性評估，亦未制定排除門檻。冷媒示範假設維修補充量等於逸散量；實際盤查須確認適用量化方法及紀錄。</p></section>
      <section id="report-overview"><div class="chapter">第四章 / 排放量計算</div><h2>4.1 溫室氣體總排放當量</h2>
      <p>本示範總排放量為 {token("total")} tCO₂e。直接排放為 {token("cat:1")} tCO₂e；輸入能源間接排放為 {token("cat:2")} tCO₂e；納入之商務差旅排放為 {token("cat:3")} tCO₂e。</p>
      <h3>表 4-1　示範排放源彙整</h3>
      <table><thead><tr><th>排放源</th><th>活動量合計</th><th>排放量 tCO₂e</th></tr></thead><tbody>{source_rows}</tbody></table>
      <p class="footnote">本示範係數未拆分氣體別，故不產生七大溫室氣體個別排放量表，避免由合計 CO₂e 推測氣體組成。</p></section>
      <section id="report-materiality"><h2>4.2 重大性與變動說明</h2><p>{narrative("materiality")}</p></section>
      <section id="report-method"><div class="chapter">第五章 / 溫室氣體盤查量化方法</div><h2>5.1 量化方法說明</h2>
      <p>各筆排放量＝活動量 × 排放係數 ÷ 1,000，單位為 tCO₂e。係數已以 kg CO₂e 表示，不再次乘上 GWP。合計值使用未四捨五入數值加總，再顯示至小數點後三位。</p>
      <p class="footnote">本示範每張工作表活動量使用同一單位。全部係數皆為自行設定之模擬值；不能援用於正式申報或查證。</p></section>
      <section id="report-quality"><h2>5.4 排放係數與數據品質管理</h2>
      <p>所有模擬活動數據都附有虛構憑證編號，供示範追溯操作；並無對應之真實發票或憑證檔。實際導入時，須以原始帳單、活動紀錄及正式係數文件取代。</p>
      <p>待補項目包括：間接排放顯著性評估、全部排放源完整性、係數適用性與正式版本、GWP 基準、資料品質及不確定性評估、基準年與重算政策、內部覆核和第三方查證。</p></section>
      <section id="report-actions"><div class="chapter">第六章 / 執行減量措施及說明</div><h2>減量措施紀錄</h2><p>{narrative("actions")}</p></section>
      <section id="report-references"><div class="chapter">第七章 / 參考文獻</div><h2>範本與數據說明</h2><p>章節參考：經濟部《114 年溫室氣體盤查報告書》。本原型未使用該報告之實際排放數據。活動量與係數之匯入來源為「{escape(source_name or '模擬盤查底稿.csv')}」，目前採用值以本次快照為準；本示範係數版本為 DEMO-114-v1，僅供操作示範。</p></section>
      <section id="report-detail"><div class="chapter">第八章 / 附件</div><h2>活動數據與計算明細</h2>{''.join(details)}
      <p class="footnote">¹ 係數單位依序為用電 kgCO₂e/kWh、燃料 kgCO₂e/L、冷媒 kgCO₂e/kg、差旅 kgCO₂e/人公里。點擊係數可查看該列完整單位與版本。</p></section>
      <div class="paper-footer">114 年度 · 模擬報告草稿 <span>由計算底稿連動產生</span></div>
    </article>"""
    display_rows = [{**r, "emissions": number(emission(r)), "raw_emissions": str(emission(r))} for r in rows]
    if language == "en":
        from localization import english_report, SHEETS_EN
        report = english_report(report)
        for metric_data in metrics.values():
            metric_data["label"] = english_report(metric_data["label"])
            metric_data["formula"] = english_report(metric_data["formula"])
        display_rows = [{**row, "sheet_label": SHEETS_EN.get(row["sheet"], row["sheet"])} for row in display_rows]
    else:
        display_rows = [{**row, "sheet_label": row["sheet"].replace("底稿", "")} for row in display_rows]
    return {"rows": display_rows, "sheets": SHEETS, "metrics": metrics, "report": report, "language": language,
            "selected": selected if selected in metrics else "total", "revision": revision,
            "total": number(total), "group_totals": {k: number(v) for k, v in group_totals.items()}}
