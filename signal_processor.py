import numpy as np
from scipy import signal
from collections import deque
import logging
from .config import config

logger = logging.getLogger(__name__)

class SignalProcessor:
    """Обработка CSI-сигнала: фильтрация, буферизация, детекция движения."""
    
    def __init__(self):
        self.buffer = deque(maxlen=config.window_size)
        # Фильтр Баттерворта 4-го порядка
        self.b, self.a = signal.butter(
            4, [config.filter_low, config.filter_high],
            btype='band', fs=config.sampling_rate
        )
        self._energy_history = deque(maxlen=10)
        self._presence = False
        self._last_activity = 0.0
        
    def process(self, raw_data: dict) -> np.ndarray | None:
        """Принимает сырой CSI-пакет, возвращает тензор (3,114,10) или None."""
        try:
            # Извлечение амплитуд
            if 'csi' in raw_data:
                csi_complex = np.array(raw_data['csi'], dtype=complex)
                amps = np.abs(csi_complex)
            elif 'amplitude' in raw_data:
                amps = np.array(raw_data['amplitude'])
            else:
                return None
                
            # Приведение к (3, 114)
            if amps.ndim == 1:
                amps = amps.reshape(3, -1)[:, :114]
            elif amps.ndim == 2:
                amps = amps[:3, :114]
            else:
                return None
                
            # Фильтрация (упрощённо, можно применить к каждому субканалу)
            # Здесь можно применить фильтр в реальном времени, но для простоты оставляем
            filtered = self._apply_filter(amps)
            
            self.buffer.append(filtered)
            self._update_presence(filtered)
            
            if len(self.buffer) == config.window_size:
                tensor = np.stack(list(self.buffer), axis=-1)
                return tensor
            return None
        except Exception as e:
            logger.debug(f"Processing error: {e}")
            return None
            
    def _apply_filter(self, amps: np.ndarray) -> np.ndarray:
        # В реальном проекте здесь применяется фильтр к каждому субканалу
        # (требует хранения истории для filtfilt)
        return amps
        
    def _update_presence(self, amps: np.ndarray):
        energy = np.mean(np.abs(amps))
        self._energy_history.append(energy)
        avg_energy = np.mean(self._energy_history) if self._energy_history else 0
        if avg_energy > config.presence_energy_threshold:
            self._presence = True
            self._last_activity = time.time()
        elif time.time() - self._last_activity > config.presence_timeout:
            self._presence = False
            
    @property
    def presence(self) -> bool:
        return self._presence