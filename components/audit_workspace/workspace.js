/* A small, dependency-free Streamlit v1 component. No access to parent DOM. */
(() => {
  "use strict";
  let data = null;
  let currentMetric = "total";
  let currentSheet = "用電底稿";
  let focusedRow = null;
  let onlyRelated = false;
  let query = "";
  let pending = false;
  let revision = null;
  const $ = (selector) => document.querySelector(selector);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt = (value, digits=2) => Number(value).toLocaleString("en-US", {minimumFractionDigits:digits, maximumFractionDigits:digits});

  function post(type, payload={}) {
    window.parent.postMessage({isStreamlitMessage:true, type, ...payload}, "*");
  }
  function emit(event) {
    post("streamlit:setComponentValue", {value:{...event, event_id:crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`}, dataType:"json"});
  }
  function resize() { post("streamlit:setFrameHeight", {height:document.documentElement.scrollHeight}); }
  function status(text, error=false) { $("#status").textContent=text; $("#status").classList.toggle("error", error); }
  function activeMetric() { return data.metrics[currentMetric] || data.metrics.total; }
  function relatedIds() { return new Set(activeMetric().rows); }

  function paintLineage() {
    const m=activeMetric();
    const sheets=data.sheets.filter(sheet => data.rows.some(r=>r.sheet===sheet && m.rows.includes(r.row_id)));
    $("#lineage").innerHTML=`<div class="lineage-top"><span class="lineage-label">↳ ${esc(m.label)}</span><span>${m.rows.length} 筆來源列</span></div><div class="lineage-value">${esc(m.value)} <small>${esc(m.unit)}</small></div><div class="lineage-formula">${esc(m.formula)}</div><div class="dependency-chips">${sheets.map(sheet=>`<button data-sheet-link="${esc(sheet)}">${esc(sheet)} · ${data.rows.filter(r=>r.sheet===sheet && m.rows.includes(r.row_id)).length} 筆 ↗</button>`).join("")}</div>`;
    $("#sheet-nav").innerHTML=data.sheets.map(sheet=>{
      const count=data.rows.filter(r=>r.sheet===sheet && m.rows.includes(r.row_id)).length;
      return `<button data-sheet="${esc(sheet)}" class="${sheet===currentSheet?'active ':''}${count?'has-related':''}" aria-pressed="${sheet===currentSheet}">${esc(sheet.replace("底稿",""))}<span class="count">${count||""}</span></button>`;
    }).join("");
    document.querySelectorAll(".report-number").forEach(el=>{
      const active=el.dataset.metric===currentMetric;
      el.classList.toggle("active",active); el.setAttribute("aria-pressed",String(active));
    });
  }

  function paintRows() {
    const ids=relatedIds();
    const rows=data.rows.filter(r=>r.sheet===currentSheet && (!onlyRelated || ids.has(r.row_id)) && (!query || [r.row_id,r.month,r.item,r.document,r.activity,r.factor].some(v=>String(v).toLowerCase().includes(query.toLowerCase()))));
    const m=activeMetric();
    $("#source-body").innerHTML=rows.length ? rows.map(r=>`<tr data-row="${esc(r.row_id)}" tabindex="0" class="${ids.has(r.row_id)?'related ':''}${r.row_id===focusedRow?'focused':''}" aria-label="${esc(r.row_id)} ${esc(r.item)}"><td>${esc(r.row_id)}<small>ISO ${esc(r.category)}</small></td><td>${esc(r.month)}<small>${esc(r.item)}</small></td><td data-field="activity" class="${ids.has(r.row_id)&&m.field==='activity'?'target-cell':''}" title="雙擊或按 Enter 編輯活動量" tabindex="0">${fmt(r.activity)}<small>${esc(r.unit)}</small></td><td data-field="factor" class="${ids.has(r.row_id)&&m.field==='factor'?'target-cell':''}" title="雙擊或按 Enter 編輯係數" tabindex="0">${fmt(r.factor,4)}</td><td class="${ids.has(r.row_id)&&m.field==='emissions'?'target-cell':''}">${esc(r.emissions)}</td></tr>`).join("") : '<tr><td colspan="5" class="empty">目前條件沒有資料。點擊報告數字會清除搜尋並定位。</td></tr>';
    $("#row-count").textContent=`${data.rows.length} 筆模擬資料`;
    $("#only-related").classList.toggle("active",onlyRelated);
    $("#only-related").setAttribute("aria-pressed",String(onlyRelated));
  }

  function paintEvidence() {
    const r=data.rows.find(r=>r.row_id===focusedRow);
    if(!r) { $("#evidence").innerHTML='<div class="evidence-title">來源憑證與計算明細</div><div class="evidence-grid"><span class="value">點選底稿列查看來源、單位與係數版本。</span></div>'; return; }
    $("#evidence").innerHTML=`<div class="evidence-title">來源明細 · ${esc(r.row_id)}</div><div class="evidence-grid">${r.source_book?`<span class="label">Excel位置</span><span class="value">${esc(r.source_book)} ／ ${esc(r.source_sheet)}!第 ${esc(r.source_excel_row)} 列</span>`:''}<span class="label">對應憑證</span><span class="value">${esc(r.document)}</span><span class="label">排放分類</span><span class="value">ISO 類別 ${esc(r.category)} ｜ ${esc(r.scope)}</span><span class="label">計算公式</span><span class="value">${esc(r.activity)} ${esc(r.unit)} × ${esc(r.factor)} ${esc(r.factor_unit)} ÷ 1,000 ＝ ${esc(r.emissions)} tCO₂e</span><span class="label">係數版本</span><span class="value">${esc(r.factor_version)} ｜ ${esc(r.source)}</span></div>`;
  }

  function scrollToRow() {
    requestAnimationFrame(()=>{
      const row=Array.from(document.querySelectorAll("#source-body tr")).find(el=>el.dataset.row===focusedRow);
      if(row) {
        const scroller=$("#source-scroll");
        const offset=row.getBoundingClientRect().top-scroller.getBoundingClientRect().top+scroller.scrollTop-scroller.clientHeight/2+row.clientHeight/2;
        scroller.scrollTo({top:Math.max(0,offset),behavior:"smooth"});
      }
      if(window.innerWidth<900) $(".source-panel").scrollIntoView({behavior:"smooth",block:"start"});
      resize();
    });
  }

  function chooseMetric(key, notify=true) {
    if(!data.metrics[key]) return;
    currentMetric=key;
    query=""; $("#search").value="";
    const m=activeMetric();
    const first=data.rows.find(r=>m.rows.includes(r.row_id));
    // A report click always reveals a dependency, even if the user was on another sheet.
    if(first) {currentSheet=first.sheet; focusedRow=first.row_id;}
    paintLineage(); paintRows(); paintEvidence(); scrollToRow();
    status(`已定位「${m.label}」→ ${m.rows.length} 筆來源列；跨表來源可用藍色標籤切換。`);
    if(notify) emit({type:"select",metric_id:key});
  }

  function switchSheet(sheet) {
    if(!data.sheets.includes(sheet)) return;
    currentSheet=sheet; query=""; $("#search").value="";
    const rows=data.rows.filter(r=>r.sheet===sheet);
    focusedRow=(rows.find(r=>relatedIds().has(r.row_id))||rows[0]||{}).row_id;
    paintLineage(); paintRows(); paintEvidence(); scrollToRow();
  }

  function beginEdit(cell) {
    if(pending || cell.querySelector("input")) return;
    const row=data.rows.find(r=>r.row_id===cell.closest("tr").dataset.row);
    const field=cell.dataset.field;
    if(!row || !["activity","factor"].includes(field)) return;
    const input=document.createElement("input"); input.type="number"; input.min="0"; input.max="1000000000000"; input.step="any"; input.value=row[field]; input.className="cell-input"; input.setAttribute("aria-label",`${row.row_id} ${field==='activity'?'活動量':'係數'}`);
    cell.replaceChildren(input); input.focus(); input.select();
    let finished=false;
    function cancel() {if(finished)return; finished=true; paintRows();}
    function commit() {
      if(finished)return;
      if(input.value.trim()==="" || !input.checkValidity() || !Number.isFinite(Number(input.value))) {
        status("請輸入 0 至 1,000,000,000,000 之間的有效數字。",true); input.focus(); return;
      }
      finished=true;
      if(Number(input.value)===Number(row[field])) {paintRows();return;}
      pending=true;
      $("#source-body").classList.add("pending");
      status("正在依底稿重算報告…");
      emit({type:"edit",row_id:row.row_id,field,value:input.value});
    }
    input.addEventListener("keydown",e=>{e.stopPropagation(); if(e.key==="Enter")commit(); if(e.key==="Escape")cancel();});
    input.addEventListener("blur",commit);
  }

  document.addEventListener("click",e=>{
    const metric=e.target.closest("[data-metric]");
    if(metric) {chooseMetric(metric.dataset.metric);return;}
    const sheet=e.target.closest("[data-sheet], [data-sheet-link]");
    if(sheet) {switchSheet(sheet.dataset.sheet||sheet.dataset.sheetLink);return;}
    const section=e.target.closest("[data-section]");
    if(section) {
      const target=document.getElementById(section.dataset.section);
      if(target) $("#report-scroll").scrollTo({top:target.getBoundingClientRect().top-$("#report-scroll").getBoundingClientRect().top+$("#report-scroll").scrollTop-20,behavior:"smooth"});
      return;
    }
    const row=e.target.closest("#source-body tr[data-row]");
    if(row && !e.target.closest("input")) {focusedRow=row.dataset.row;document.querySelectorAll("#source-body tr").forEach(el=>el.classList.toggle("focused",el===row));paintEvidence();resize();}
  });
  $("#source-body").addEventListener("dblclick",e=>{const cell=e.target.closest("td[data-field]");if(cell)beginEdit(cell);});
  $("#source-body").addEventListener("keydown",e=>{if(e.key==="Enter" && !e.target.closest("input")){const cell=e.target.closest("td[data-field]");if(cell){e.preventDefault();beginEdit(cell);}}});
  $("#search").addEventListener("input",e=>{query=e.target.value;paintRows();});
  $("#only-related").onclick=()=>{onlyRelated=!onlyRelated;paintRows();};

  window.addEventListener("message",event=>{
    if(event.source!==window.parent || event.data?.type!=="streamlit:render") return;
    const next=event.data.args.payload;
    if(!next) return;
    const initial=data===null;
    const changed=revision!==next.revision;
    const leftScroll=$("#source-scroll").scrollTop;
    const rightScroll=$("#report-scroll").scrollTop;
    data=next;
    if(pending) {pending=false;$("#source-body").classList.remove("pending");}
    if(initial || changed) {
      $("#report-content").innerHTML=data.report;
      revision=data.revision;
      if(initial) {chooseMetric(data.selected,false);}
      else {paintLineage();paintRows();paintEvidence();$("#source-scroll").scrollTop=leftScroll;$("#report-scroll").scrollTop=rightScroll;status("底稿已更新，報告內文、表格與占比已重新計算。");}
    }
    $("#revision").textContent=`工作階段修訂 ${data.revision}`;
    if(data.error)status(data.error,true);
    resize();
  });
  window.addEventListener("resize",resize);
  new ResizeObserver(resize).observe(document.body);
  post("streamlit:componentReady", {apiVersion:1});
  resize();
})();
