# main.py
import queue
import time
import logging
import signal
import sys

from csi_server import CSIServer
from signal_processor import SignalProcessor
from pose_estimator import PoseEstimator
from visualizer import Visualizer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Очереди
raw_csi_queue = queue.Queue()
processed_queue = queue.Queue()
pose_queue = queue.Queue()

def signal_handler(sig, frame):
    logging.info("Получен сигнал завершения...")
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)

    logging.info("=" * 50)
    logging.info("🚀 WiFi DensePose — Multi-Person Real-time")
    logging.info("=" * 50)

    # Создаём компоненты
    csi_server = CSIServer(raw_csi_queue)
    signal_processor = SignalProcessor(raw_csi_queue, processed_queue)
    pose_estimator = PoseEstimator(processed_queue, pose_queue)
    visualizer = Visualizer(pose_queue)

    # Запускаем
    csi_server.start()
    signal_processor.start()
    pose_estimator.start()
    visualizer.start()

    logging.info("✅ Все компоненты запущены. Нажмите Ctrl+C для выхода.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("Останавливаем компоненты...")
        csi_server.stop()
        signal_processor.stop()
        pose_estimator.stop()
        visualizer.stop()
        logging.info("Программа завершена.")

if __name__ == "__main__":
    main()