# PakaThumbAI - установка (ComfyUI + kohya sd-scripts + базовая модель)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$LogName = "install"
. "$PSScriptRoot\common.ps1"

$ComfyVersion = "0.43.2"
$KohyaVersion = "0.9.1"
$ModelUrl = "https://huggingface.co/lllyasviel/fav_models/resolve/main/fav/DreamShaper_8_pruned.safetensors"
$ModelFile = Join-Path $Root "models\checkpoints\DreamShaper_8_pruned.safetensors"

Step "1/6 Проверяю видеокарту NVIDIA"
$gpu = Get-Gpu
$info = "   {0} | {1} МБ видеопамяти | драйвер {2}" -f $gpu.Name, $gpu.VramMb, $gpu.Driver
Write-Host $info; Log $info
if ([double]$gpu.Driver -lt 580) {
    Fail ("Драйвер NVIDIA {0} слишком старый, нужен 580 или новее. Обнови: https://www.nvidia.com/drivers и запусти install.bat снова" -f $gpu.Driver)
}

Step "2/6 Проверяю uv (менеджер Python)"
$uv = Get-Uv
if (-not $uv) {
    Write-Host "   Ставлю uv..."
    & powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $uv = Get-Uv
    if (-not $uv) { Fail "Не удалось установить uv" }
}
Write-Host "   $uv"

Step "3/6 Скачиваю ComfyUI $ComfyVersion и sd-scripts $KohyaVersion"
New-Item -ItemType Directory -Force $AppDir | Out-Null
Get-Repo "https://github.com/comfyanonymous/ComfyUI/archive/refs/tags/v$ComfyVersion.zip" "ComfyUI-$ComfyVersion" $ComfyDir
Get-Repo "https://github.com/kohya-ss/sd-scripts/archive/refs/tags/v$KohyaVersion.zip" "sd-scripts-$KohyaVersion" $KohyaDir

Step "4/6 Ставлю Python-окружение для ComfyUI (генерация)"
if (-not (Test-Path $ComfyPy)) { & $uv venv --python 3.12 "$ComfyDir\venv"; Check "uv venv ComfyUI" }
& $uv pip install --python $ComfyPy torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
Check "torch для ComfyUI"
& $uv pip install --python $ComfyPy -r "$ComfyDir\requirements.txt"
Check "зависимости ComfyUI"

Step "5/6 Ставлю Python-окружение для обучения (kohya sd-scripts)"
if (-not (Test-Path $KohyaPy)) { & $uv venv --python 3.10 "$KohyaDir\venv"; Check "uv venv sd-scripts" }
& $uv pip install --python $KohyaPy torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu121
Check "torch для sd-scripts"
Push-Location $KohyaDir
& $uv pip install --python $KohyaPy "numpy<2" -r requirements.txt
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Fail "Не удалось поставить зависимости sd-scripts" }

Step "6/6 Скачиваю базовую модель DreamShaper 8 (~2 ГБ)"
if ((Test-Path $ModelFile) -and ((Get-Item $ModelFile).Length -gt 2000000000)) {
    Write-Host "   Уже скачана"
} else {
    & curl.exe -L --fail --retry 5 -C - -o $ModelFile $ModelUrl
    Check "скачивание модели"
}

Step "Проверка: видит ли PyTorch видеокарту"
foreach ($py in @($ComfyPy, $KohyaPy)) {
    $out = & $py -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
    Write-Host "   $out"; Log "   $out"
    if ($out -notmatch "True") { Fail "PyTorch не видит видеокарту ($py)" }
}

Write-Host ""
Write-Host "Готово! Дальше:" -ForegroundColor Green
Log "INSTALL OK"
Write-Host "  start.bat     - открыть ComfyUI в браузере"
Write-Host "  generate.bat  - сгенерировать thumbnail'ы из командной строки"
Write-Host "  train.bat     - обучить свой стиль (LoRA) на картинках из папки dataset"
