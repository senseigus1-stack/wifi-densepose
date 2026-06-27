Write-Host "[INFO] Установка зависимостей..." -ForegroundColor Cyan

if (-not (Test-Path "venv")) { python -m venv venv }

& .\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host "[SUCCESS] Зависимости установлены" -ForegroundColor Green