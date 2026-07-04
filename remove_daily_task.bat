@echo off
setlocal
schtasks /Delete /F /TN "Topic22_Stockguy_DailyUpdate"
endlocal
