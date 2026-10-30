@echo off
if not exist "%~dp0app\ComfyUI\venv\Scripts\python.exe" (
  echo ComfyUI is not installed. Run install.bat first.
  pause
  exit /b 1
)
cd /d "%~dp0app\ComfyUI"
"venv\Scripts\python.exe" main.py --extra-model-paths-config "%~dp0config\extra_model_paths.yaml" --output-directory "%~dp0outputs" --auto-launch
pause
