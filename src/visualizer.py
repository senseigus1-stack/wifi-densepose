import open3d as o3d
import numpy as np
import time
import logging
from collections import deque
from .config import config

logger = logging.getLogger(__name__)

class Visualizer:
    """Улучшенный 3D-визуализатор с полом, сеткой, легендой и анимацией."""
    
    CONNECTIONS = [
        (0,1),(1,2),(1,3),(2,4),(3,5),
        (4,6),(5,7),(1,8),(8,9),(8,10),
        (9,11),(10,12)
    ]
    COLORS = [
        [1,0.2,0.2], [0.2,0.8,0.2], [0.2,0.4,1.0],
        [1,0.8,0.0], [1,0.0,1.0], [0.0,1,1]
    ]
    
    def __init__(self):
        self.window_name = "WiFi DensePose — 3D Skeleton Viewer"
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window(window_name=self.window_name, 
                               width=config.viz_width, height=config.viz_height)
        self._setup_scene()
        self._person_geometries = {}  # id -> {spheres, lines}
        self._pose_history = {}       # id -> deque for smoothing
        
    def _setup_scene(self):
        # Пол (сетка)
        grid = o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.5, origin=[0,0,0])
        self.vis.add_geometry(grid)
        
        # Добавим полусферу для индикатора присутствия
        self.presence_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=0.05)
        self.presence_sphere.paint_uniform_color([0,1,0])
        self.presence_sphere.translate([-0.5, 1.9, 0])
        self.vis.add_geometry(self.presence_sphere)
        
        # Добавим текст (можно через точки, но для простоты оставим)
        logger.info("Scene setup complete")
        
    def update(self, poses: list[dict], presence: bool):
        """Обновляет сцену на основе списка поз и статуса присутствия."""
        current_ids = {p['id'] for p in poses}
        
        # Удаляем исчезнувших
        for pid in list(self._person_geometries.keys()):
            if pid not in current_ids:
                self._remove_person(pid)
                
        # Обновляем или добавляем
        for p in poses:
            pid = p['id']
            pose = np.array(p['pose'])
            if pid not in self._person_geometries:
                self._add_person(pid)
            self._update_person(pid, pose)
            
        # Индикатор присутствия
        if presence and len(poses)>0:
            self.presence_sphere.paint_uniform_color([0,1,0])
        else:
            self.presence_sphere.paint_uniform_color([1,0,0])
        self.vis.update_geometry(self.presence_sphere)
        
        self.vis.poll_events()
        self.vis.update_renderer()
        
    def _add_person(self, pid):
        color = self.COLORS[pid % len(self.COLORS)]
        spheres = []
        for _ in range(17):
            sphere = o3d.geometry.TriangleMesh.create_sphere(radius=0.04)
            sphere.paint_uniform_color(color)
            spheres.append(sphere)
            self.vis.add_geometry(sphere)
        line_set = o3d.geometry.LineSet()
        line_set.paint_uniform_color(color)
        self.vis.add_geometry(line_set)
        self._person_geometries[pid] = {'spheres': spheres, 'line_set': line_set}
        # История для сглаживания
        self._pose_history[pid] = deque(maxlen=5)
        
    def _remove_person(self, pid):
        if pid in self._person_geometries:
            for sphere in self._person_geometries[pid]['spheres']:
                self.vis.remove_geometry(sphere)
            self.vis.remove_geometry(self._person_geometries[pid]['line_set'])
            del self._person_geometries[pid]
            if pid in self._pose_history:
                del self._pose_history[pid]
                
    def _update_person(self, pid, pose):
        # Сглаживание
        history = self._pose_history.get(pid, deque(maxlen=5))
        history.append(pose)
        if len(history) > 1:
            smoothed = np.mean(history, axis=0)
        else:
            smoothed = pose
            
        geom = self._person_geometries[pid]
        spheres = geom['spheres']
        line_set = geom['line_set']
        
        # Обновляем сферы
        for i, sphere in enumerate(spheres):
            if i < len(smoothed):
                sphere.translate(smoothed[i] - sphere.get_center(), relative=False)
                self.vis.update_geometry(sphere)
                
        # Обновляем линии
        points = smoothed
        lines_points = []
        for (i,j) in self.CONNECTIONS:
            if i < len(points) and j < len(points):
                lines_points.append(points[i])
                lines_points.append(points[j])
        if lines_points:
            lines_points = np.array(lines_points)
            new_line_set = o3d.geometry.LineSet()
            new_line_set.points = o3d.utility.Vector3dVector(lines_points)
            line_indices = [[i, i+1] for i in range(0, len(lines_points), 2)]
            new_line_set.lines = o3d.utility.Vector2iVector(line_indices)
            new_line_set.paint_uniform_color(self.COLORS[pid % len(self.COLORS)])
            self.vis.remove_geometry(line_set)
            self.vis.add_geometry(new_line_set)
            geom['line_set'] = new_line_set
            
    def close(self):
        self.vis.destroy_window()
        logger.info("Visualizer closed")