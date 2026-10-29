"""Continuous local PDF preview with a single scrollable document surface."""
import base64
from html import escape

import pymupdf
import streamlit as st
import streamlit.components.v1 as components


@st.cache_data(show_spinner=False, max_entries=5)
def document_html(content, title):
    pages = []
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        count = len(pdf)
        for index, page in enumerate(pdf):
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
            encoded = base64.b64encode(pixmap.tobytes("jpeg", jpg_quality=82)).decode("ascii")
            pages.append(
                f'<figure aria-label="第 {index+1} 頁，共 {count} 頁">'
                f'<img src="data:image/jpeg;base64,{encoded}" width="{pixmap.width}" height="{pixmap.height}" '
                f'loading="{"eager" if index == 0 else "lazy"}" alt="{escape(title, quote=True)} 第 {index+1} 頁">'
                f'<figcaption>第 {index+1} 頁／共 {count} 頁</figcaption></figure>'
            )
    return f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><style>
      *{{box-sizing:border-box}}html,body{{margin:0;height:100%;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#4d6357}}
      .viewer{{height:860px;border:1px solid #dce4dd;border-radius:9px;overflow:hidden;background:#e8ece8}}
      header{{height:42px;padding:12px 16px;background:#f6f8f5;border-bottom:1px solid #dce4dd;font-size:12px;display:flex;justify-content:space-between;gap:12px}}
      header span{{color:#809084;font-size:11px}}main{{height:calc(100% - 42px);overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;padding:20px;scrollbar-gutter:stable}}
      main:focus-visible{{outline:2px solid #6f9b83;outline-offset:-2px}}figure{{margin:0 auto 22px;max-width:1040px}}
      img{{width:100%;height:auto;display:block;background:white;box-shadow:0 2px 9px #233b291a}}
      figcaption{{padding-top:8px;text-align:center;font-size:11px;color:#78867d}}
      @media(max-width:650px){{main{{padding:10px}}header span{{display:none}}}}
      </style></head><body><div class="viewer"><header>{escape(title)}<span>連續預覽 · 共 {count} 頁 · 直接捲動閱讀</span></header>
      <main tabindex="0" role="document" aria-label="{escape(title, quote=True)}，連續頁面預覽">{''.join(pages)}</main></div></body></html>'''


def render_pdf(content, title):
    with st.spinner("正在載入文件預覽…"):
        html = document_html(content, title)
    components.html(html, height=864, scrolling=False)
