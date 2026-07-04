@echo off
setlocal
cd /d "%~dp0"
if not exist .git (
  echo No git repository found at %CD%.
  exit /b 1
)
git add docs output project_data\cleaned project_data\benchmarks
git commit -m "Update stockguy analysis site" --allow-empty
git push
endlocal
