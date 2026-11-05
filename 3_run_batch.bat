@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "DET_ARGS="
if exist "yolo11n.onnx" set DET_ARGS=--detector onnx --model yolo11n.onnx
echo 正在逐支分析影片，影片多的話需要一些時間...
py -m pet_vision batch videos --out output\batch %DET_ARGS%
if errorlevel 1 goto fail
start "" "output\batch\batch_report.xlsx"
echo 完成！請把 output\batch\batch_report.xlsx 傳給 Claude。
pause
exit /b 0
:fail
echo 執行失敗，請把這個視窗截圖給 Claude。
pause
exit /b 1
