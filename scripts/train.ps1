# PakaThumbAI - обучение своей LoRA на картинках из папки dataset
# train.bat -Dataset dataset_horror -Name pakahorror  -> другая папка и имя LoRA
# train.bat -Epochs 6                                -> другое число эпох (по умолчанию 10)
param(
    [string]$Dataset = "dataset",
    [string]$Name = "pakathumb",
    [int]$Epochs = 0,
    [Parameter(ValueFromRemainingArguments = $true)] $Rest
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$LogName = "train"
. "$PSScriptRoot\common.ps1"
Set-Location $Root

if (-not (Test-Path $KohyaPy)) { Fail "sd-scripts не установлен. Сначала запусти install.bat" }
$model = Join-Path $Root "models\checkpoints\DreamShaper_8_pruned.safetensors"
if (-not (Test-Path $model)) { Fail "Нет базовой модели. Запусти install.bat ещё раз" }

$DatasetDir = Join-Path $Root $Dataset
if (-not (Test-Path $DatasetDir)) { Fail "Нет папки $Dataset" }
$images = @(Get-ChildItem $DatasetDir -File |
    Where-Object { $_.Extension -match '^\.(png|jpe?g|webp)$' })
if ($images.Count -lt 5) {
    Fail ("В папке {0} {1} картинок, нужно хотя бы 5 (лучше 20-50)" -f $Dataset, $images.Count)
}

# ComfyUI в фоне держит видеопамять - закрываем его на время обучения
$comfy = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*ComfyUI*main.py*" })
if ($comfy.Count -gt 0) {
    Write-Host "   Закрываю ComfyUI, чтобы освободить видеопамять"
    $comfy | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
}

# зависшее прошлое обучение (например после сна ПК) держит видеопамять - закрываем
$stale = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*train_network.py*" })
if ($stale.Count -gt 0) {
    Write-Host "   Закрываю прошлое незавершённое обучение"
    $stale | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Start-Sleep -Seconds 3
}

# пока идёт обучение, Windows не уходит в сон по бездействию (сбрасывается, когда окно закроется)
Add-Type -Namespace PakaThumb -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
[PakaThumb.Power]::SetThreadExecutionState([uint32]"0x80000001") | Out-Null

$extra = @()
$gpu = Get-Gpu
if ($gpu.VramMb -lt 6000) {
    # 4 ГБ: учим только U-Net и делаем LoRA поменьше, чтобы влезть в память
    $extra += @("--network_train_unet_only", "--network_dim", "16", "--network_alpha", "8")
}

if ($Epochs -gt 0) { $extra += @("--max_train_epochs", "$Epochs") } else { $Epochs = 10 }
$steps = $images.Count * 10 * $Epochs
Step ("Обучение: {0} картинок, ~{1} шагов, {2} ({3} МБ)" -f $images.Count, $steps, $gpu.Name, $gpu.VramMb)
Write-Host "   Результат: models\loras\$Name.safetensors (промежуточные - каждые 2 эпохи)"

# конфиг датасета из шаблона config\dataset.toml, но с нужной папкой
$dsConfig = Join-Path $AppDir "dataset_$Name.toml"
$tpl = Get-Content (Join-Path $Root "config\dataset.toml") -Raw -Encoding UTF8
$tpl = $tpl.Replace('image_dir = "dataset"', ('image_dir = "{0}"' -f ($Dataset -replace "\\", "/")))
[IO.File]::WriteAllText($dsConfig, $tpl)

# прогресс - в окне, сообщения обучения - в app\train_python.log
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$pyLog = Join-Path $AppDir "train_python.log"
& $KohyaPy (Join-Path $KohyaDir "train_network.py") --config_file (Join-Path $Root "config\train_lora.toml") --console_log_file $pyLog `
    --dataset_config $dsConfig --output_name $Name @extra @Rest
Check "обучение LoRA (подробности в app\train_python.log)"

Write-Host ""
Write-Host "Готово! LoRA сохранена в models\loras\$Name.safetensors" -ForegroundColor Green
Log "TRAIN OK"
Write-Host ("Генерация с ней: generate.bat `"промпт`" --lora {0}" -f $Name)
