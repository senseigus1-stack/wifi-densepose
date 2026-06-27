WiFi DensePose — Multi-Person 3D Pose Estimation from Wi-Fi
=============================================================

This document is provided in three languages: English, Russian, and Udmurt.
Choose your section below.

=============================================================================
ENGLISH (English)
=============================================================================

Introduction
------------

WiFi DensePose is a system that turns commodity Wi-Fi signals into real-time
multi-person 3D pose estimation — without cameras. By analyzing CSI (Channel
State Information) from multiple ESP32-S3 nodes arranged in a mesh network,
it reconstructs 17 COCO keypoints for up to 4 people simultaneously, through
walls and in darkness.

How It Works: Full Technical Description
----------------------------------------

This section explains the complete data pipeline: from radio waves to 3D
skeletons on your screen.

Stage 1: Radio Wave Propagation (Physics)

A Wi-Fi router emits electromagnetic waves at 2.4 GHz. These waves travel
through the room and reflect off everything: walls, furniture, and people.
The human body is a dielectric with high water content — it reflects,
scatters, and absorbs radio waves differently depending on pose and movement.

Mathematically, the received signal is the superposition of all propagation paths:

H(f) = sum over n of A_n * exp(-j * 2 * pi * f * tau_n)

Where:
- H(f) — channel frequency response (what we measure)
- A_n — amplitude of the n-th path
- tau_n — delay of the n-th path
- f — frequency

When a person moves, A_n and tau_n change for paths that reflect off them.
CSI captures these changes.

Stage 2: CSI (Channel State Information)

CSI is a matrix of complex numbers sized (N_antennas x N_subcarriers):
- N_antennas = 3 (minimum for pose estimation)
- N_subcarriers = 114 (in a 20 MHz Wi-Fi channel)

Each number is a complex amplitude:

H[i][j] = |H[i][j]| * exp(j * phi[i][j])

Where:
- |H[i][j]| — amplitude (signal strength on i-th antenna, j-th subcarrier)
- phi[i][j] — phase (wave shift)

Unlike RSSI (a single number), CSI gives 114 independent measurements per
antenna. This enables detection of micro-movements (breathing, head turns).

Stage 3: ESP32-S3 Capture

ESP32-S3 uses ESP-CSI — Espressif's technology that exposes PHY-layer Wi-Fi
data:

1. Packet reception: ESP32-S3 receives a Wi-Fi packet from the router.
2. CSI extraction: The chip extracts amplitude and phase for every subcarrier
   for each antenna pair.
3. UDP streaming: Data is packed into JSON and sent via UDP to the computer's
   IP address (port 5005 by default).

Raw packet format:

{
  "timestamp": 1640995200.123,
  "mac": "AA:BB:CC:DD:EE:FF",
  "csi": [[1.23, -0.45], [0.78, 0.12], ...],
  "amplitude": [1.34, 0.79, ...],
  "phase": [0.12, -0.34, ...]
}

Stage 4: Multiple Nodes and UDP Relay (Multi-Person)

With 3-6 ESP32-S3 nodes positioned around the room, each captures CSI from
a different angle. However, due to a known firmware bug, all nodes send
node_id=1. The UDP relay fixes this by remapping node IDs based on the
sender's IP address:

IP 192.168.1.100 -> node_id=1
IP 192.168.1.101 -> node_id=2
IP 192.168.1.102 -> node_id=3

The relay listens on port 5005, rewrites the node_id, and forwards to port 5099.

Stage 5: Signal Preprocessing (Software)

The SignalProcessor module:

1. Amplitude extraction: Converts complex CSI to amplitude magnitude.
2. Reshaping: Converts data to (3, 114) — 3 antennas x 114 subcarriers.
3. Buffering: Collects WINDOW_SIZE=10 time frames at 100 Hz (0.1 seconds).
4. Filtering: Applies a 4th-order Butterworth bandpass filter (0.5-10 Hz)
   to isolate human movement (breathing, walking) from noise.

Bandpass filter transfer function:

|H(omega)|^2 = 1 / (1 + (omega/omega_c)^(2*n))

Where n=4 (order), omega_c is the cutoff frequency.

5. Tensor formation: Forms a (3, 114, 10) tensor — 3 antennas x 114 subcarriers
   x 10 time frames — and sends it to the neural network.

Stage 6: Neural Network — From CSI to Skeleton

The model (wifi-densepose-mmfi-pose) is a Transformer-based architecture.

Input: (3, 114, 10) amplitude tensor.

Pipeline:

1. Linear projection: Each of 10 time frames is projected into 256-dim space:

   e_t = W_e * x_t + b_e,  for t = 1..10

   Where x_t in R^342 (flattened 3x114), W_e in R^(256x342), b_e in R^256.

2. Transformer encoder: 4 layers, 8 attention heads. Attention:

   Attention(Q,K,V) = softmax(Q * K^T / sqrt(d_k)) * V

3. Temporal attention pooling: Key innovation — instead of averaging time
   frames, uses attention weights to preserve temporal dynamics:

   z = sum over t of alpha_t * h_t
   alpha_t = exp(w^T * h_t) / sum over j of exp(w^T * h_j)

4. MLP decoder: Maps z to 17x2 keypoints (x, y coordinates in [0,1]).

5. Skeleton graph refinement: Graph convolution over COCO bone topology
   to enforce anatomical consistency.

Output: 17 COCO keypoints per person.

Stage 7: Multi-Person Tracking

The PoseEstimator module:

1. Receives tensor from the preprocessing pipeline.
2. Runs inference through the neural network.
3. Converts 2D keypoints to 3D (Z=0 initially) and scales to meters.
4. Assigns IDs to each detected person (tracking across frames).
5. Applies exponential smoothing to reduce jitter:

   pose_smooth = (1 - alpha) * pose_prev + alpha * pose_current

   Where alpha = 0.3 (configurable).
6. Detects presence based on signal energy threshold.
7. Outputs a list of poses with IDs to the visualization module.

Stage 8: 3D Visualization

The Visualizer module (Open3D):

1. Receives pose lists from the estimator.
2. Creates geometry for each person: 17 spheres (joints) + lines (bones).
3. Assigns unique colors to each person (6-color palette).
4. Adds/removes skeletons as people enter/leave the scene.
5. Shows presence indicator: green sphere when people are detected,
   red when empty.
6. Supports interaction: rotate, zoom, switch color styles.

Keyboard shortcuts:
- 1, 2, 3 — switch color styles
- Mouse drag — rotate view
- Scroll — zoom

Performance
-----------

Metric                      Value
Accuracy (MM-Fi, torso-PCK@20)  82.69% (single), 83.59% (ensemble)
Multi-Person MPJPE          ~107 mm
Latency                     50-100 ms
Max people                  4
Through-wall range          up to 5 m
Model size                  ~2.3M parameters

Hardware Requirements
---------------------

- 3-6 ESP32-S3 boards (ESP32-S3 SuperMini or DevKitC-1 recommended)
- Micro-USB cables for each board (power and flashing)
- One 2.4 GHz Wi-Fi router (fixed channel, DHCP enabled)
- Computer (Linux or Windows) to run server software

Software Requirements
---------------------

- Python 3.10+
- ESP-IDF v5.2+ (if building firmware from source)
- Git
- Docker (optional, for server)

Step 1: Prepare Your Wi-Fi Router
---------------------------------

1. Enable only 2.4 GHz band (disable 5 GHz or use different SSID).
2. Set a fixed Wi-Fi channel (e.g., channel 6) – disable auto-channel switching.
3. Note down the SSID and password – you will need them during firmware configuration.
4. Enable DHCP so that ESP32 boards automatically get IP addresses.
5. Disable AP Isolation so boards can see each other and your computer.

Step 2: Flash Firmware to ESP32-S3
----------------------------------

You have two options: use pre-built binaries (quick) or build from source (flexible).

Option A: Pre-built binaries (recommended for beginners)

1. Download the firmware from the project repository:
   RuView/firmware/esp32-csi-node/release_bins/

2. Install esptool:
   pip install esptool

3. Connect your ESP32-S3 via USB. Identify the serial port:
   - Linux: /dev/ttyUSB* or /dev/ttyACM*
   - Windows: COMx (check Device Manager)

4. Flash the board (example for 8 MB board on COM7):
   python -m esptool --chip esp32s3 --port COM7 --baud 460800 \
       write_flash --flash_mode dio --flash_size 8MB \
       0x0 bootloader.bin \
       0x8000 partition-table.bin \
       0xf000 ota_data_initial.bin \
       0x20000 esp32-csi-node.bin

   For 4 MB boards, use the *-4mb.bin files and --flash_size 4MB.

5. Repeat for each board.

Option B: Build from source (advanced)

1. Set up ESP-IDF v5.2+ following the official guide.
2. Clone the repository and navigate to the firmware folder:
   git clone https://github.com/ruvnet/RuView.git
   cd RuView/firmware/esp32-csi-node
3. Set target:
   idf.py set-target esp32s3
4. Configure:
   idf.py menuconfig
   - Set Wi-Fi SSID and password (your router)
   - Set computer IP address (where data will be sent)
   - Set UDP port (default 5005)
   - Set Node ID (unique for each board: 1, 2, 3, ...)
5. Build and flash:
   idf.py build
   idf.py -p PORT flash

Step 3: Set Up the Mesh Network (Multiple Boards)
-------------------------------------------------

After flashing, all boards will connect to your router (not to each other directly).
They all send CSI data to the same computer IP and port. However, due to a
known firmware bug, all boards send with node_id=1, making it impossible for
the server to distinguish them. We fix this with a UDP relay.

1. Find the IP addresses of each board (check serial monitor or router admin page).
2. Write down the IPs – you will need them for the relay.

Step 4: Run the UDP Relay (Critical!)
-------------------------------------

The relay listens on port 5005, identifies the sender's IP, rewrites node_id
based on a mapping (IP -> node_id), and forwards to port 5099.

1. From the project root, run:
   python scripts/csi_node_id_relay.py --listen-port 5005 --dest-port 5099
   (Keep this terminal open)

2. For Windows Docker users, use scripts/udp-relay.py to combine UDP streams.

Step 5: Start the Server
------------------------

Option A: Using Docker (recommended)

cd docker
docker-compose up --build

The server will listen on UDP port 5099 (from relay) and expose HTTP on port 3000.

Option B: Native (without Docker)

source venv/bin/activate   # Linux
# or .\venv\Scripts\Activate.ps1  # Windows

python -m src.main --source esp32 --udp-port 5099

Step 6: Verify Everything Works
--------------------------------

1. Check relay logs – you should see lines like:
   forwarded: {'192.168.1.100': 13000, '192.168.1.101': 13000}
   rewrites=13000

2. Open http://localhost:3000/api/v1/nodes – should list all active nodes.

3. Open http://localhost:3000 in a browser – you should see 3D skeletons.

Troubleshooting
---------------

Issue                                   Solution
ESP32 not connecting to Wi-Fi           Check SSID/password; ensure 2.4 GHz band
Server sees only one node               Run the UDP relay (csi_node_id_relay.py)
On Windows Docker only one node         Use udp-relay.py and map port 5006:5005/udp in compose
No skeletons despite data               Ensure model is downloaded; check presence detection; enable emulation
Cannot flash board                      Check port drivers; on ESP32-S3, press BOOT button while connecting

=============================================================================
РУССКИЙ (Russian)
=============================================================================

Введение
--------

WiFi DensePose — система, преобразующая обычные Wi-Fi сигналы в трёхмерную
оценку позы нескольких человек в реальном времени без камер. Анализируя CSI
от нескольких узлов ESP32-S3, объединённых в mesh-сеть, она восстанавливает
17 ключевых точек для одновременного отслеживания до 4 человек сквозь стены
и в полной темноте.

Как это работает: полное техническое описание
--------------------------------------------

В этом разделе описана полная цепочка обработки данных: от радиоволн до
скелетов на экране.

Этап 1: Распространение радиоволн (физика)

Wi-Fi роутер излучает электромагнитные волны на частоте 2.4 ГГц. Эти волны
распространяются по комнате и отражаются от всего: стен, мебели, людей.
Тело человека — это диэлектрик с высоким содержанием воды — оно по-разному
отражает, рассеивает и поглощает радиоволны в зависимости от позы и движения.

Математически, принятый сигнал — это суперпозиция всех путей распространения:

H(f) = сумма по n от A_n * exp(-j * 2 * pi * f * tau_n)

Где:
- H(f) — частотная характеристика канала (то, что мы измеряем)
- A_n — амплитуда n-го пути
- tau_n — задержка n-го пути
- f — частота

Когда человек двигается, A_n и tau_n для путей, отражающихся от него,
меняются. CSI фиксирует эти изменения.

Этап 2: CSI (Channel State Information)

CSI — это матрица комплексных чисел размером (N_антенн x N_поднесущих):
- N_антенн = 3 (минимально для оценки позы)
- N_поднесущих = 114 (в Wi-Fi канале шириной 20 МГц)

Каждое число — это комплексная амплитуда:

H[i][j] = |H[i][j]| * exp(j * phi[i][j])

Где:
- |H[i][j]| — амплитуда (сила сигнала на i-й антенне и j-й поднесущей)
- phi[i][j] — фаза (сдвиг волны)

В отличие от RSSI (одно число), CSI даёт 114 независимых измерений на
каждой антенне. Это позволяет видеть микродвижения (дыхание, повороты головы).

Этап 3: Захват CSI на ESP32-S3

ESP32-S3 использует ESP-CSI — технологию Espressif, открывающую доступ
к PHY-уровню Wi-Fi:

1. Приём пакета: ESP32-S3 принимает Wi-Fi пакет от роутера.
2. Извлечение CSI: Чип извлекает амплитуду и фазу для каждой поднесущей
   для каждой пары антенн.
3. UDP-стриминг: Данные упаковываются в JSON и отправляются по UDP на
   IP-адрес компьютера (порт 5005 по умолчанию).

Формат сырого пакета:

{
  "timestamp": 1640995200.123,
  "mac": "AA:BB:CC:DD:EE:FF",
  "csi": [[1.23, -0.45], [0.78, 0.12], ...],
  "amplitude": [1.34, 0.79, ...],
  "phase": [0.12, -0.34, ...]
}

Этап 4: Несколько узлов и UDP-ретранслятор (Multi-Person)

С 3-6 узлами ESP32-S3, расположенными по периметру комнаты, каждый узел
захватывает CSI под своим углом. Однако из-за известной ошибки в прошивке
все узлы отправляют node_id=1. UDP-ретранслятор исправляет это,
переназначая node_id на основе IP-адреса отправителя:

IP 192.168.1.100 -> node_id=1
IP 192.168.1.101 -> node_id=2
IP 192.168.1.102 -> node_id=3

Ретранслятор слушает порт 5005, перезаписывает node_id и перенаправляет на
порт 5099.

Этап 5: Предобработка сигнала (программная)

Модуль SignalProcessor:

1. Извлечение амплитуд: Преобразует комплексный CSI в модуль амплитуды.
2. Решейпинг: Приводит данные к форме (3, 114) — 3 антенны x 114 поднесущих.
3. Буферизация: Накопляет WINDOW_SIZE=10 временных срезов с частотой 100 Гц
   (0.1 секунды).
4. Фильтрация: Применяет полосовой фильтр Баттерворта 4-го порядка (0.5-10 Гц)
   для выделения движений человека (дыхание, ходьба) на фоне шума.

Передаточная функция фильтра:

|H(omega)|^2 = 1 / (1 + (omega/omega_c)^(2*n))

Где n=4 (порядок), omega_c — частота среза.

5. Формирование тензора: Формирует тензор (3, 114, 10) — 3 антенны x 114
   поднесущих x 10 временных срезов — и отправляет его в нейросеть.

Этап 6: Нейросеть — от CSI к скелету

Модель (wifi-densepose-mmfi-pose) имеет архитектуру на основе Transformer.

Вход: Тензор амплитуд (3, 114, 10).

Цепочка обработки:

1. Линейная проекция: Каждый из 10 временных срезов проецируется в
   пространство размерности 256:

   e_t = W_e * x_t + b_e,  для t = 1..10

   Где x_t в R^342 (развёрнутый 3x114), W_e в R^(256x342), b_e в R^256.

2. Transformer-энкодер: 4 слоя, 8 голов внимания. Внимание:

   Attention(Q,K,V) = softmax(Q * K^T / sqrt(d_k)) * V

3. Пулдинг внимания по времени: Ключевое нововведение — вместо усреднения
   временных срезов используются веса внимания для сохранения временной динамики:

   z = сумма по t от alpha_t * h_t
   alpha_t = exp(w^T * h_t) / сумма по j от exp(w^T * h_j)

4. MLP-декодер: Отображает z в 17x2 ключевых точек (x, y координаты в [0,1]).

5. Уточнение на графе скелета: Графовая свёртка по топологии костей COCO
   для обеспечения анатомической согласованности.

Выход: 17 ключевых точек COCO для каждого человека.

Этап 7: Отслеживание нескольких людей (Multi-Person Tracking)

Модуль PoseEstimator:

1. Принимает тензор из цепочки предобработки.
2. Выполняет инференс через нейросеть.
3. Преобразует 2D ключевые точки в 3D (Z=0 изначально) и масштабирует в метры.
4. Назначает ID каждому обнаруженному человеку (отслеживание между кадрами).
5. Применяет экспоненциальное сглаживание для устранения дрожания:

   pose_smooth = (1 - alpha) * pose_prev + alpha * pose_current

   Где alpha = 0.3 (настраивается).
6. Детектирует присутствие по порогу энергии сигнала.
7. Выдаёт список поз с ID в модуль визуализации.

Этап 8: 3D-визуализация

Модуль Visualizer (Open3D):

1. Получает список поз от оценщика.
2. Создаёт геометрию для каждого человека: 17 сфер (суставы) + линии (кости).
3. Назначает уникальные цвета каждому человеку (6-цветовая палитра).
4. Добавляет/удаляет скелеты при появлении/исчезновении людей.
5. Показывает индикатор присутствия: зелёная сфера — люди есть, красная — пусто.
6. Поддерживает взаимодействие: вращение, зум, переключение стилей цветов.

Горячие клавиши:
- 1, 2, 3 — переключение цветовых стилей
- Перетаскивание мышью — вращение сцены
- Колесо мыши — масштабирование

Производительность
------------------

Метрика                         Значение
Точность (MM-Fi, torso-PCK@20)  82.69% (одна), 83.59% (ансамбль)
Multi-Person MPJPE              ~107 мм
Задержка                        50-100 мс
Макс. человек                   4
Дальность сквозь стены          до 5 м
Размер модели                   ~2.3М параметров

Требования к оборудованию
-------------------------

- 3-6 плат ESP32-S3 (рекомендуются ESP32-S3 SuperMini или DevKitC-1)
- Micro-USB кабели для каждой платы (для прошивки и питания)
- Один Wi-Fi роутер 2.4 ГГц (фиксированный канал, DHCP включён)
- Компьютер (Linux или Windows) для запуска серверной части

Требования к программному обеспечению
-------------------------------------

- Python 3.10+
- ESP-IDF v5.2+ (если собираете прошивку из исходников)
- Git
- Docker (опционально, для сервера)

Шаг 1: Подготовка Wi-Fi роутера
-------------------------------

1. Включите только 2.4 ГГц (отключите 5 ГГц или используйте разные SSID).
2. Зафиксируйте канал Wi-Fi (например, канал 6) – отключите авто-переключение.
3. Запомните SSID и пароль – они понадобятся при настройке прошивки.
4. Включите DHCP, чтобы платы автоматически получали IP-адреса.
5. Отключите AP Isolation, чтобы платы могли видеть друг друга и компьютер.

Шаг 2: Прошивка ESP32-S3
------------------------

У вас есть два варианта: использовать готовые бинарники (быстро) или собрать из исходников (гибко).

Вариант A: Готовые бинарники (рекомендуется для начинающих)

1. Скачайте прошивку из репозитория проекта:
   RuView/firmware/esp32-csi-node/release_bins/

2. Установите esptool:
   pip install esptool

3. Подключите ESP32-S3 по USB. Определите порт:
   - Linux: /dev/ttyUSB* или /dev/ttyACM*
   - Windows: COMx (смотрите в Диспетчере устройств)

4. Прошейте плату (пример для 8 МБ платы на COM7):
   python -m esptool --chip esp32s3 --port COM7 --baud 460800 \
       write_flash --flash_mode dio --flash_size 8MB \
       0x0 bootloader.bin \
       0x8000 partition-table.bin \
       0xf000 ota_data_initial.bin \
       0x20000 esp32-csi-node.bin

   Для 4 МБ плат используйте файлы *-4mb.bin и флаг --flash_size 4MB.

5. Повторите для каждой платы.

Вариант B: Сборка из исходников (продвинутый)

1. Установите ESP-IDF v5.2+ по официальной инструкции.
2. Клонируйте репозиторий и перейдите в папку прошивки:
   git clone https://github.com/ruvnet/RuView.git
   cd RuView/firmware/esp32-csi-node
3. Настройте target:
   idf.py set-target esp32s3
4. Настройте параметры:
   idf.py menuconfig
   - Установите SSID и пароль Wi-Fi (вашего роутера)
   - Установите IP-адрес компьютера (куда отправлять данные)
   - Установите UDP порт (по умолчанию 5005)
   - Установите Node ID (уникальный номер для каждой платы: 1, 2, 3...)
5. Соберите и прошейте:
   idf.py build
   idf.py -p PORT flash

Шаг 3: Настройка mesh-сети (несколько плат)
-------------------------------------------

После прошивки все платы подключаются к роутеру (не напрямую друг к другу).
Все они отправляют данные на один IP и порт компьютера. Однако из-за ошибки
в прошивке все платы отправляют node_id=1, и сервер не может их различить.
Мы исправляем это с помощью UDP-ретранслятора.

1. Узнайте IP-адреса каждой платы (посмотрите в мониторе порта или в админке роутера).
2. Запишите их – они понадобятся для ретранслятора.

Шаг 4: Запуск UDP-ретранслятора (критично!)
-------------------------------------------

Ретранслятор слушает порт 5005, определяет IP-адрес отправителя, перезаписывает
node_id на основе соответствия IP -> node_id и перенаправляет на порт 5099.

1. Из корня проекта выполните:
   python scripts/csi_node_id_relay.py --listen-port 5005 --dest-port 5099
   (Оставьте этот терминал открытым)

2. Для пользователей Windows с Docker используйте scripts/udp-relay.py, чтобы
   объединить UDP-потоки.

Шаг 5: Запуск сервера
---------------------

Вариант A: Docker (рекомендуется)

cd docker
docker-compose up --build

Сервер будет слушать UDP порт 5099 (от ретранслятора) и HTTP порт 3000.

Вариант B: Нативный запуск (без Docker)

source venv/bin/activate   # Linux
# или .\venv\Scripts\Activate.ps1  # Windows

python -m src.main --source esp32 --udp-port 5099

Шаг 6: Проверка работоспособности
----------------------------------

1. Посмотрите логи ретранслятора – должны появляться строки:
   forwarded: {'192.168.1.100': 13000, '192.168.1.101': 13000}
   rewrites=13000

2. Откройте http://localhost:3000/api/v1/nodes – должен вернуться JSON со всеми узлами.

3. Откройте http://localhost:3000 в браузере – вы должны увидеть 3D-скелеты.

Типичные проблемы и их решение
------------------------------

Проблема                               Решение
ESP32 не подключается к Wi-Fi           Проверьте SSID/пароль; убедитесь, что роутер на 2.4 ГГц
Сервер видит только один узел           Запустите UDP-ретранслятор (csi_node_id_relay.py)
В Windows Docker виден только один узел  Используйте udp-relay.py и измените маппинг портов в docker-compose.yml на 5006:5005/udp
Нет скелетов, хотя данные идут          Убедитесь, что модель скачана; проверьте детекцию присутствия; включите эмуляцию для теста
Плата не прошивается                    Проверьте драйверы порта; на ESP32-S3 может потребоваться удерживать кнопку BOOT при подключении


=============================================================================
УДМУРТ КЫЛ (Udmurt)
=============================================================================

Азькыл (Введение)
------------------

WiFi DensePose – Wi‑Fi сигналъёс пыр адямилэсь позаоссэс тодэтъян система,
камераос ӧвӧл. Трос ESP32‑S3 узелъёслэн mesh‑сетенызы CSI (Channel State
Information) лыдъёс пыр 17 ключевой точкаосысь скелет лэсьтэ, 4 адямилы
огпола, стенаос пыр, пемытэн.

Кызьы ужа: быдэс технической малпан
-------------------------------------

Та люкетэн валэктоно, кызьы даннойёс быдтӥсько: радиоволнаосысь 3D‑скелетъёсозь.

1-тӥ люкет: Радиоволнаослэн быдтонзы (физика)

Wi‑Fi роутер 2.4 ГГц частотаен электромагнитной волнаос ыштэ. Та волнаос
комната пыр быдто но вань объектъёсысь вордскыло: стенаосысь, мебельысь,
адямиосысь. Адямилэн телоез – ву тросэз диэлектрик – со волнаосты
пӧртэмлыко вордтэ, пазьда но сьӧраз, поза но быдон сярысь.

Математикая, басьтэм сигнал – вань быдон пумъемъёслэн суперпозицизы:

H(f) = сумма n-лы A_n * exp(-j * 2 * pi * f * tau_n)

Кытын:
- H(f) – каналлэн частота характеристикаез (ми тодэтъёсмы)
- A_n – n-ти пумъемлэн амплитудаез
- tau_n – n-ти пумъемлэн быдтон дырыз
- f – частота

Адями быдэ, ветлэ яке гинэ тышкаке, сое вордскем пумъемъёслэн A_n но tau_n
вошъясько. CSI та вошъяськонъёссэ лыдъя.

2-тӥ люкет: CSI (Channel State Information)

CSI – та комплексной лыдъёсын матрица, быдэсэз (N_антенна × N_поднесущая):
- N_антенна = 3 (поза тодэтъян понна тӥрмытӥ)
- N_поднесущая = 114 (20 МГц Wi‑Fi каналын)

Кажне лыд – комплексной амплитуда:

H[i][j] = |H[i][j]| * exp(j * phi[i][j])

Кытын:
- |H[i][j]| – амплитуда (i-ти антенна, j-ти поднесущая)
- phi[i][j] – фаза (волналэн вошъяськемез)

RSSI‑лэсь (ог лыд) пӧртэм, CSI кажне антенналы 114 независимой мертан
сётэ. Та позволитъя микродвижениеос (тышкан, йыр вошъяськон) адзыны.

3-тӥ люкет: CSI‑ез ESP32‑S3‑ын люкан

ESP32‑S3 ESP‑CSI технологиез кутылэ – Espressif‑лэн PHY‑уровень Wi‑Fi‑ез
усьтонэз:

1. Пакет басьтон: ESP32‑S3 роутерысь Wi‑Fi пакет басьтэ.
2. CSI люкан: Чип кажне поднесущаялы но антенна люкетлы амплитуда но фаза
   басьтэ.
3. UDP‑я ыстон: Даннойёс JSON‑лы пырто но UDP пыр компьютерлэн IP‑адресаз
   ысто (ваньды порт 5005).

Сырой пакетлэн форматез:

{
  "timestamp": 1640995200.123,
  "mac": "AA:BB:CC:DD:EE:FF",
  "csi": [[1.23, -0.45], [0.78, 0.12], ...],
  "amplitude": [1.34, 0.79, ...],
  "phase": [0.12, -0.34, ...]
}

4-тӥ люкет: Трос узел но UDP‑ретранслятор (Multi‑Person)

3‑6 ESP32‑S3 узелъёс комната периметръя пуктэмын, кажнезы аслаз ракурсеныз
CSI люка. Но прошивкаын тодмо ошибка – вань узелъёс node_id=1‑я ысто.
UDP‑ретранслятор сое тупатэ, node_id‑ез отправительлэн IP‑адресаз сэрттыса:

IP 192.168.1.100 -> node_id=1
IP 192.168.1.101 -> node_id=2
IP 192.168.1.102 -> node_id=3

Ретранслятор порт 5005 кылё, node_id‑ез воштыса, порт 5099‑лы ыстэ.

5-тӥ люкет: Сигнал азьын дасян (программной)

SignalProcessor модуль:

1. Амплитудаос люкан: Комплексной CSI‑ез амплитуда модульлы тупатэ.
2. Форма воштон: Даннойёссэ (3, 114)‑лы пыртэ – 3 антенна × 114 поднесущая.
3. Буферизация: WINDOW_SIZE=10 дыр срез люка, частота 100 Гц (0.1 секунда).
4. Фильтрация: 4‑ти порядко Баттерворт полосовой фильтр (0.5‑10 Гц) кутылэ,
   адямилэсь быдонэз (тышкан, ветлон) шумлэсь люкиськыны.

Фильтрлэн передаточной функцияез:

|H(omega)|^2 = 1 / (1 + (omega/omega_c)^(2*n))

Кытын n=4 (порядок), omega_c – срез частота.

5. Тензор лэсьтон: (3, 114, 10) тензор лэсьтэ – 3 антенна × 114 поднесущая ×
   10 дыр срез – но нейросетьлы сётэ.

6-тӥ люкет: Нейросеть – CSI‑ысь скелетозь

Модель (wifi‑densepose‑mmfi‑pose) Transformer вылэсь лэсьтэм.

Пырон: (3, 114, 10) амплитуда тензор.

Ужан рад:

1. Линейной проекция: 10 дыр срезэз 256‑мерной пространствое пыртэ:

   e_t = W_e * x_t + b_e,  t = 1..10

   Кытын x_t R^342‑ын (3×114 люкаськем), W_e R^(256×342)‑ын, b_e R^256‑ын.

2. Transformer‑энкодер: 4 слой, 8 йырын внимание. Внимание:

   Attention(Q,K,V) = softmax(Q * K^T / sqrt(d_k)) * V

3. Дыр внимание пулинг: Валтӥс выльдыт – дыр срезъёсты огъя усреднять
   карытэк, внимание весъёс пыр дыр динамика утьыны:

   z = сумма t-лы alpha_t * h_t
   alpha_t = exp(w^T * h_t) / сумма j-лы exp(w^T * h_j)

4. MLP‑декодер: z‑ез 17×2 ключевой точкаослы (x, y координатаос [0,1]‑ын)
   тупатэ.

5. Скелет граф вылэсь тупатон: COCO лыдон топологияя графовой свёртка
   анатомической согласованность понна.

Поттон: 17 COCO ключевой точка кажне адямилы.

7-тӥ люкет: Трос адямилы лыдон (Multi‑Person Tracking)

PoseEstimator модуль:

1. Тензорэз азьын дасян радлэсь басьтэ.
2. Нейросеть пыр инференс каре.
3. 2D ключевой точкаоссэ 3D‑лы (Z=0 нырысетын) тупатэ но метръёсы шкала каре.
4. Кажне адямилы ID сетэ (кадръёс пыр лыдон).
5. Экспоненциальной смазка кутылэ трясениез чакланы:

   pose_smooth = (1 - alpha) * pose_prev + alpha * pose_current

   Кытын alpha = 0.3 (тупатъяно).
6. Присутствие лыдъя сигнал энергия порог пыр.
7. Позаослэн списоксэсты ID‑еныз визуализация модульлы сётэ.

8-тӥ люкет: 3D‑видмоно

Visualizer модуль (Open3D):

1. PoseEstimator‑ысь поза список басьтэ.
2. Кажне адямилы геометрия лэсьтэ: 17 шар (сустав) но гин (лыдъёс).
3. Кажне адямилы аслаз буёл сетэ (6 буёллэн палитраез).
4. Скелетъёсты сэрттэ но быдтэ адямиос валэктон но быдтон дыръя.
5. Присутствие индикатор возьматэ: зелёной шар – адямиос вань, горд – ӧвӧл.
6. Взаимодействие: эркыным, зум, буёлъёс воштон.

Клавишаослэн валтӥсь командаоссы:
- 1, 2, 3 – буёл стиль воштон
- Мышь пыр эркыны – сцена эркыны
- Мышьлэн колесоез – зум

Ужан быдэстэмлык (Performance)
-------------------------------

Метрика                         Быдэстэмлык
Точность (MM-Fi, torso-PCK@20)  82.69% (ог), 83.59% (ансамбль)
Multi-Person MPJPE              ~107 мм
Берпум (Latency)                50-100 мс
Макс. адямиос                   4
Стенаос пыр дальность           ～5 м
Модельлэн быдэсэз               ~2.3М параметр

Оборудование кутскон
---------------------

- 3‑6 ESP32‑S3 плата (ESP32‑S3 SuperMini яке DevKitC‑1 эсэгетэм)
- Кажне платалы Micro‑USB кабель (прошивка но питание понна)
- Ог 2.4 ГГц Wi‑Fi роутер (фиксированной канал, DHCP вӧйын)
- Компьютер (Linux яке Windows) сервер ужатыны

Программной кутскон
--------------------

- Python 3.10+
- ESP‑IDF v5.2+ (прошивка сборка понна)
- Git
- Docker (опционально, сервер понна)

1-тӥ шаг: Wi‑Fi роутерэз дасян
--------------------------------

1. 2.4 ГГц гинэ (5 ГГц узь).
2. Фиксированной канал пукты (кылсярысь канал 6) – авто‑воштон узь.
3. SSID но пароль гожтэ – прошивка дасян понна кӧс.
4. DHCP вӧйы – платаос IP адресъёс басьтозы.
5. AP Isolation узь – платаос ог‑огэс но компьютерэз адӟозы.

2-тӥ шаг: ESP32‑S3‑лы прошивка пуктон
--------------------------------------

Кык вариант: готовой бинарникъёс (тургак) яке исходникъёсысь сборка (багат).

Вариант A: Готовой бинарникъёс (нырысетӥ понна)

1. Проектлэн репозиторияз прошивка басьтэ:
   RuView/firmware/esp32‑csi‑node/release_bins/
2. esptool пукты:
   pip install esptool
3. ESP32‑S3 USB‑я валтэ. Порт тодэ:
   - Linux: /dev/ttyUSB* яке /dev/ttyACM*
   - Windows: COMx (Диспетчер устройств‑ын)
4. Прошейте (пример 8 МБ платалы COM7):
   python -m esptool --chip esp32s3 --port COM7 --baud 460800 \
       write_flash --flash_mode dio --flash_size 8MB \
       0x0 bootloader.bin \
       0x8000 partition-table.bin \
       0xf000 ota_data_initial.bin \
       0x20000 esp32‑csi‑node.bin
   4 МБ платалы *‑4mb.bin файлъёс но --flash_size 4MB флаг.
5. Кажне платалы вотэс кыльты.

Вариант B: Исходникъёсысь сборка (багат)

1. ESP‑IDF v5.2+ пукты.
2. Репозиторий клон каре:
   git clone https://github.com/ruvnet/RuView.git
   cd RuView/firmware/esp32‑csi‑node
3. Target пукты:
   idf.py set‑target esp32s3
4. Конфигурация:
   idf.py menuconfig
   - Wi‑Fi SSID но пароль (роутерлэн)
   - Компьютерлэн IP адресез (даннойёс ыстоно)
   - UDP порт (ваньды 5005)
   - Node ID (кажне платалы пӧртэм: 1, 2, 3...)
5. Сборка но прошивка:
   idf.py build
   idf.py -p PORT flash

3-тӥ шаг: Mesh‑сеть дасян (трос плата)
--------------------------------------

Прошивка бере вань платаос роутере валтӥсько (ог‑огзылы ӧвӧл). Ваньзы
даннойёссэ ог компьютерлы ысто. Но прошивкаын ошибка – вань платаос
node_id=1‑я ысто, сервер пӧртэмлыкыз ӧдӟе. UDP‑ретранслятор сое тупатэ.

1. Кажне платалэн IP адрессэ тодэ (монитор яке роутер админка).
2. Гожтэ – ретрансляторлы кӧс.

4-тӥ шаг: UDP‑ретранслятор кутскон (валтӥс!)
-------------------------------------------

Ретранслятор порт 5005 кылё, отправительлэн IP‑ез пыр node_id‑ез тупатэ
(IP -> node_id) но порт 5099‑лы ыстэ.

1. Проектлэн кореньяз:
   python scripts/csi_node_id_relay.py --listen‑port 5005 --dest‑port 5099
   (Терминал усьтэм кельты)

2. Windows Docker понна scripts/udp‑relay.py кутылэ.

5-тӥ шаг: Сервер кутскон
-------------------------

Вариант A: Docker (эсэгетэм)

cd docker
docker‑compose up --build

Сервер UDP порт 5099 (ретрансляторысь) но HTTP порт 3000 кылё.

Вариант B: Нативной (Docker ӧвӧл)

source venv/bin/activate   # Linux
# яке .\venv\Scripts\Activate.ps1  # Windows

python -m src.main --source esp32 --udp‑port 5099

6-тӥ шаг: Ужан эскерон
----------------------

1. Ретранслятор логъёс – строкаос потозы:
   forwarded: {'192.168.1.100': 13000, '192.168.1.101': 13000}
   rewrites=13000

2. http://localhost:3000/api/v1/nodes усьтэ – вань узелъёслэн списоксы потэ.

3. http://localhost:3000 усьтэ – 3D скелетъёс адӟиськозы.

Лыдтэм проблемъёс
-----------------

Проблема                               Тупатон
ESP32 Wi‑Fi‑е ӧз валтӥськы             SSID/пароль эскере; роутер 2.4 ГГц‑ын ужа
Сервер гинэ ог узел адӟе               UDP‑ретранслятор кутэ (csi_node_id_relay.py)
Windows Docker‑ын гинэ ог узел         udp‑relay.py куты, docker‑compose.yml‑ын порт маппинг вошты: 5006:5005/udp
Скелетъёс ӧвӧл, но даннойёс вань       Модель басьтэмын эскере; присутствие эскерон; эмуляция вӧйы
Плата прошивка ӧз быдзы                Порт драйверъёс эскере; ESP32‑S3‑ын BOOT кнопка кутӥськы

=============================================================================
Заключение (Conclusion)
=======================

Та README быдэс пошаговой руководство сётэ оборудование дасяны,
ESP32‑S3 платаослы прошивка пуктыны, mesh‑сеть дасяны, UDP‑ретранслятор
но сервер кутскыны. "Кызьы ужа" люкетэн валэктоно быдэс данной
конвейер – радиоволнаосысь 3D‑скелетъёсозь. Вань шагъёсты радэз
кыльтыса, система "коробкаысь" ужаны кутскоз.

Проблемаос валэктоно ке, лыдтэм проблемъёслэн таблицаезлы эскере.

Ужанлы туро!