import asyncio
import json
import logging
from typing import Callable, Awaitable
from .config import config

logger = logging.getLogger(__name__)

class CSIServer:
    """Асинхронный UDP-сервер для приёма CSI-данных с ESP32-S3."""
    
    def __init__(self, callback: Callable[[dict], Awaitable[None]]):
        self.callback = callback
        self.transport = None
        self.protocol = None
        self._running = False
        
    async def start(self):
        """Запуск сервера."""
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: CSIProtocol(self.callback),
            local_addr=(config.udp_ip, config.udp_port)
        )
        self._running = True
        logger.info(f"UDP server started on {config.udp_ip}:{config.udp_port}")
        
    async def stop(self):
        """Остановка сервера."""
        if self.transport:
            self.transport.close()
        self._running = False
        logger.info("UDP server stopped")

class CSIProtocol(asyncio.DatagramProtocol):
    def __init__(self, callback):
        self.callback = callback
        
    def datagram_received(self, data, addr):
        try:
            payload = json.loads(data.decode('utf-8'))
            asyncio.create_task(self.callback(payload))
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from {addr}")
        except Exception as e:
            logger.error(f"Error processing datagram: {e}")