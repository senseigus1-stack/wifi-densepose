#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo ""; echo "============================================"; echo -e "${BLUE}$1${NC}"; echo "============================================"; }

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        log_error "Не удалось определить ОС"
        exit 1
    fi
    log_info "Обнаружена ОС: $OS $VERSION"
}

check_architecture() {
    ARCH=$(uname -m)
    log_info "Архитектура: $ARCH"
    case $ARCH in
        x86_64|aarch64|arm64) log_success "Поддерживаемая архитектура: $ARCH" ;;
        *) log_warning "Архитектура $ARCH не тестировалась" ;;
    esac
}

check_cpu() {
    CPU_CORES=$(nproc)
    CPU_MODEL=$(lscpu | grep "Model name" | head -1 | cut -d':' -f2 | xargs)
    log_info "CPU: $CPU_MODEL ($CPU_CORES ядер)"
    if grep -q avx2 /proc/cpuinfo; then
        log_success "CPU поддерживает AVX2"
    else
        log_warning "CPU не поддерживает AVX2 — PyTorch может работать медленнее"
    fi
}

check_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
        log_success "Обнаружен NVIDIA GPU: $GPU_INFO"
        DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null)
        log_success "Версия драйвера NVIDIA: $DRIVER_VERSION"
        HAS_GPU=true
    else
        log_warning "NVIDIA GPU не обнаружен — инференс на CPU"
        HAS_GPU=false
    fi
}

check_ram() {
    TOTAL_RAM=$(free -h | awk '/^Mem:/ {print $2}')
    TOTAL_RAM_GB=$(free -g | awk '/^Mem:/ {print $2}')
    log_info "Оперативная память: $TOTAL_RAM"
    if [ "$TOTAL_RAM_GB" -lt 4 ]; then
        log_warning "Рекомендуется минимум 4 ГБ RAM (сейчас $TOTAL_RAM)"
    else
        log_success "Достаточно RAM: $TOTAL_RAM"
    fi
}

check_disk() {
    AVAIL_SPACE=$(df -h . | awk 'NR==2 {print $4}')
    AVAIL_SPACE_GB=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    log_info "Свободное место на диске: $AVAIL_SPACE"
    if [ "$AVAIL_SPACE_GB" -lt 5 ]; then
        log_warning "Рекомендуется минимум 5 ГБ свободного места (сейчас $AVAIL_SPACE)"
    else
        log_success "Достаточно места: $AVAIL_SPACE"
    fi
}

check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        log_success "Python3 найден: $PYTHON_VERSION"
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
        if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
            log_success "Python версия >= 3.10"
        else
            log_error "Требуется Python >= 3.10 (сейчас $PYTHON_VERSION)"
            exit 1
        fi
    else
        log_error "Python3 не найден"
        exit 1
    fi
}

install_system_deps() {
    log_section "Установка системных зависимостей"
    case $OS in
        ubuntu|debian|linuxmint|pop)
            sudo apt update
            sudo apt install -y python3-pip python3-venv python3-dev git build-essential cmake libopenblas-dev libatlas-base-dev libjpeg-dev libpng-dev libgl1-mesa-glx libglib2.0-0 wget curl
            ;;
        fedora|rhel|centos)
            sudo dnf install -y python3-pip python3-devel git gcc-c++ make cmake openblas-devel atlas-devel libjpeg-turbo-devel libpng-devel mesa-libGL glib2 wget curl
            ;;
        arch|manjaro)
            sudo pacman -Sy --noconfirm python-pip python-virtualenv git base-devel cmake openblas lapack libjpeg-turbo libpng mesa glib2 wget curl
            ;;
        *)
            log_warning "Неизвестная ОС. Установите вручную: python3, pip, git, build-essential"
            ;;
    esac
}

create_venv() {
    log_section "Создание виртуального окружения"
    if [ -d "venv" ]; then
        log_warning "Виртуальное окружение уже существует"
        read -p "Удалить и создать заново? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf venv
        else
            return 0
        fi
    fi
    python3 -m venv venv
    log_success "Виртуальное окружение создано"
}

install_python_deps() {
    log_section "Установка Python зависимостей"
    source venv/bin/activate
    pip install --upgrade pip setuptools wheel
    if [ "$HAS_GPU" = true ] && command -v nvcc &> /dev/null; then
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    else
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    fi
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        log_error "requirements.txt не найден"
        exit 1
    fi
    pip install git+https://github.com/hkevin01/wifi-radar.git || log_warning "Не удалось установить WiFi-Radar"
    log_success "Все зависимости установлены"
}

check_model() {
    log_section "Проверка модели"
    source venv/bin/activate
    mkdir -p models
    if [ -d "models/wifi-densepose-mmfi-pose" ]; then
        log_success "Модель уже скачана"
    else
        log_info "Скачивание модели wifi-densepose-mmfi-pose..."
        python -c "
import os
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
try:
    from transformers import AutoModelForImageClassification
    model = AutoModelForImageClassification.from_pretrained('ruvnet/wifi-densepose-mmfi-pose', cache_dir='models')
    print('✅ Модель успешно загружена!')
except Exception as e:
    print(f'⚠️ Не удалось загрузить модель: {e}')
" || log_warning "Не удалось загрузить модель"
    fi
}

final_check() {
    log_section "Финальная проверка"
    source venv/bin/activate
    log_info "Проверка установленных пакетов:"
    python -c "
import sys
packages = ['numpy', 'scipy', 'open3d', 'torch', 'transformers']
for pkg in packages:
    try:
        __import__(pkg)
        print(f'✅ {pkg}')
    except ImportError:
        print(f'❌ {pkg} — НЕ УСТАНОВЛЕН')
"
    log_success "Установка завершена!"
    echo ""
    echo "============================================"
    echo "  🚀 Для запуска проекта:"
    echo "    source venv/bin/activate"
    echo "    python -m src.main"
    echo "============================================"
}

main() {
    log_section "WiFi DensePose — Установка для Linux"
    detect_os
    check_architecture
    check_cpu
    check_gpu
    check_ram
    check_disk
    check_python
    install_system_deps
    create_venv
    install_python_deps
    check_model
    final_check
}

main "$@"