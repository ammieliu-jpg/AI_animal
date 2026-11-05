@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "VIDEO_ARGS="
set "DET_ARGS="
if exist "cat eating.mp4" if exist "cat_zones.json" set VIDEO_ARGS=--video "cat eating.mp4" --zones cat_zones.json
if exist "yolo11n.onnx" set DET_ARGS=--detector onnx --model yolo11n.onnx
echo 正在產生 Demo，影片越大越久，請稍候...
py -m petsentinel demo %VIDEO_ARGS% %DET_ARGS% --out output\demo
if errorlevel 1 (
  echo.
  echo 執行失敗，請把這個視窗截圖給 Claude。
  pause
  exit /b 1
)
start "" "output\demo\index.html"
echo 完成！已用瀏覽器打開 output\demo\index.html
pause
