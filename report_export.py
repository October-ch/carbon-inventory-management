"""Local report snapshots and PDF generation using the existing PyMuPDF engine."""
import hashlib
import io
import json
import re
from datetime import datetime
from html import escape
from uuid import uuid4

import pymupdf

from inventory import ROOT

EXPORT_DIR = ROOT / "exports"
TEMPLATE_VERSION = "enterprise-demo-114-v2"
CALCULATION_VERSION = "decimal-activity-factor-v1"


def fingerprint(rows, narratives, source):
    content = {"rows": rows, "narratives": narratives, "source": source,
               "template": TEMPLATE_VERSION, "calculation": CALCULATION_VERSION}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def static_report(report):
    report = re.sub(r'<span class="link-mark"[^>]*>.*?</span>', '', report)
    report = re.sub(r'<button\b([^>]*)>', r'<span\1>', report)
    return (report.replace("</button>", "</span>")
            .replace("盤查報告草稿", "盤查報告（人工覆核）")
            .replace("模擬報告草稿", "模擬報告（人工覆核）")
            .replace("報告摘要 / 可點選數值追溯來源", "報告摘要")
            .replace("點擊係數可查看該列完整單位與版本。", "係數版本及來源詳見本版盤查快照。"))


def make_pdf(report, record):
    cover = f'''<div class="cover"><p>澄源科技股份有限公司（虛構）</p><h1>114 年溫室氣體盤查報告書</h1>
      <p>模擬企業盤查 · 人工覆核版本</p><p>盤查期間：114 年 1 月 1 日至 12 月 31 日</p>
      <p>覆核人：{escape(record['reviewer'])}<br>覆核時間：{escape(record['time'])}<br>
      版本：{escape(record['version'])}<br>來源：{escape(record['source_name'])}</p>
      <p>本文件為模擬資料與工作流程展示，非第三方查證聲明。</p></div>'''
    css = '''body{font-family:sans-serif;font-size:9pt;line-height:1.5;color:#24362f}
      .cover{text-align:center}
      .cover h1{font-size:23pt;margin:45pt 0} .cover p{margin:25pt 0}
      h1{font-size:21pt}h2{font-size:14pt;margin-top:16pt}
      h3{font-size:11pt;margin-top:12pt}
      p{margin:8pt 0}.paper-topline,.paper-footer,.report-label{font-size:8pt;color:#64766c}
      .draft-note{background-color:#f8f3e7;padding:10pt;font-size:9pt}
      .chapter{font-size:9pt;color:#53735c;margin-top:20pt}
      table{width:100%;border-collapse:collapse;margin:12pt 0;font-size:8pt}
      th{background-color:#dce9e0}th,td{border:0.5pt solid #b6c7bb;padding:5pt;text-align:right}
      td:first-child,th:first-child{text-align:left}.footnote{font-size:8pt;color:#6e7b72}
      .report-number{color:#24362f;font-weight:bold}.subtitle{color:#627566}
      '''
    html = '<html lang="zh-Hant"><body>' + static_report(report) + '</body></html>'
    story = pymupdf.Story(html=html, user_css=css)
    output = io.BytesIO()
    page_rect = pymupdf.paper_rect("a4")

    def rectangles(index, filled):
        if index > 80:
            raise ValueError("報告超過80頁，請縮短文字後重新輸出")
        return page_rect, page_rect + (45, 45, -45, -48), None

    with pymupdf.DocumentWriter(output) as writer:
        story.write(writer, rectangles)
    with pymupdf.open(stream=output.getvalue(), filetype="pdf") as pdf:
        first = pdf.new_page(pno=0, width=page_rect.width, height=page_rect.height)
        first.insert_htmlbox(pymupdf.Rect(55, 140, page_rect.width-55, page_rect.height-85), '<html lang="zh-Hant"><body>'+cover+'</body></html>', css=css)
        pdf.set_metadata({"title": "114年模擬企業溫室氣體盤查報告書", "author": record["reviewer"],
                          "subject": "模擬資料；人工覆核；未經第三方查證", "keywords": record["fingerprint"]})
        for i, page in enumerate(pdf):
            page.insert_text((45, page.rect.height-23), f"{record['version']}  |  {i+1} / {len(pdf)}", fontsize=8, color=(.45,.5,.47))
        return pdf.tobytes(garbage=4, deflate=True)


def freeze_report(rows, narratives, source, payload, reviewer, audit_log, revision):
    if not reviewer.strip() or len(reviewer) > 80:
        raise ValueError("請輸入80字以內的覆核人名稱")
    record = {"version": datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8],
              "time": datetime.now().astimezone().isoformat(timespec="seconds"), "reviewer": reviewer.strip(),
              "fingerprint": fingerprint(rows, narratives, source), "source_name": source.get("filename", "內建模擬底稿"),
              "template_version": TEMPLATE_VERSION, "calculation_version": CALCULATION_VERSION,
              "revision": revision, "simulation": True}
    # Render successfully before creating a persisted, approved output bundle.
    pdf = make_pdf(payload["report"], record)
    bundle = EXPORT_DIR / record["version"]
    bundle.mkdir(parents=True, exist_ok=False)
    snapshot = {"record": record, "source": source, "rows": rows, "narratives": narratives,
                "metrics": payload["metrics"], "audit_log": audit_log, "report_html": payload["report"]}
    pdf_path = bundle / "114年_模擬企業溫室氣體盤查報告書.pdf"
    pdf_path.write_bytes(pdf)
    (bundle / "盤查快照.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    if source.get("sha256"):
        from excel_io import INPUT_DIR, ensure_examples
        entry = next((e for e in ensure_examples() if e["sha256"] == source["sha256"]), None)
        if entry:
            original = (INPUT_DIR / entry["filename"]).read_bytes()
            if hashlib.sha256(original).hexdigest() == source["sha256"]:
                (bundle / entry["filename"]).write_bytes(original)
    record["pdf_sha256"] = hashlib.sha256(pdf).hexdigest()
    (bundle / "覆核紀錄.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**record, "directory": str(bundle), "pdf_path": str(pdf_path)}
