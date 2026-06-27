param(
    [switch]$SkipHardwareCheck,
    [switch]$SkipModelDownload
)

$ErrorActionPreference = "Stop"

function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }
function Write-Section { Write-Host ""; Write-Host "============================================" -ForegroundColor Cyan; Write-Host $args[0] -ForegroundColor Cyan; Write-Host "============================================" -ForegroundColor Cyan }

function Check-WindowsVersion {
    $os = Get-CimInstance -ClassName Win32_OperatingSystem
    Write-Info "Windows: $($os.Caption) $($os.Version)"
    $version = [Version]$os.Version
    if ($version.Major -lt 10) { Write-Warning "Windows 10 или новее рекомендуется" }
    else { Write-Success "Windows версия: $($version.Major).$($version.Minor)" }
}

function Check-RAM {
    $ram = (Get-CimInstance -ClassName Win32_ComputerSystem).TotalPhysicalMemory / 1GB
    Write-Info "Оперативная память: $([math]::Round($ram, 2)) GB"
    if ($ram -lt 4) { Write-Warning "Рекомендуется минимум 4 GB RAM (сейчас $([math]::Round($ram, 2)) GB)" }
    else { Write-Success "Достаточно RAM: $([math]::Round($ram, 2)) GB" }
}

function Check-Disk {
    $drive = Get-PSDrive -Name (Get-Location).Drive.Name
    $free = $drive.Free / 1GB
    Write-Info "Свободное место: $([math]::Round($free, 2)) GB"
    if ($free -lt 5) { Write-Warning "Рекомендуется минимум 5 GB свободного места" }
    else { Write-Success "Достаточно места: $([math]::Round($free, 2)) GB" }
}

function Check-Python {
    try {
        $pythonVersion = python --version 2>&1
        Write-Success "Python найден: $pythonVersion"
        if ($pythonVersion -match "Python 3\.(1[0-9]|[2-9][0-9])") { Write-Success "Python >= 3.10" }
        else { Write-Error "Требуется Python >= 3.10"; exit 1 }
        return $true
    } catch {
        Write-Error "Python не найден. Установите Python 3.10+ из https://python.org"; exit 1
    }
}

function Check-GPU {
    try {
        $nvidia = nvidia-smi --query-gpu=name --format=csv,noheader 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "NVIDIA GPU обнаружен: $nvidia"
            $driver = nvidia-smi --query-gpu=driver_version --format=csv,noheader
            Write-Success "Версия драйвера: $driver"
            return $true
        }
    } catch { Write-Warning "NVIDIA GPU не обнаружен — инференс на CPU" }
    return $false
}

function Create-Venv {
    Write-Section "Создание виртуального окружения"
    if (Test-Path "venv") {
        Write-Warning "Виртуальное окружение уже существует"
        $response = Read-Host "Удалить и создать заново? (y/N)"
        if ($response -eq "y" -or $response -eq "Y") { Remove-Item -Recurse -Force "venv" }
        else { return }
    }
    python -m venv venv
    Write-Success "Виртуальное окружение создано"
}

function Install-PythonDeps {
    Write-Section "Установка Python зависимостей"
    & .\venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip setuptools wheel
    if ($HasGPU) {
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    } else {
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    }
    if (Test-Path "requirements.txt") { pip install -r requirements.txt }
    else { Write-Error "requirements.txt не найден"; exit 1 }
    pip install git+https://github.com/hkevin01/wifi-radar.git 2>$null
    Write-Success "Все зависимости установлены"
}

function Download-Model {
    if ($SkipModelDownload) { Write-Info "Пропуск загрузки модели"; return }
    Write-Section "Скачивание модели"
    New-Item -ItemType Directory -Force -Path "models" | Out-Null
    & .\venv\Scripts\Activate.ps1
    Write-Info "Загрузка wifi-densepose-mmfi-pose..."
    python -c @"
import os
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
try:
    from transformers import AutoModelForImageClassification
    model = AutoModelForImageClassification.from_pretrained('ruvnet/wifi-densepose-mmfi-pose', cache_dir='models')
    print('✅ Модель успешно загружена!')
except Exception as e:
    print(f'⚠️ Не удалось загрузить модель: {e}')
"@
}

function Final-Check {
    Write-Section "Финальная проверка"
    & .\venv\Scripts\Activate.ps1
    Write-Info "Проверка установленных пакетов:"
    python -c @"
import sys
packages = ['numpy', 'scipy', 'open3d', 'torch', 'transformers']
for pkg in packages:
    try:
        __import__(pkg)
        print(f'✅ {pkg}')
    except ImportError:
        print(f'❌ {pkg} — НЕ УСТАНОВЛЕН')
"@
    Write-Success "Установка завершена!"
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  🚀 Для запуска проекта:" -ForegroundColor Green
    Write-Host "    .\venv\Scripts\Activate.ps1"
    Write-Host "    python main.py"
    Write-Host "============================================" -ForegroundColor Cyan
}

function Main {
    Write-Section "WiFi DensePose — Установка для Windows"
    if (-not $SkipHardwareCheck) {
        Check-WindowsVersion
        Check-RAM
        Check-Disk
        $script:HasGPU = Check-GPU
    } else { $script:HasGPU = $false }
    Check-Python
    Create-Venv
    Install-PythonDeps
    Download-Model
    Final-Check
}

Main