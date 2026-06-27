# config.py
# Конфигурационный файл для проекта WiFi Sensing (Multi-Person)

# --- Сеть ---
UDP_IP = "0.0.0.0"
UDP_PORT = 5566

# --- Обработка сигнала ---
SAMPLING_RATE = 100          # Гц, частота дискретизации CSI
FILTER_LOW = 0.5             # Нижняя граница полосового фильтра (Гц)
FILTER_HIGH = 10.0           # Верхняя граница полосового фильтра (Гц)
WINDOW_SIZE = 10             # Количество временных срезов для модели

# --- Параметры модели (Multi-Person) ---
# ID модели на Hugging Face (если используется)
MODEL_ID = "ruvnet/wifi-densepose-mmfi-pose"
MODEL_INPUT_SHAPE = (3, 114, 10)

# --- Детекция присутствия ---
PRESENCE_ENERGY_THRESHOLD = 0.15
PRESENCE_TIMEOUT = 2.0                # секунд

# --- Multi-Person ---
MAX_PEOPLE = 4
PERSON_ID_TIMEOUT = 3.0               # секунд без обновления

# --- Визуализация ---
VIZ_WIDTH = 900
VIZ_HEIGHT = 700
SMOOTHING_ALPHA = 0.3                 # сглаживание (0..1)

# --- Пути ---
MODELS_DIR = "models"