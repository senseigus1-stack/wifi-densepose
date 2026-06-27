# pose_estimator.py
import numpy as np
import queue
import threading
import logging
import time
from collections import deque
from config import (
    PRESENCE_ENERGY_THRESHOLD, PRESENCE_TIMEOUT,
    SMOOTHING_ALPHA, PERSON_ID_TIMEOUT, MAX_PEOPLE
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PoseEstimator:
    """
    Загружает модель WiFi-Radar для multi-person pose estimation.
    Возвращает список поз для всех обнаруженных людей.
    """
    def __init__(self, input_queue: queue.Queue, output_queue: queue.Queue):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.running = False
        self.thread = None
        self.model = None
        self.model_loaded = False

        # Для сглаживания поз каждого человека
        self.smooth_poses = {}  # id -> поза
        self.last_activity_time = time.time()
        self.energy_history = deque(maxlen=10)

    def start(self):
        if self.running:
            return
        self._load_model()
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logging.info("Модуль оценки позы (Multi-Person) запущен")

    def _load_model(self):
        """Загружает модель WiFi-Radar (или использует эмуляцию)."""
        try:
            # Попытка импортировать реальную модель
            from wifi_radar import WiFiRadar
            self.model = WiFiRadar()
            self.model_loaded = True
            logging.info("✅ Модель WiFi-Radar успешно загружена!")
        except ImportError:
            logging.warning("⚠️ WiFi-Radar не найден. Используем симуляцию нескольких людей.")
            self.model_loaded = False
        except Exception as e:
            logging.error(f"❌ Ошибка загрузки модели: {e}")
            self.model_loaded = False

    def _run(self):
        while self.running:
            try:
                csi_tensor = self.input_queue.get(timeout=0.1)
            except queue.Empty:
                # Если долго нет данных — считаем, что людей нет
                if time.time() - self.last_activity_time > PRESENCE_TIMEOUT:
                    self.output_queue.put({'poses': [], 'present': False})
                continue

            # Вычисляем энергию сигнала
            energy = np.mean(np.abs(csi_tensor))
            self.energy_history.append(energy)
            avg_energy = np.mean(self.energy_history) if self.energy_history else 0

            # Детекция присутствия
            if avg_energy > PRESENCE_ENERGY_THRESHOLD:
                self.last_activity_time = time.time()
                person_present = True
            else:
                if time.time() - self.last_activity_time > PRESENCE_TIMEOUT:
                    self.output_queue.put({'poses': [], 'present': False})
                    continue
                person_present = True

            # Инференс модели
            if self.model_loaded and self.model is not None:
                try:
                    raw_poses = self.model.predict(csi_tensor)
                except Exception as e:
                    logging.debug(f"Ошибка инференса: {e}")
                    raw_poses = []
            else:
                # Эмуляция: 1-2 случайных человека
                raw_poses = self._simulate_poses()

            # Ограничиваем количество людей
            if len(raw_poses) > MAX_PEOPLE:
                raw_poses = raw_poses[:MAX_PEOPLE]

            # Сглаживание
            smoothed_poses = []
            current_ids = {p['id'] for p in raw_poses}

            # Удаляем старые ID
            for pid in list(self.smooth_poses.keys()):
                if pid not in current_ids:
                    del self.smooth_poses[pid]

            for raw in raw_poses:
                pid = raw['id']
                pose = np.array(raw['pose'])  # (17, 3)

                if pid in self.smooth_poses:
                    prev = self.smooth_poses[pid]
                    pose = (1 - SMOOTHING_ALPHA) * prev + SMOOTHING_ALPHA * pose
                self.smooth_poses[pid] = pose

                smoothed_poses.append({
                    'id': pid,
                    'pose': pose.tolist()
                })

            # Отправляем результат
            self.output_queue.put({
                'timestamp': time.time(),
                'poses': smoothed_poses,
                'present': person_present and len(smoothed_poses) > 0,
                'count': len(smoothed_poses)
            })

    def _simulate_poses(self):
        """Генерирует симулированные позы для 1-2 человек."""
        import random
        num_people = random.randint(1, 2)
        poses = []
        for i in range(num_people):
            # Базовая стоячая поза со случайным смещением
            pose = np.array([
                [0.0, 1.7, 0.0],
                [0.0, 1.6, 0.0],
                [0.3, 1.5, 0.0],
                [-0.3, 1.5, 0.0],
                [0.5, 1.2, 0.0],
                [-0.5, 1.2, 0.0],
                [0.4, 0.9, 0.0],
                [-0.4, 0.9, 0.0],
                [0.1, 1.2, 0.0],
                [0.1, 0.8, 0.0],
                [-0.1, 0.8, 0.0],
                [0.1, 0.4, 0.0],
                [-0.1, 0.4, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0]
            ])
            # Случайное смещение по X для разных людей
            pose[:, 0] += (i - 0.5) * 0.5
            # Случайное движение рук
            pose[4, 0] += random.uniform(-0.2, 0.2)
            pose[5, 0] += random.uniform(-0.2, 0.2)
            poses.append({'id': i, 'pose': pose})
        return poses

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        logging.info("Модуль оценки позы остановлен")