"""Additive Excel → narrative editing → manual review → frozen PDF workflow."""
import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from excel_io import INPUT_DIR, ensure_examples, import_generated_excel
from inventory import DEFAULT_NARRATIVES, NARRATIVE_LABELS, build_payload
from report_export import fingerprint, freeze_report
from pdf_preview import render_pdf


def initialize_workflow():
    defaults = {"report_narratives": dict(DEFAULT_NARRATIVES), "source_info": {"filename": "內建模擬盤查底稿.csv", "version": "v1"},
                "reviewed_report": None, "last_import": None, "narrative_epoch": 0}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def current_fingerprint():
    return fingerprint(st.session_state.inventory_rows, st.session_state.report_narratives, st.session_state.source_info)


def render_input():
    st.subheader("用 Excel 底稿更新報告數值")
    st.caption("先下載自行產生的 v1 或 v2 原檔，再上傳到下方。系統先核對檔案 SHA-256，通過後才讀取；本版不接受其他 Excel 或經修改重新儲存的檔案。")
    entries = ensure_examples()
    cols = st.columns(2)
    for column, entry in zip(cols, entries):
        with column:
            st.write(entry["description"])
            st.download_button("下載模擬 Excel " + entry["version"], (INPUT_DIR / entry["filename"]).read_bytes(), entry["filename"],
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_"+entry["version"])
    uploaded = st.file_uploader("上傳本專案產生的 Excel 原檔", type=["xlsx"], key="excel_input", help="目前僅接受以上兩份原檔，最大500 KB。所有公式計算均由系統執行，Excel內為數值快照。")
    st.caption("匯入會更新整份底稿並保留已儲存的報告文字；既有覆核狀態會失效。尚未下載的介面數字修改會被此次匯入資料取代。")
    if st.button("驗證並匯入 Excel", type="primary", disabled=uploaded is None):
        try:
            rows, source = import_generated_excel(uploaded.getvalue())
            old = build_payload(st.session_state.inventory_rows)["metrics"]
            new = build_payload(rows)["metrics"]
            changes = [{"欄位": new[key]["label"], "匯入前": old[key]["value"], "匯入後": new[key]["value"], "單位": new[key]["unit"]}
                       for key in ["total", "cat:1", "cat:2", "cat:3"]]
            st.session_state.inventory_rows = rows
            st.session_state.original_rows = [dict(r) for r in rows]
            st.session_state.source_info = source
            st.session_state.revision += 1
            st.session_state.workspace_epoch += 1
            st.session_state.selected_metric = "total"
            st.session_state.last_event_id = None
            st.session_state.last_import = {"source": source["filename"], "changes": changes}
            st.session_state.reviewed_report = None
            st.session_state.audit_log.append({"revision": st.session_state.revision, "time": datetime.now().astimezone().isoformat(timespec="seconds"),
                "action": "excel_import", "source": source["filename"], "sha256": source["sha256"]})
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    st.write("目前資料來源：", st.session_state.source_info["filename"])
    if st.session_state.last_import:
        st.success("匯入成功。已核對底稿排放量與 Python 重算結果，並更新報告欄位。")
        st.dataframe(st.session_state.last_import["changes"], hide_index=True, width="stretch")
    with st.expander("Excel 格式與報告欄位對照"):
        st.write("檔案包含使用說明、用電／燃料／冷媒／差旅四張底稿，以及報告欄位對照。活動量及係數是輸入，排放量由 Python 重算；不執行 Excel 公式或外部連線。")
        metrics = build_payload(st.session_state.inventory_rows)["metrics"]
        st.dataframe([{"報告欄位ID": key, "用途": m["label"], "值": m["value"], "來源列數": len(m["rows"])}
                      for key, m in metrics.items() if key in ["total", "cat:1", "cat:2", "cat:3"] or key.startswith("sum:")], hide_index=True)


def render_editor(payload):
    st.subheader("調整敘述，確認報告內容")
    st.caption("保留自動數值欄位，例如 {{total}} 或 {{cat:2}}，資料更新後仍會連動；自行輸入的固定數字不會自動更新。儲存文字後，回到左右工作台即可檢視完整報告。")
    with st.form("report_narrative_form"):
        edited = {}
        for key, label in NARRATIVE_LABELS.items():
            edited[key] = st.text_area(label, value=st.session_state.report_narratives[key], height=115, max_chars=6000,
                                       key=f"narrative_{key}_{st.session_state.narrative_epoch}")
        saved = st.form_submit_button("儲存報告文字並更新草稿", type="primary")
    if saved:
        try:
            build_payload(st.session_state.inventory_rows, narratives=edited)
            if edited != st.session_state.report_narratives:
                st.session_state.report_narratives = edited
                st.session_state.revision += 1
                st.session_state.reviewed_report = None
                st.session_state.audit_log.append({"revision": st.session_state.revision, "time": datetime.now().astimezone().isoformat(timespec="seconds"),
                                                   "action": "report_text_update", "narratives": dict(edited)})
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    st.divider()
    st.write("**人工覆核與版本凍結**")
    st.caption("這是本機操作人的內部確認紀錄，並非第三方查證或身分認證。請先儲存上方文字，再確認本版。")
    fp = current_fingerprint()
    st.caption("目前內容指紋：" + fp[:16])
    with st.form("review_"+fp):
        checks = [st.checkbox("已核對報告數值與對應底稿", key="check_numbers_"+fp),
                  st.checkbox("已確認報告文字與重大性說明", key="check_narrative_"+fp),
                  st.checkbox("已確認本文件為模擬資料，待補範圍有適當揭露", key="check_scope_"+fp)]
        reviewer = st.text_input("覆核人", placeholder="輸入本次覆核人名稱", max_chars=80, key="reviewer_"+fp)
        confirmed = st.form_submit_button("確認並凍結本版，產生 PDF", type="primary")
    if confirmed:
        if not all(checks):
            st.error("請完成三項覆核確認後再凍結版本。")
        elif edited != st.session_state.report_narratives:
            st.error("上方報告文字尚未儲存，請先儲存文字，再覆核目前版本。")
        else:
            try:
                with st.spinner("正在產生 PDF 與保存盤查快照…"):
                    st.session_state.reviewed_report = freeze_report(st.session_state.inventory_rows, st.session_state.report_narratives,
                        st.session_state.source_info, payload, reviewer, st.session_state.audit_log, st.session_state.revision)
                st.success("已保存覆核版本。請至「PDF 預覽與輸出」檢視及下載。")
            except (ValueError, OSError) as exc:
                st.error(str(exc))


def render_output():
    st.subheader("檢視已覆核的 PDF")
    record = st.session_state.reviewed_report
    if not record or record["fingerprint"] != current_fingerprint():
        st.info("目前內容尚未完成覆核，或覆核後已有變動。請至「報告編輯與覆核」確認並凍結本版，再產生 PDF。之前的輸出仍保留於專案 exports 資料夾。")
        return
    content = Path(record["pdf_path"]).read_bytes()
    st.success(f"已完成內部人工覆核 · {record['reviewer']} · {record['time']}")
    left, right = st.columns([1, 3])
    with left:
        st.write("版本：", record["version"])
        st.caption("資料與文字已凍結。後續修改不會覆寫這份 PDF；須重新覆核並產生新版本。")
        st.download_button("下載已覆核 PDF", content, f"114年_模擬企業盤查報告_{record['version']}.pdf", "application/pdf", type="primary")
        st.download_button("下載本版盤查快照", (Path(record["directory"])/"盤查快照.json").read_bytes(), "盤查快照.json", "application/json")
        st.caption("本機保存位置：" + record["directory"])
    with right:
        render_pdf(content, "已覆核模擬報告")
