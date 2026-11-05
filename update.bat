@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在下載最新版程式...
git pull
if errorlevel 1 (
  echo 更新失敗，請把這個視窗截圖給 Claude。
) else (
  echo 更新完成！
)
pause
