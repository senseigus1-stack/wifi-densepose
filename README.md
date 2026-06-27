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
multi-person 3D pose estimation — without a single camera. By analyzing
Channel State Information (CSI) — the tiny distortions that a human body
imprints on radio waves — the system reconstructs 17 COCO keypoints for up
to 4 people simultaneously, works through walls, in darkness, and requires
no wearables.

Hardware Requirements
---------------------

Component           Recommended Model              Approx. Cost   Purpose
Microcontroller     ESP32-S3 (CSI-enabled)         ~$10-15        CSI capture and UDP streaming
Wi-Fi Router        Any 2.4 GHz router             (existing)     Radio source
Computer            Linux (Ubuntu 22.04+) / Win10+ / macOS    —    Inference & visualization
GPU (optional)      NVIDIA with CUDA               —              Accelerated inference

Note: Standard Wi-Fi adapters do not expose CSI. You need an ESP32-S3 or
a research NIC (Intel 5300, Atheros AR9580).

Physical Principles: How Wi-Fi Sees Through Walls
-------------------------------------------------

Wi-Fi sensing is based on the physics of radio wave propagation and the
multipath effect[reference:0].

When a Wi-Fi router transmits a signal, the electromagnetic waves travel
from the transmitter antenna to the receiver antenna through multiple paths:
- Direct line-of-sight path
- Reflections from walls, furniture, and other objects
- Reflections from the human body[reference:1]

The received signal is the superposition of all these paths[reference:2]. When
a person moves, walks, or even breathes, they change the reflection paths
— some paths get blocked, new paths appear, and the relative phases of
the reflected waves shift[reference:3].

These changes are captured by CSI — a per-subcarrier measurement of
amplitude and phase for every pair of transmitting and receiving antennas[reference:4].
Unlike RSSI (a single number representing overall signal strength), CSI
provides rich, high-dimensional data that can detect movements as subtle
as breathing[reference:5].

CSI Data Format
---------------

ESP32-S3 sends UDP (port 5566) JSON packets. Example:

{
  "timestamp": 1640995200.123,
  "mac": "AA:BB:CC:DD:EE:FF",
  "csi": [ [1.23, -0.45], [0.78, 0.12], ... ],
  "amplitude": [1.34, 0.79, ...],
  "phase": [0.12, -0.34, ...]
}

- csi – array of complex numbers (real, imag) for all subcarriers and antennas.
- amplitude – magnitudes (modulus of complex numbers).
- phase – phases (argument of complex numbers).
- The system expects 3 antennas × 114 subcarriers. Extra data is truncated;
  missing data is zero-filled.

ESP32-S3: The Sensing Frontend
------------------------------

The ESP32-S3 is a low-cost microcontroller with built-in Wi-Fi. Espressif's
ESP-CSI technology allows it to expose raw Channel State Information from
the Wi-Fi PHY layer[reference:6][reference:7].

How ESP-CSI works:
- Wi-Fi uses OFDM, splitting each channel into many subcarriers[reference:8].
- For each subcarrier, the chip measures amplitude (signal strength) and
  phase (wave rotation/delay)[reference:9].
- These values are captured at the PHY layer and exposed via CSI callback
  events in the ESP-IDF API[reference:10].
- The data is then streamed over UDP to your computer for processing.

ESP-CSI advantages over RSSI:
- RSSI: single value, low sensitivity, detects only big changes[reference:11].
- CSI: per-subcarrier amplitude + phase, high sensitivity, detects breathing[reference:12].
- CSI is robust against common interference like power adapters[reference:13].

For multi-person pose estimation, you need multiple antennas. The ESP32-S3
supports this, and with an external router providing the signal, you get
a 3-antenna × 114-subcarrier CSI matrix.

Neural Network: From CSI to Skeleton
------------------------------------

The model used is `wifi-densepose-mmfi-pose` (available on Hugging Face)[reference:14].

Input: CSI amplitude tensor of shape [3, 114, 10]
- 3 antenna pairs (spatial diversity)
- 114 subcarriers (frequency diversity)
- 10 time frames at 100 Hz (temporal dynamics)[reference:15]

Architecture (simplified):
1. 10 time frames → 10 tokens (dim 342 → 256)
2. 4-layer / 8-head Transformer encoder
3. Temporal attention pooling — the key breakthrough (replacing global-mean-pool
   took accuracy from 3% to 48%+)[reference:16]
4. MLP decoder + skeleton-graph refinement head (graph convolution over COCO
   bone topology)[reference:17]
5. Output: [17, 2] keypoints in [0,1] coordinate space

Model size: ~2.3M parameters[reference:18]

Performance (MM-Fi benchmark, torso-PCK@20):
- CSI2Pose (prior work): 68.41%
- MultiFormer (prior SOTA, 2025): 72.25%
- This model (single): 82.69%
- This model (3-ensemble + TTA): 83.59%[reference:19]

Important limitations:
- The 82.69% result is in-domain (random split)[reference:20].
- Cross-subject (new person): ~64%
- Cross-environment (new room): ~17.5% (with CORAL domain alignment)[reference:21]
- Real-world deployment requires few-shot calibration — a tiny amount of
  labeled data from the deployment site recovers most of the performance[reference:22].

File Descriptions
-----------------

config.py
  Central configuration: network settings (UDP_IP, UDP_PORT), signal
  processing parameters (SAMPLING_RATE, filters), model ID and input shape,
  presence detection thresholds, multi-person limits, visualization options.

csi_server.py
  UDP server class CSIServer: listens on UDP port, parses JSON, pushes raw
  data into raw_csi_queue in a separate thread.

signal_processor.py
  Class SignalProcessor: extracts amplitudes from raw CSI, reshapes to
  (3, 114), maintains a buffer of the last WINDOW_SIZE frames, and when full,
  forms a (3, 114, 10) tensor and puts it into processed_queue for the neural
  network.

pose_estimator.py
  Core module. Class PoseEstimator: loads the wifi-densepose-mmfi-pose model
  (or emulates if unavailable), runs inference on CSI tensors, obtains 17
  keypoints per person, adds Z=0, scales to meters, applies exponential
  smoothing, tracks person IDs, detects presence via energy threshold, and
  outputs a list of poses with IDs to pose_queue. If model is missing, it
  simulates 1-2 standing people with slight arm movements for demonstration.

visualizer.py
  Open3D visualization. Class Visualizer: receives pose lists, creates
  per-person geometry (spheres + lines) with unique colors, adds/removes
  skeletons as people appear/disappear, shows a presence indicator (green/red
  sphere), supports 1, 2, 3 keys for color style switching (stub).

main.py
  Entry point. Sets up queues, starts all components as threads, handles
  Ctrl+C for clean shutdown.

Installation and Run
--------------------

Docker (recommended):
  cd docker
  docker-compose up --build

Linux (native):
  git clone https://github.com/senseigus1-stack/wifi-densepose.git
  cd wifi-densepose
  chmod +x scripts/linux/setup.sh
  ./scripts/linux/setup.sh
  source venv/bin/activate
  python main.py

Windows (PowerShell):
  git clone https://github.com/senseigus1-stack/wifi-densepose.git
  cd wifi-densepose
  .\scripts\windows\setup.ps1
  .\venv\Scripts\Activate.ps1
  python main.py

Setup scripts check Python, CUDA, RAM, free disk space, and install all
dependencies.

License and References
----------------------

MIT License. Based on:
- Person-in-WiFi 3D (CVPR 2024) – first end-to-end multi-person pose
  estimation from Wi-Fi[reference:23].
- WiFi-DensePose (CMU Master Thesis, 2022) – mapping Wi-Fi to poses[reference:24].
- WiFi-Radar (GitHub) – practical fall detection and gait analysis.

Source code at https://github.com/senseigus1-stack/wifi-densepose


=============================================================================
РУССКИЙ (Russian)
=============================================================================

Введение
--------

WiFi DensePose — это система, которая превращает обычные Wi‑Fi сигналы
в трёхмерную оценку позы нескольких человек в реальном времени —
без единой камеры. Анализируя CSI (Channel State Information) —
те крошечные искажения, которые тело человека накладывает на радиоволны —
система восстанавливает 17 ключевых точек (COCO) для одновременного
отслеживания до 4 человек. Она работает сквозь стены, в полной темноте
и не требует носимых датчиков.

Требования к оборудованию
-------------------------

Компонент             Рекомендуемая модель              Цена (прим.)   Назначение
Микроконтроллер       ESP32‑S3 (с поддержкой CSI)       ~$10‑15        Сбор CSI и отправка по UDP
Wi‑Fi роутер          Любой 2.4 ГГц                     (есть)         Источник радиосигнала
Компьютер             Linux (Ubuntu 22.04+) / Win10+ / macOS   —       Запуск нейросети и визуализации
GPU (опционально)     NVIDIA с CUDA                     —              Ускорение инференса

Важно: обычные Wi‑Fi адаптеры не выдают CSI. Нужен ESP32‑S3 или
исследовательская сетевая карта (Intel 5300, Atheros AR9580).

Физические принципы: как Wi‑Fi видит сквозь стены
-------------------------------------------------

В основе Wi‑Fi sensing лежит физика распространения радиоволн и
эффект многолучевого распространения (multipath)[reference:25].

Когда роутер излучает сигнал, электромагнитные волны идут от передающей
антенны к приёмной по множеству путей:
- Прямая видимость (line‑of‑sight)
- Отражения от стен, мебели и других объектов
- Отражения от тела человека[reference:26]

Принятый сигнал — это суперпозиция всех этих путей[reference:27]. Когда человек
движется, идёт или даже просто дышит, он изменяет пути отражения —
одни пути блокируются, появляются новые, относительные фазы отражённых
волн сдвигаются[reference:28].

Эти изменения фиксирует CSI — поканальное измерение амплитуды и фазы
для каждой пары передающей и приёмной антенн[reference:29]. В отличие от
RSSI (одно число, общая мощность сигнала), CSI даёт богатые многомерные
данные, способные улавливать движения вплоть до дыхания[reference:30].

Формат данных CSI
-----------------

ESP32‑S3 отправляет данные по UDP (порт 5566) в формате JSON. Пример:

{
  "timestamp": 1640995200.123,
  "mac": "AA:BB:CC:DD:EE:FF",
  "csi": [ [1.23, -0.45], [0.78, 0.12], ... ],
  "amplitude": [1.34, 0.79, ...],
  "phase": [0.12, -0.34, ...]
}

- csi – массив комплексных чисел (действительная и мнимая часть) для всех
  субканалов и антенн.
- amplitude – амплитуды (модуль комплексного числа).
- phase – фазы (аргумент комплексного числа).
- Система ожидает 3 антенны × 114 субканалов. Лишние данные обрезаются,
  недостающие заполняются нулями.

ESP32‑S3: сенсорный фронтенд
----------------------------

ESP32‑S3 — это недорогой микроконтроллер со встроенным Wi‑Fi. Технология
ESP‑CSI от Espressif позволяет получать сырую информацию о состоянии
канала (CSI) прямо с PHY‑уровня Wi‑Fi[reference:31][reference:32].

Как работает ESP‑CSI:
- Wi‑Fi использует OFDM, разбивая каждый канал на множество субканалов[reference:33].
- Для каждого субканала чип измеряет амплитуду (силу сигнала) и фазу
  (поворот/задержку волны)[reference:34].
- Эти значения снимаются на PHY‑уровне и передаются через CSI‑колбэки
  в ESP‑IDF API[reference:35].
- Данные затем передаются по UDP на ваш компьютер для обработки.

Преимущества ESP‑CSI перед RSSI:
- RSSI: одно число, низкая чувствительность, detects only big changes[reference:36].
- CSI: поканальные амплитуда + фаза, высокая чувствительность, видит дыхание[reference:37].
- CSI устойчив к типичным помехам (блоки питания и т.п.)[reference:38].

Для многопользовательской оценки позы нужно несколько антенн. ESP32‑S3
это поддерживает, а с внешним роутером, дающим сигнал, вы получаете
матрицу CSI размером 3 антенны × 114 субканалов.

Нейросеть: от CSI к скелету
---------------------------

Используется модель `wifi-densepose-mmfi-pose` (доступна на Hugging Face)[reference:39].

Вход: тензор амплитуд CSI размером [3, 114, 10]
- 3 пары антенн (пространственное разнообразие)
- 114 субканалов (частотное разнообразие)
- 10 временных срезов с частотой 100 Гц (временная динамика)[reference:40]

Архитектура (упрощённо):
1. 10 временных срезов → 10 токенов (размерность 342 → 256)
2. 4‑слойный / 8‑головый Transformer‑энкодер
3. Временное attention‑пулинг — ключевой прорыв (замена global‑mean‑pool
   подняла точность с 3% до 48%+)[reference:41]
4. MLP‑декодер + head уточнения скелета (графовая свёртка по топологии
   костей COCO)[reference:42]
5. Выход: [17, 2] ключевых точек в координатах [0,1]

Размер модели: ~2.3 млн параметров[reference:43]

Точность (бенчмарк MM‑Fi, torso‑PCK@20):
- CSI2Pose (предыдущая работа): 68.41%
- MultiFormer (предыдущий SOTA, 2025): 72.25%
- Эта модель (одиночная): 82.69%
- Эта модель (ансамбль из 3 + TTA): 83.59%[reference:44]

Важные ограничения:
- Результат 82.69% получен в условиях in‑domain (random split)[reference:45].
- Перекрёстный субъект (новый человек): ~64%
- Перекрёстное окружение (новая комната): ~17.5% (с CORAL‑выравниванием)[reference:46]
- Для реального развёртывания требуется few‑shot калибровка — небольшое
  количество размеченных данных с места установки восстанавливает
  большую часть точности[reference:47].

Описание файлов проекта
-----------------------

config.py
  Главный конфигурационный файл. Содержит сетевые настройки (UDP_IP,
  UDP_PORT), параметры обработки сигнала (SAMPLING_RATE, фильтры),
  идентификатор модели и форму входа, пороги детекции присутствия,
  лимиты на количество людей, настройки визуализации.

csi_server.py
  Модуль UDP‑сервера. Класс CSIServer: в отдельном потоке слушает порт,
  парсит JSON и кладёт данные в очередь raw_csi_queue.

signal_processor.py
  Модуль предобработки CSI. Класс SignalProcessor: извлекает амплитуды
  из сырых данных, приводит к форме (3, 114), накапливает буфер из
  WINDOW_SIZE последних срезов, формирует тензор (3, 114, 10) и отправляет
  в processed_queue для нейросети.

pose_estimator.py
  Самый важный модуль. Класс PoseEstimator: загружает модель
  wifi-densepose-mmfi-pose (или эмулирует, если недоступна), выполняет
  инференс на тензорах CSI, получает 17 ключевых точек для каждого
  человека, добавляет Z=0, масштабирует в метры, применяет сглаживание,
  отслеживает идентификаторы, детектирует присутствие по энергии,
  выводит список поз с ID в очередь pose_queue. При отсутствии модели
  эмулирует 1‑2 стоячих человека с лёгким движением рук.

visualizer.py
  Визуализация с Open3D. Класс Visualizer: получает списки поз, создаёт
  для каждого человека свою геометрию (сферы + линии) с уникальным цветом,
  добавляет и удаляет скелеты при появлении/исчезновении людей, показывает
  индикатор присутствия (зелёный/красный шар), поддерживает клавиши 1, 2, 3
  для смены цветовых стилей (заглушка).

main.py
  Точка входа. Создаёт очереди, запускает все компоненты в потоках,
  обрабатывает Ctrl+C для корректного завершения.

Установка и запуск
------------------

Docker (рекомендуется):
  cd docker
  docker-compose up --build

Linux (нативная установка):
  git clone https://github.com/senseigus1-stack/wifi-densepose.git
  cd wifi-densepose
  chmod +x scripts/linux/setup.sh
  ./scripts/linux/setup.sh
  source venv/bin/activate
  python main.py

Windows (PowerShell):
  git clone https://github.com/senseigus1-stack/wifi-densepose.git
  cd wifi-densepose
  .\scripts\windows\setup.ps1
  .\venv\Scripts\Activate.ps1
  python main.py

Скрипты установки автоматически проверяют наличие Python, CUDA, RAM,
свободное место и устанавливают все зависимости.

Лицензия и ссылки
-----------------

Проект распространяется под лицензией MIT. Основан на работах:
- Person‑in‑WiFi 3D (CVPR 2024) – первая end‑to‑end многопользовательская
  оценка позы по Wi‑Fi[reference:48].
- WiFi‑DensePose (CMU Master Thesis, 2022) – отображение Wi‑Fi сигналов
  в позы[reference:49].
- WiFi‑Radar (GitHub) – практическая реализация для детекции падений
  и анализа походки.

Исходный код и документация доступны на GitHub:
https://github.com/senseigus1-stack/wifi-densepose


=============================================================================
УДМУРТ КЫЛ (Udmurt)
=============================================================================

Азькыл (Введение)
------------------

WiFi DensePose – Wi‑Fi сигналъёс пыр кык‑укыр адямилэсь позаоссэс (3D)
тодэтъян система. Камераос ӧвӧл, пельосты сурт ӧвӧл – гинэ радиосигналъёс.
CSI (Channel State Information) лыдъёс пыр – адямилэн радиоволнаос вылэ
бертонэз – система 17 ключевой точкаосысь скелет лэсьтэ, 4 адямилы
огпола, стенаос пыр, пемытэн, портативной приборъёс тӥр.

Кутскон (Требования к оборудованию)
-----------------------------------

Компонент            Модель                 Дун (прим.)   Ужан
Микроконтроллер      ESP32‑S3 (CSI‑ен)      ~$10‑15       CSI люканы, UDP‑ын ыстыны
Wi‑Fi роутер         Кылсярысь 2.4 ГГц      (вал)         Сигнал лэсьтон
Компьютер            Linux (Ubuntu) / Win10+ / macOS   —   Нейросеть ужатыны, видмоны
GPU (кулэ)           NVIDIA CUDA            —             Быстро ужатон

Валэктон: обычной Wi‑Fi адаптеръёс CSI лыдъёссэс ӧдъяло. ESP32‑S3 яке
Intel 5300, Atheros AR9580 потэ.

Физической кылдытэт: Wi‑Fi кызьы стенаос пыр адӟе
--------------------------------------------------

Wi‑Fi sensingлэн валэктоныз – радиоволнаослэн быдтонзылэн физикаез но
multipath (трос пумъем) эффект[reference:50].

Роутер сигнал ыштэ куке, электромагнитной волнаос transmitter антеннаысь
receiver антеннаозь трос пумъем быдтэ:
- Чорыгез адӟон (line‑of‑sight)
- Стенаосысь, мебельысь но мукет объектъёсысь вордскем
- Адямилэсь вордскем[reference:51]

Басьтэм сигнал – вань пумъемъёслэн суперпозицизы[reference:52]. Адями
быдэ, ветлэ яке гинэ тышкаке – со вордскем пумъемъёсты вошты:
огпумъемъёс вусэ, выльёс потэ, вордскем волнаослэн фазазы
вошъяське[reference:53].

Та вошъяськонъёссэ CSI люка – кажне субканаллы амплитуда но фаза
кажне transmitter-receiver антенна люкетлы[reference:54]. RSSI (ог
лыд, сигналлэн быдэс кужымез) сэрттыса, CSI багат, трос мертан
даннойёс сётэ, тышкан сямен но дышетэ[reference:55].

CSI лыдъёслэн форматысьтызы
----------------------------

ESP32‑S3 UDP (порт 5566) JSON‑я ыстэ. Пример:

{
  "timestamp": 1640995200.123,
  "mac": "AA:BB:CC:DD:EE:FF",
  "csi": [ [1.23, -0.45], [0.78, 0.12], ... ],
  "amplitude": [1.34, 0.79, ...],
  "phase": [0.12, -0.34, ...]
}

- csi – комплексной лыдъёсын массив (действительной но мнимой люкет)
  вань субканалъёслы но антеннаослы.
- amplitude – амплитудаос (комплексной лыдлэн модулез).
- phase – фазаос (комплексной лыдлэн аргументез).
- Система 3 антенна × 114 субканал возьма. Трос лыд – чаклан,
  тӥрмем – нульосын полон.

ESP32‑S3: люкан прибор
-----------------------

ESP32‑S3 – дунэтӥ микроконтроллер, вӧйыны Wi‑Fi. Espressif‑лэн ESP‑CSI
технологиез CSI лыдъёссэ Wi‑Fi‑лэн PHY уровеньысь басьтыны быгатэ[reference:56][reference:57].

ESP‑CSI кызьы ужа:
- Wi‑Fi OFDM кутылэ, кажне каналыз трос субканалъёслы люка[reference:58].
- Кажне субканаллы чип амплитуда (сигналлэн быдэсэз) но фаза (волналэн
  берпумэн / кытскемез) мерта[reference:59].
- Та лыдъёс PHY уровеньысь басьтэмын но CSI‑колбэк пыр ESP‑IDF API‑лы
  сётэмын[reference:60].
- Даннойёс UDP пыр компьютерлы ыстэмын.

ESP‑CSI‑лэн RSSI сэрттыса бурдэсъёсыз:
- RSSI: ог лыд, утӥсьлыко, быдэс вошъяськонъёс гинэ адӟе[reference:61].
- CSI: кажне субканаллы амплитуда + фаза, кылдытэ, тышкан но адӟе[reference:62].
- CSI интерференциялы (батарейкаос но мукет) тӧро[reference:63].

Трос адямилэсь позаоссэс тодэтъян понна трос антенна кутӥсько.
ESP32‑S3 сое возьма, но внешней роутер сигнал сёте – со 3 антенна ×
114 субканал CSI матрица.

Нейросеть: CSI‑ысь скелетозь
----------------------------

Модель `wifi-densepose-mmfi-pose` (Hugging Face‑ын) кутылэ[reference:64].

Пырон: CSI амплитудаослэн тензорзы [3, 114, 10]
- 3 антенна люкет (пространственной пӧртэмлык)
- 114 субканал (частота пӧртэмлык)
- 10 дыр срез 100 Гц‑эн (дыр динамика)[reference:65]

Архитектура (люкаськем):
1. 10 дыр срез → 10 токен (размер 342 → 256)
2. 4‑слойной / 8‑головой Transformer‑энкодер
3. Дыр attention‑пулинг – валтӥс выльдыт (global‑mean‑pool сэрттыса
   точность 3%‑ысь 48%+‑озь выдӥз)[reference:66]
4. MLP‑декодер + скелет утон йырын (графовой свёртка COCO
   лыдон топологияя)[reference:67]
5. Поттон: [17, 2] ключевой точка [0,1] координатаосын

Модельлэн быдэсэз: ~2.3 млн параметр[reference:68]

Точность (MM‑Fi, torso‑PCK@20):
- CSI2Pose (азьвыл уж): 68.41%
- MultiFormer (азьвыл SOTA, 2025): 72.25%
- Та модель (ог): 82.69%
- Та модель (3‑ансамбль + TTA): 83.59%[reference:69]

Валтӥс гожтэмъёс:
- 82.69% – in‑domain (random split) условиын[reference:70].
- Выль адями (cross‑subject): ~64%
- Выль комната (cross‑environment): ~17.5% (CORAL‑ен)[reference:71]
- Ужам понна few‑shot калибровка кӧс – ужан интыысь унчы лыд
  даннойёс точность бадӟым люкетсэ бертытоз[reference:72].

Файлъёслэн малпамъёссы
----------------------

config.py
  Ужан конфиг: UDP адрес но порт, сигнал фильтрацилэн параметръёсыз
  (SAMPLING_RATE, фильтръёс), модельлэн ID‑ез но пырон форма,
  адямиослэн ваньмодыныз эскерон порогъёс, адямиослэн лыдзы,
  видмонон параметръёс.

csi_server.py
  UDP сервер (класс CSIServer): портъёсты кылё, JSON‑ыз лыдъя,
  raw_csi_queue‑лы пуктэ.

signal_processor.py
  Амплитудаосыз люка, (3, 114)‑лы тупатэ, WINDOW_SIZE срезъёсыз
  люка, (3, 114, 10) тензор лэсьтэ но processed_queue‑лы пуктэ.

pose_estimator.py
  Модельэз (wifi‑densepose‑mmfi‑pose) люка, инференс каре, 17
  ключевой точкаосыз басьтэ, Z=0 сэрттэ, метръёсы шкала каре,
  смазка каре, адямиослы ID сетэ, присутствие эскере (энергия пыр),
  позаослэн списоксэсты ID‑ен pose_queue‑лы пуктэ. Модель ӧвӧл
  ке – 1‑2 адямилы вӧзьыт скелет лэсьтэ (демонстрация понна).

visualizer.py
  Open3D‑ын видмоно. Класс Visualizer: позаослэн списоксэсты
  басьтэ, кажне адямилы своёй геометриос (шариксэс но гинсы)
  лэсьтэ, буёлъёсыз пӧртэм, адямиос валэктон но быдтон дыръя
  скелетъёсты сэрттэ но быдтэ, присутствие индикатор (зелёной /
  горд шар) возьматэ, 1, 2, 3 клавишаосын буёлъёсты воштыны
  быгатэ (заглушка).

main.py
  Кутскон (точка входа). Очередьёсыз лэсьтэ, вань компонентъёсты
  отдельной потокъёсын кутэ, Ctrl+C‑лэсь дугдытэ (чисто остановка).

Установка но угон
-----------------

Docker (эсэгетэм):
  cd docker
  docker-compose up --build

Linux (нативной):
  git clone https://github.com/senseigus1-stack/wifi-densepose.git
  cd wifi-densepose
  chmod +x scripts/linux/setup.sh
  ./scripts/linux/setup.sh
  source venv/bin/activate
  python main.py

Windows (PowerShell):
  git clone https://github.com/senseigus1-stack/wifi-densepose.git
  cd wifi-densepose
  .\scripts\windows\setup.ps1
  .\venv\Scripts\Activate.ps1
  python main.py

Установка скриптъёс Python, CUDA, RAM, диск пространство эскеро,
вань зависимостьёсыз пуктэ.

Лицензия но ссылкаос
--------------------

MIT лицензия. Ужпумъёс (основано на):
- Person‑in‑WiFi 3D (CVPR 2024) – нырысетӥз мульти‑адямилэн
  Wi‑Fi пырозы позаоссэс тодэтъян[reference:73].
- WiFi‑DensePose (CMU Master Thesis, 2022) – Wi‑Fi сигналъёсты
  позаослы тупатъян[reference:74].
- WiFi‑Radar (GitHub) – практической падение лыдъян но походка
  анализ.

Код GitHub‑ын: https://github.com/senseigus1-stack/wifi-densepose
