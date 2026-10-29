#!/bin/zsh
cd "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print '請先依 README.md 建立 .venv 並安裝 requirements.txt。'
  read '?按 Enter 關閉'
  exit 1
fi
URL='http://127.0.0.1:8501'
.venv/bin/python -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true &
streamlit_pid=$!

# Wait until Streamlit is ready, then explicitly open the local app in the browser.
for attempt in {1..30}; do
  if curl --fail --silent "$URL/_stcore/health" >/dev/null; then
    open "$URL"
    break
  fi
  sleep 1
done

wait "$streamlit_pid"
