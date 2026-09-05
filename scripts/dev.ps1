$ErrorActionPreference='Stop'
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r apps\api\requirements.txt
npm install
Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','apps.api.aiopt_web.main:app','--reload','--host','127.0.0.1','--port','8000' -WindowStyle Hidden
npm run dev
