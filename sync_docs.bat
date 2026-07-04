@echo off
setlocal
cd /d "%~dp0\.."
if not exist .git (
  echo No git repository found at %CD%.
  exit /b 1
)
git add projects\topic_22_stockguy_analysis\docs projects\topic_22_stockguy_analysis\output projects\topic_22_stockguy_analysis\project_data\cleaned
git commit -m "Update stockguy analysis site" --allow-empty
git push
endlocal
