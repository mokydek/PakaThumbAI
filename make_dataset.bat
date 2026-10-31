@echo off
if not exist "%~dp0app\ComfyUI\venv\Scripts\python.exe" (
  echo ComfyUI is not installed. Run install.bat first.
  pause
  exit /b 1
)
"%~dp0app\ComfyUI\venv\Scripts\python.exe" "%~dp0tools\make_dataset.py" %*
pause
