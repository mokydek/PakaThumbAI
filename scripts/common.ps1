# Общие пути и функции для скриптов PakaThumbAI
$Root     = Split-Path -Parent $PSScriptRoot
$AppDir   = Join-Path $Root "app"
$ComfyDir = Join-Path $AppDir "ComfyUI"
$KohyaDir = Join-Path $AppDir "sd-scripts"
$ComfyPy  = Join-Path $ComfyDir "venv\Scripts\python.exe"
$KohyaPy  = Join-Path $KohyaDir "venv\Scripts\python.exe"

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }

function Fail($text) {
    Write-Host ""
    Write-Host "ОШИБКА: $text" -ForegroundColor Red
    exit 1
}

function Check($what) { if ($LASTEXITCODE -ne 0) { Fail "Не получилось: $what" } }

function Get-Gpu {
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $smi) { Fail "Не найден nvidia-smi. Установи драйвер NVIDIA: https://www.nvidia.com/drivers" }
    $line = (& nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits | Select-Object -First 1)
    $p = $line.Split(",") | ForEach-Object { $_.Trim() }
    [pscustomobject]@{ Name = $p[0]; VramMb = [int]$p[1]; Driver = $p[2] }
}

function Get-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $local = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path $local) { return $local }
    return $null
}

function Get-Repo($url, $innerName, $dest) {
    if (Test-Path (Join-Path $dest "README.md")) { Write-Host "   Уже есть: $dest"; return }
    $zip = Join-Path $AppDir "$innerName.zip"
    & curl.exe -L --fail --retry 5 -o $zip $url
    Check "скачивание $url"
    $tmp = Join-Path $AppDir "_unpack"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive -Path $zip -DestinationPath $tmp
    Move-Item (Join-Path $tmp $innerName) $dest
    Remove-Item -Recurse -Force $tmp, $zip
}
