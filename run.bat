@echo off
cd /d "D:\Projects\Gradious\Backend"
"C:\Users\kummu srinivas\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 5000 > out.log 2>&1
