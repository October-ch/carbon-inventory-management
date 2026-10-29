#!/bin/zsh
cd "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print '請先依 README.md 建立 .venv 並安裝 requirements.txt。'
  read '?按 Enter 關閉'
  exit 1
fi
exec .venv/bin/python -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
