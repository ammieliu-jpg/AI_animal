@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -m pet_vision init videos
if errorlevel 1 goto fail
echo.
echo 已建立 videos 資料夾與兩個表格：sources.csv（來源）、labels.csv（標註）
echo 請把下載的影片放進 videos 資料夾，並在 sources.csv 填好每支影片的來源網址與授權。
start "" "videos"
pause
exit /b 0
:fail
echo 執行失敗，請把這個視窗截圖給 Claude。
pause
exit /b 1
