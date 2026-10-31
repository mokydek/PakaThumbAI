# PakaThumbAI - обучение своей LoRA на картинках из папки dataset
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$LogName = "train"
. "$PSScriptRoot\common.ps1"
Set-Location $Root

if (-not (Test-Path $KohyaPy)) { Fail "sd-scripts не установлен. Сначала запусти install.bat" }
$model = Join-Path $Root "models\checkpoints\DreamShaper_8_pruned.safetensors"
if (-not (Test-Path $model)) { Fail "Нет базовой модели. Запусти install.bat ещё раз" }

$images = @(Get-ChildItem (Join-Path $Root "dataset") -File |
    Where-Object { $_.Extension -match '^\.(png|jpe?g|webp)$' })
if ($images.Count -lt 5) {
    Fail ("В папке dataset {0} картинок, нужно хотя бы 5 (лучше 20-50)" -f $images.Count)
}

# ComfyUI в фоне держит видеопамять - закрываем его на время обучения
$comfy = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*ComfyUI*main.py*" })
if ($comfy.Count -gt 0) {
    Write-Host "   Закрываю ComfyUI, чтобы освободить видеопамять"
    $comfy | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
}

$extra = @()
$gpu = Get-Gpu
if ($gpu.VramMb -lt 6000) {
    # 4 ГБ: учим только U-Net и делаем LoRA поменьше, чтобы влезть в память
    $extra += @("--network_train_unet_only", "--network_dim", "16", "--network_alpha", "8")
}

$steps = $images.Count * 10 * 10
Step ("Обучение: {0} картинок, ~{1} шагов, {2} ({3} МБ)" -f $images.Count, $steps, $gpu.Name, $gpu.VramMb)
Write-Host "   Результат: models\loras\pakathumb.safetensors (промежуточные - каждые 2 эпохи)"

# вывод обучения идёт и в окно, и в app\train.log
$ErrorActionPreference = "Continue"
& $KohyaPy (Join-Path $KohyaDir "train_network.py") --config_file (Join-Path $Root "config\train_lora.toml") @extra @args 2>&1 |
    ForEach-Object { "$_" } | Tee-Object -FilePath $LogFile -Append
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($code -ne 0) { Fail "обучение LoRA (подробности в app\train.log)" }

Write-Host ""
Write-Host "Готово! LoRA сохранена в models\loras\pakathumb.safetensors" -ForegroundColor Green
Log "TRAIN OK"
Write-Host "generate.bat теперь использует её автоматически."
