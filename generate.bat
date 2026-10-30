@echo off
if not exist "%~dp0app\ComfyUI\venv\Scripts\python.exe" (
  echo ComfyUI is not installed. Run install.bat first.
  exit /b 1
)
"%~dp0app\ComfyUI\venv\Scripts\python.exe" "%~dp0tools\generate.py" %*
