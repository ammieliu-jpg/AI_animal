@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "MODEL_ARGS="
if exist "yolo11n.onnx" set MODEL_ARGS=--model yolo11n.onnx
py -m pet_vision prepare videos %MODEL_ARGS%
if errorlevel 1 goto fail
echo.
echo 每支影片的截圖在 videos\_snapshots；自動找到碗的影片已產生 _zones.json 草稿。
echo 請把截圖傳給 Claude，確認或補上區域（水碗、食碗、砂盆）。
start "" "videos\_snapshots"
pause
exit /b 0
:fail
echo 執行失敗，請把這個視窗截圖給 Claude。
pause
exit /b 1
