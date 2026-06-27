import asyncio
import logging
import signal
import sys
from src.config import config
from src.csi_server import CSIServer
from src.signal_processor import SignalProcessor
from src.pose_estimator import PoseEstimator
from src.visualizer import Visualizer

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class App:
    def __init__(self):
        self.signal_proc = SignalProcessor()
        self.pose_est = PoseEstimator()
        self.visualizer = Visualizer()
        self._running = True
        
    async def handle_csi_data(self, raw_data: dict):
        """Callback для CSI-сервера."""
        tensor = self.signal_proc.process(raw_data)
        if tensor is not None:
            poses = self.pose_est.predict(tensor)
            presence = self.signal_proc.presence
            self.visualizer.update(poses, presence)
            
    async def run(self):
        server = CSIServer(self.handle_csi_data)
        await server.start()
        logger.info("Application started")
        
        # Обработка завершения
        def shutdown():
            self._running = False
            logger.info("Shutdown signal received")
            
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown)
            
        while self._running:
            await asyncio.sleep(0.1)
            
        await server.stop()
        self.visualizer.close()
        logger.info("Application stopped")
        
if __name__ == "__main__":
    app = App()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")