# signal_processor.py
import numpy as np
from scipy import signal
from collections import deque
import queue
import threading
import logging
from config import SAMPLING_RATE, FILTER_LOW, FILTER_HIGH, WINDOW_SIZE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SignalProcessor:
    """
    Обрабатывает сырые CSI-данные:
    - извлекает амплитуды по субканалам
    - фильтрует сигнал
    - накапливает буфер для подачи в нейросеть
    """

    def __init__(self, input_queue: queue.Queue, output_queue: queue.Queue):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.running = False
        self.thread = None

        # Буфер: храним WINDOW_SIZE последних срезов
        # Каждый срез: 3 антенны × 114 субканалов
        self.buffer = deque(maxlen=WINDOW_SIZE)

        # Проектируем полосовой фильтр
        self.b, self.a = signal.butter(4, [FILTER_LOW, FILTER_HIGH],
                                       btype='band', fs=SAMPLING_RATE)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logging.info("Обработчик сигналов запущен")

    def _run(self):
        while self.running:
            try:
                csi_data = self.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Извлекаем амплитуды (ESP32-S3 шлёт комплексные CSI)
            try:
                if 'csi' in csi_data:
                    csi_complex = np.array(csi_data['csi'], dtype=complex)
                    amplitudes = np.abs(csi_complex)
                elif 'amplitude' in csi_data:
                    amplitudes = np.array(csi_data['amplitude'])
                else:
                    continue

                # Приводим к форме (3, 114)
                if amplitudes.ndim == 1:
                    amplitudes = amplitudes.reshape(3, -1)[:, :114]
                elif amplitudes.ndim == 2:
                    amplitudes = amplitudes[:3, :114]

                # Применяем фильтр (упрощённо)
                filtered = self._apply_filter(amplitudes)
                self.buffer.append(filtered)

                if len(self.buffer) == WINDOW_SIZE:
                    tensor = np.stack(list(self.buffer), axis=-1)
                    self.output_queue.put(tensor)

            except Exception as e:
                logging.debug(f"Ошибка обработки CSI: {e}")

        logging.info("Обработчик сигналов остановлен")

    def _apply_filter(self, amplitudes):
        # В реальном проекте здесь применяется фильтр
        return amplitudes

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)