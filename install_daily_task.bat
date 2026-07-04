@echo off
setlocal
cd /d "%~dp0"
schtasks /Create /F /SC DAILY /ST 08:00 /TN "Topic22_Stockguy_DailyUpdate" /TR "\"%~dp0daily_update.bat\""
endlocal
