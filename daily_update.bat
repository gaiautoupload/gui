@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" scripts\fetch_youtube_transcript.py --allow-missing
) else (
  echo .venv not found; skipping YouTube transcript fetch.
)
"C:\Users\pioterlee\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts\stockguy_pipeline.py
endlocal
