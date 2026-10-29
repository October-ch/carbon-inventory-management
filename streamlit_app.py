"""Streamlit app: linked simulation workpapers and inventory report."""
import hashlib
import json
from datetime import datetime

import pymupdf
import streamlit as st
import streamlit.components.v1 as components

from inventory import ROOT, apply_edit, build_payload, csv_bytes, load_rows
from workflow_ui import initialize_workflow, render_input, render_editor, render_output
from pdf_preview import render_pdf

PDF_PATH = ROOT / "114年溫室氣體盤查報告書.pdf"
st.set_page_config(page_title="碳盤查 · 底稿與報告連動", page_icon="🌿", layout="wide", initial_sidebar_state="collapsed")

workspace = components.declare_component("carbon_audit_workspace", path=str(ROOT / "components" / "audit_workspace"))

st.markdown("""<style>
  .stApp {background:#f5f7f4;color:#203c30}
  .block-container {padding:2rem 2.5rem 1rem;max-width:1900px}
  h1,h2,h3 {color:#253f31}
  .app-heading {display:flex;justify-content:space-between;align-items:center;gap:20px;margin:0 0 20px}
  .app-brand {font-size:11px;font-weight:650;letter-spacing:2px;color:#6c8b77;margin-bottom:10px}
  .app-heading h1 {font-size:29px;letter-spacing:1px;line-height:1.4;padding:0;margin:0}
  .app-heading p {font-size:12px;color:#87948a;margin:9px 0 0}
  .project-tag {border:1px solid #dce5dd;background:#fff;border-radius:7px;padding:10px 15px;color:#5b7563;font-size:12px;white-space:nowrap}
  [data-testid="stTabs"] [data-baseweb="tab-list"] {gap:25px}
  [data-testid="stTabs"] [data-baseweb="tab"] {font-size:13px}
  [data-testid="stMetric"] {background:white;border:1px solid #e0e7df;border-radius:9px;padding:13px 18px}
  [data-testid="stMetricValue"] {font-size:23px}
  [data-testid="stMetricLabel"] {color:#799080;font-size:11px}
  @media(max-width:800px){.block-container{padding:1.3rem 1rem}.app-heading h1{font-size:23px}.project-tag{display:none}}
  </style><div class="app-heading"><div><div class="app-brand">CARBON WORKSPACE / 盤查協作工作台</div><h1>讓每一筆報告數字，都有跡可循。</h1><p>114 年度企業盤查 · 模擬底稿 → 排放量計算 → 報告數據追溯</p></div><div class="project-tag">澄源科技（虛構） · 模擬資料</div></div>""", unsafe_allow_html=True)

if "inventory_rows" not in st.session_state:
    st.session_state.inventory_rows = load_rows()
    st.session_state.original_rows = load_rows()
    st.session_state.revision = 0
    st.session_state.audit_log = []
    st.session_state.selected_metric = "total"
    st.session_state.last_event_id = None
    st.session_state.workspace_epoch = 0

initialize_workflow()
payload = build_payload(st.session_state.inventory_rows, st.session_state.selected_metric, st.session_state.revision, st.session_state.report_narratives, st.session_state.source_info["filename"])
payload["error"] = st.session_state.pop("workspace_error", None)

overview = st.columns(4)
for column, label, key in zip(overview, ["示範盤查總量", "類別 1 · 直接排放", "類別 2 · 輸入能源", "類別 3 · 部分運輸"], ["total", "cat:1", "cat:2", "cat:3"]):
    column.metric(label + "（tCO₂e）", payload["metrics"][key]["value"])

linked_tab, practice_tab, input_tab, editor_tab, output_tab, pdf_tab, data_tab = st.tabs(["底稿與報告連動", "資料模擬練習", "Excel 匯入", "報告編輯與覆核", "PDF 預覽與輸出", "原始 PDF 範本", "匯出與修訂紀錄"])

with linked_tab:
    event = workspace(payload=payload, key=f"audit_workspace_{st.session_state.workspace_epoch}", default=None)
    if isinstance(event, dict) and event.get("event_id") and event["event_id"] != st.session_state.last_event_id:
        st.session_state.last_event_id = event["event_id"]
        if event.get("type") == "select" and event.get("metric_id") in payload["metrics"]:
            st.session_state.selected_metric = event["metric_id"]
        elif event.get("type") == "edit":
            try:
                updated, old_value = apply_edit(st.session_state.inventory_rows, event)
                st.session_state.inventory_rows = updated
                st.session_state.revision += 1
                st.session_state.reviewed_report = None
                st.session_state.audit_log.append({"revision": st.session_state.revision,
                    "time": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "row_id": event["row_id"], "field": event["field"], "old": old_value,
                    "new": str(event["value"])})
            except ValueError as exc:
                st.session_state.workspace_error = str(exc)
            st.rerun()
    st.caption("操作：點報告藍色數字查看來源；切換左側工作表查看跨表明細；雙擊活動量／係數後按 Enter 可重算。修改暫存於本工作階段，請至匯出頁下載留存。")

with practice_tab:
    st.subheader("資料模擬練習 · 預留串接入口")
    st.write("後續練習流程：原始 CSV → pandas 清理 → SQLite／SQL 分析 → 標準底稿 → 現有報告。")
    st.info("目前僅預留入口，尚未執行資料處理或匯入。後續會在獨立練習檔案完成流程，再從這裡串接結果。")
    st.download_button("下載目標底稿欄位範本 CSV", csv_bytes([]), "資料練習_目標底稿欄位.csv", "text/csv")
    st.caption("範本沿用現有底稿欄位；後續清理與 SQL 轉換結果將對應至此格式，再由既有計算邏輯產生報告。")

with input_tab:
    render_input()

with editor_tab:
    render_editor(payload)

with output_tab:
    render_output()


with pdf_tab:
    st.info("範本為經濟部 114 年溫室氣體盤查報告書。互動草稿參照其章節編排，使用虛構企業與模擬數據。原始 PDF 保持原內容，其數字未綁定模擬底稿。")
    if PDF_PATH.exists():
        with pymupdf.open(PDF_PATH) as document:
            page_count = len(document)
        controls, preview = st.columns([1, 3])
        with controls:
            st.caption(f"共 {page_count} 頁。第 2 頁為目錄，第 16 頁起為排放量計算，第 21 頁起為量化方法。")
            st.download_button("下載原始 PDF", data=PDF_PATH.read_bytes(), file_name=PDF_PATH.name, mime="application/pdf")
        with preview:
            render_pdf(PDF_PATH.read_bytes(), "原始 PDF 範本")
    else:
        st.warning(f"找不到範本 PDF，請將檔案放至：{PDF_PATH}")

with data_tab:
    st.subheader("保留這次盤查的資料與對應關係")
    st.caption("CSV 保留工作底稿，JSON 同時保存初始值、目前值、數值對應及工作階段修訂紀錄。下載後可作為此原型的資料快照；本版未提供正式多人版本管理。")
    current = st.session_state.inventory_rows
    snapshot = {
        "schema_version": 1, "simulation": True, "inventory_year": 114,
        "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "revision": st.session_state.revision, "original_rows": st.session_state.original_rows,
        "narratives": st.session_state.report_narratives, "source": st.session_state.source_info,
        "current_rows": current, "metrics": payload["metrics"], "audit_log": st.session_state.audit_log,
        "template": {"name": PDF_PATH.name, "sha256": hashlib.sha256(PDF_PATH.read_bytes()).hexdigest() if PDF_PATH.exists() else None},
    }
    downloads = st.columns(3)
    downloads[0].download_button("↓ 下載計算底稿 CSV", csv_bytes(current), "114年_模擬盤查計算底稿.csv", "text/csv")
    downloads[1].download_button("↓ 下載資料與追溯快照 JSON", json.dumps(snapshot, ensure_ascii=False, indent=2), "114年_盤查追溯快照.json", "application/json")
    # Standalone export preserves values and metric IDs as attributes for audit use.
    report_html = '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>114 年模擬盤查報告</title><style>body{max-width:1000px;margin:40px auto;font-family:sans-serif;line-height:1.8}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:8px}.report-number{border:0;background:transparent;font:inherit;color:inherit}.link-mark{display:none}.draft-note{background:#fff4dc;padding:15px}</style>' + payload["report"] + '</html>'
    downloads[2].download_button("↓ 下載報告 HTML", report_html, "114年_模擬溫室氣體盤查報告.html", "text/html")
    st.caption("下載之報告 HTML 為數值快照；報告點選連動功能須在 Streamlit 工作台使用。")
    if st.session_state.audit_log:
        st.dataframe(st.session_state.audit_log, hide_index=True, width="stretch")
    else:
        st.caption("尚無修改。雙擊底稿數值可新增一筆修訂紀錄。")
    with st.popover("重新載入初始模擬資料"):
        st.write("會清除本工作階段的修改與修訂紀錄，請先下載所需快照。")
        if st.button("確認重新載入", type="primary"):
            st.session_state.inventory_rows = load_rows()
            st.session_state.original_rows = load_rows()
            st.session_state.revision = 0
            st.session_state.audit_log = []
            st.session_state.selected_metric = "total"
            st.session_state.workspace_epoch += 1
            st.session_state.source_info = {"filename": "內建模擬盤查底稿.csv", "version": "v1"}
            st.session_state.reviewed_report = None
            st.session_state.last_import = None
            st.rerun()
