# csi_server.py
import socket
import json
import threading
import queue
import logging
from config import UDP_IP, UDP_PORT

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CSIServer:
    """UDP сервер для приёма CSI-данных с ESP32-S3."""

    def __init__(self, data_queue: queue.Queue):
        self.data_queue = data_queue
        self.running = False
        self.sock = None
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logging.info(f"UDP CSI сервер запущен на {UDP_IP}:{UDP_PORT}")

    def _run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((UDP_IP, UDP_PORT))
        self.sock.settimeout(1.0)

        while self.running:
            try:
                data, addr = self.sock.recvfrom(65535)
                csi_data = json.loads(data.decode('utf-8'))
                self.data_queue.put(csi_data)
            except socket.timeout:
                continue
            except json.JSONDecodeError as e:
                logging.warning(f"Ошибка декодирования JSON: {e}")
            except Exception as e:
                logging.error(f"Ошибка в UDP-сервере: {e}")

        if self.sock:
            self.sock.close()
        logging.info("UDP CSI сервер остановлен")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)