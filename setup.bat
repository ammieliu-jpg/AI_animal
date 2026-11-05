@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/3] 檢查 Python...
py --version
if errorlevel 1 (
  echo 找不到 Python，請先到 https://www.python.org/downloads/ 安裝，並勾選 Add python.exe to PATH
  pause
  exit /b 1
)
echo [2/3] 安裝需要的套件...
py -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo [3/3] 準備 YOLO 模型...
if exist yolo11n.onnx (
  echo 已經有 yolo11n.onnx，略過
) else (
  py -m pip install ultralytics
  if errorlevel 1 goto fail
  py -c "from ultralytics import YOLO; YOLO('yolo11n.pt').export(format='onnx')"
  if errorlevel 1 goto fail
)
echo.
echo 安裝完成！之後雙擊 run_demo.bat 就能跑 Demo。
pause
exit /b 0
:fail
echo.
echo 安裝失敗，請把這個視窗截圖給 Claude。
pause
exit /b 1
