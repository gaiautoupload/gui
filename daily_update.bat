@echo off
setlocal
cd /d "%~dp0"
"C:\Users\pioterlee\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts\stockguy_pipeline.py
endlocal
