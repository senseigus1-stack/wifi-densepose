import numpy as np
import torch
from transformers import AutoModelForImageClassification
import logging
from .config import config

logger = logging.getLogger(__name__)

class PoseEstimator:
    """Загрузка модели и преобразование CSI-тензора в 3D-позы."""
    
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self._load_model()
        
    def _load_model(self):
        try:
            logger.info(f"Loading model {config.model_id} on {self.device}...")
            self.model = AutoModelForImageClassification.from_pretrained(
                config.model_id,
                cache_dir=config.models_dir
            ).to(self.device)
            self.model.eval()
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model = None
            
    def predict(self, tensor: np.ndarray) -> list[dict]:
        """Принимает тензор (3,114,10), возвращает список поз [{'id': 0, 'pose': (17,3)}]."""
        if self.model is None:
            return self._simulate_poses()
            
        try:
            # Подготовка входных данных
            input_tensor = torch.from_numpy(tensor).float().unsqueeze(0).to(self.device)
            with torch.no_grad():
                outputs = self.model(input_tensor)
            # Предположим, что модель возвращает логиты (17*2)
            keypoints = outputs.logits.cpu().numpy()[0]  # (34,)
            keypoints_2d = keypoints.reshape(17, 2)
            # Нормализация и масштабирование
            keypoints_3d = np.zeros((17, 3))
            keypoints_3d[:, :2] = keypoints_2d
            keypoints_3d[:, 0] = (keypoints_3d[:, 0] - 0.5) * 1.2
            keypoints_3d[:, 1] = keypoints_3d[:, 1] * 1.8
            # Возвращаем в формате списка
            return [{'id': 0, 'pose': keypoints_3d.tolist()}]
        except Exception as e:
            logger.debug(f"Inference error: {e}")
            return []
            
    def _simulate_poses(self) -> list[dict]:
        # Эмуляция для демонстрации
        import random
        num_people = random.randint(1, 2)
        poses = []
        for i in range(num_people):
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
            pose[:, 0] += (i - 0.5) * 0.5
            poses.append({'id': i, 'pose': pose.tolist()})
        return poses