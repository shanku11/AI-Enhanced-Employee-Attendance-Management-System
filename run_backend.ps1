$Python = "C:\Users\kummu srinivas\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
Set-Location "$PSScriptRoot\Backend"
& $Python -m uvicorn main:app --host 127.0.0.1 --port 5000
