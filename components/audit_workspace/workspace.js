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
  let uiLanguage = null;
  const $ = (selector) => document.querySelector(selector);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt = (value, digits=2) => Number(value).toLocaleString("en-US", {minimumFractionDigits:digits, maximumFractionDigits:digits});
  const EN_SHEETS={"用電底稿":"Electricity","燃料底稿":"Fuel","冷媒底稿":"Refrigerants","差旅底稿":"Business travel"};
  const EN_ITEMS={"辦公室外購電力":"Purchased electricity","公務車汽油":"Company vehicle gasoline","空調冷媒補充（示範視為逸散量）":"AC refrigerant replenishment (assumed leakage for demo)","員工商務鐵路差旅":"Employee business rail travel"};
  const tx=(zh,en)=>data?.language==="en"?en:zh;
  const displayItem=(item)=>data?.language==="en"?(EN_ITEMS[item]||item):item;
  const displayMonth=(month)=>data?.language==="en"?month.replace(/^114\//,"2025/"):month;
  const displayDoc=(doc)=>data?.language==="en"?doc.replace("模擬電費單","Simulated electricity bill").replace("模擬汽油單據","Simulated gasoline receipt").replace("模擬冷媒維修單","Simulated refrigerant service record").replace("模擬差旅紀錄","Simulated travel record"):doc;
  function applyLocale(){
    const en=data?.language==="en";
    document.documentElement.lang=en?"en":"zh-Hant";
    const pairs=[["資料與報告即時連動","Workpapers and report are linked"],["點選右側藍色數字，追溯左側來源；雙擊底稿活動量或係數可修改。","Select a blue figure to trace its sources; double-click activity data or a factor to edit."],["資料來源與計算底稿","Source data and workpapers"],["底稿工作表","Workpaper tabs"],["搜尋月份、項目或憑證編號","Search period, item, or document ID"],["搜尋底稿","Search workpapers"],["只看關聯列","Related rows only"],["底稿列","Workpaper row"],["期間／項目","Period / item"],["活動量","Activity data"],["係數","Factor"],["排放量","Emissions"],["藍色：報告引用列","Blue: rows cited by report"],["互動草稿","Interactive draft"],["排放量計算","Emissions"],["邊界與鑑別","Boundary & sources"],["量化方法","Methodology"],["數據明細","Details"],["準備載入計算底稿…","Loading workpapers…"]].map(([zh,enText])=>en?[zh,enText]:[enText,zh]);
    document.querySelectorAll("#workspace *").forEach(el=>{if(el.children.length===0){let value=el.textContent;for(const [from,to] of pairs)value=value.replaceAll(from,to);if(value!==el.textContent)el.textContent=value;}});
    const guide=document.querySelector(".workspace-guide"); if(guide){guide.querySelector("strong").textContent=tx("資料與報告即時連動","Workpapers and report are linked");guide.querySelectorAll("span")[1].textContent=tx("點選右側藍色數字，追溯左側來源；雙擊底稿活動量或係數可修改。","Select a blue figure to trace its sources; double-click activity data or a factor to edit.");}
    const search=$("#search"); if(search){search.placeholder=tx("搜尋月份、項目或憑證編號","Search period, item, or document ID");search.setAttribute("aria-label",tx("搜尋底稿","Search workpapers"));}
    const headers=document.querySelectorAll(".workpaper thead th");if(headers.length){headers[0].textContent=tx("底稿列","Workpaper row");headers[1].textContent=tx("期間／項目","Period / item");headers[2].textContent=tx("活動量","Activity data");headers[3].textContent=tx("係數","Factor");headers[4].innerHTML=tx("排放量<br>tCO₂e","Emissions<br>tCO₂e");}
    const heads=document.querySelectorAll(".source-panel .panel-head h2,.report-panel .panel-head h2");
    if(heads.length){heads[0].textContent=tx("資料來源與計算底稿","Source data and workpapers");heads[1].textContent=tx("114 年溫室氣體盤查報告書","2025 GHG Inventory Report");}
    const nav=document.querySelectorAll(".report-nav button");["排放量計算","邊界與鑑別","量化方法","數據明細"].forEach((s,i)=>{if(nav[i])nav[i].textContent=tx(s,["Emissions","Boundary & sources","Methodology","Details"][i]);});
  }

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
    $("#lineage").innerHTML=`<div class="lineage-top"><span class="lineage-label">↳ ${esc(m.label)}</span><span>${m.rows.length} ${tx("筆來源列","source rows")}</span></div><div class="lineage-value">${esc(m.value)} <small>${esc(m.unit)}</small></div><div class="lineage-formula">${esc(m.formula)}</div><div class="dependency-chips">${sheets.map(sheet=>`<button data-sheet-link="${esc(sheet)}">${esc(EN_SHEETS[sheet]||sheet)} · ${data.rows.filter(r=>r.sheet===sheet && m.rows.includes(r.row_id)).length} ${tx("筆","rows")} ↗</button>`).join("")}</div>`;
    $("#sheet-nav").innerHTML=data.sheets.map(sheet=>{
      const count=data.rows.filter(r=>r.sheet===sheet && m.rows.includes(r.row_id)).length;
      return `<button data-sheet="${esc(sheet)}" class="${sheet===currentSheet?'active ':''}${count?'has-related':''}" aria-pressed="${sheet===currentSheet}">${esc(EN_SHEETS[sheet]||sheet.replace("底稿",""))}<span class="count">${count||""}</span></button>`;
    }).join("");
    document.querySelectorAll(".report-number").forEach(el=>{
      const active=el.dataset.metric===currentMetric;
      el.classList.toggle("active",active); el.setAttribute("aria-pressed",String(active));
    });
  }

  function paintRows() {
    const ids=relatedIds();
    const rows=data.rows.filter(r=>r.sheet===currentSheet && (!onlyRelated || ids.has(r.row_id)) && (!query || [r.row_id,r.month,displayMonth(r.month),r.item,displayItem(r.item),r.document,displayDoc(r.document),r.activity,r.factor].some(v=>String(v).toLowerCase().includes(query.toLowerCase()))));
    const m=activeMetric();
    $("#source-body").innerHTML=rows.length ? rows.map(r=>`<tr data-row="${esc(r.row_id)}" tabindex="0" class="${ids.has(r.row_id)?'related ':''}${r.row_id===focusedRow?'focused':''}" aria-label="${esc(r.row_id)} ${esc(displayItem(r.item))}"><td>${esc(r.row_id)}<small>ISO ${esc(r.category)}</small></td><td>${esc(displayMonth(r.month))}<small>${esc(displayItem(r.item))}</small></td><td data-field="activity" class="${ids.has(r.row_id)&&m.field==='activity'?'target-cell':''}" title="${tx("雙擊或按 Enter 編輯活動量","Double-click or press Enter to edit activity data")}" tabindex="0">${fmt(r.activity)}<small>${esc(r.unit)}</small></td><td data-field="factor" class="${ids.has(r.row_id)&&m.field==='factor'?'target-cell':''}" title="${tx("雙擊或按 Enter 編輯係數","Double-click or press Enter to edit factor")}" tabindex="0">${fmt(r.factor,4)}</td><td class="${ids.has(r.row_id)&&m.field==='emissions'?'target-cell':''}">${esc(r.emissions)}</td></tr>`).join("") : `<tr><td colspan="5" class="empty">${tx("目前條件沒有資料。點擊報告數字會清除搜尋並定位。","No rows match. Select a report figure to clear the search and locate its sources.")}</td></tr>`;
    $("#row-count").textContent=`${data.rows.length} ${tx("筆模擬資料","demo rows")}`;
    $("#only-related").classList.toggle("active",onlyRelated);
    $("#only-related").setAttribute("aria-pressed",String(onlyRelated));
  }

  function paintEvidence() {
    const r=data.rows.find(r=>r.row_id===focusedRow);
    if(!r) { $("#evidence").innerHTML=`<div class="evidence-title">${tx("來源憑證與計算明細","Source evidence and calculation")}</div><div class="evidence-grid"><span class="value">${tx("點選底稿列查看來源、單位與係數版本。","Select a workpaper row to view source, units, and factor version.")}</span></div>`; return; }
    const sourceText=data.language==="en"?r.source.replace("自行模擬，非官方數據／無實體憑證","Simulated; not official data; no physical evidence"):r.source;
    $("#evidence").innerHTML=`<div class="evidence-title">${tx("來源明細","Source details")} · ${esc(r.row_id)}</div><div class="evidence-grid">${r.source_book?`<span class="label">${tx("Excel位置","Excel location")}</span><span class="value">${esc(r.source_book)} / ${esc(EN_SHEETS[r.source_sheet]||r.source_sheet)} · row ${esc(r.source_excel_row)}</span>`:''}<span class="label">${tx("對應憑證","Source document")}</span><span class="value">${esc(displayDoc(r.document))}</span><span class="label">${tx("排放分類","Emission category")}</span><span class="value">ISO ${tx("類別","Category")} ${esc(r.category)} | ${esc(r.scope)}</span><span class="label">${tx("計算公式","Calculation formula")}</span><span class="value">${esc(r.activity)} ${esc(r.unit)} × ${esc(r.factor)} ${esc(r.factor_unit)} ÷ 1,000 = ${esc(r.emissions)} tCO₂e</span><span class="label">${tx("係數版本","Factor version")}</span><span class="value">${esc(r.factor_version)} | ${esc(sourceText)}</span></div>`;
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
    status(data.language==="en"?`Located “${m.label}” → ${m.rows.length} source rows. Use the blue tags to switch workpapers.`:`已定位「${m.label}」→ ${m.rows.length} 筆來源列；跨表來源可用藍色標籤切換。`);
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
      status(tx("請輸入 0 至 1,000,000,000,000 之間的有效數字。","Enter a valid number from 0 to 1,000,000,000,000."),true); input.focus(); return;
      }
      finished=true;
      if(Number(input.value)===Number(row[field])) {paintRows();return;}
      pending=true;
      $("#source-body").classList.add("pending");
      status(tx("正在依底稿重算報告…","Recalculating the report from workpapers…"));
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
    const changed=revision!==next.revision || uiLanguage!==next.language;
    const leftScroll=$("#source-scroll").scrollTop;
    const rightScroll=$("#report-scroll").scrollTop;
    data=next;
    if(pending) {pending=false;$("#source-body").classList.remove("pending");}
    if(initial || changed) {
      applyLocale();
      $("#report-content").innerHTML=data.report;
      revision=data.revision;
      uiLanguage=data.language;
      if(initial) {chooseMetric(data.selected,false);}
      else {paintLineage();paintRows();paintEvidence();$("#source-scroll").scrollTop=leftScroll;$("#report-scroll").scrollTop=rightScroll;status(tx("底稿已更新，報告內文、表格與占比已重新計算。","Workpapers updated. Report text, tables, and shares were recalculated."));}
    }
    $("#revision").textContent=`${tx("工作階段修訂","Session revision")} ${data.revision}`;
    if(data.error)status(data.error,true);
    resize();
  });
  window.addEventListener("resize",resize);
  new ResizeObserver(resize).observe(document.body);
  post("streamlit:componentReady", {apiVersion:1});
  resize();
})();
