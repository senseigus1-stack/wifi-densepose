# visualizer.py
import open3d as o3d
import numpy as np
import queue
import threading
import logging
import time
from config import VIZ_WIDTH, VIZ_HEIGHT

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Visualizer:
    CONNECTIONS = [
        (0, 1), (1, 2), (1, 3), (2, 4), (3, 5),
        (4, 6), (5, 7), (1, 8), (8, 9), (8, 10),
        (9, 11), (10, 12)
    ]

    # Палитра цветов для разных людей
    COLORS = [
        [1.0, 0.2, 0.2],  # Красный
        [0.2, 0.8, 0.2],  # Зелёный
        [0.2, 0.4, 1.0],  # Синий
        [1.0, 0.8, 0.0],  # Жёлтый
        [1.0, 0.0, 1.0],  # Пурпурный
        [0.0, 1.0, 1.0],  # Бирюзовый
    ]

    def __init__(self, input_queue: queue.Queue):
        self.input_queue = input_queue
        self.running = False
        self.thread = None
        self.poses = []
        self.present = False
        self.person_count = 0

        # Хранилище геометрии для каждого человека
        self.person_geometries = {}  # id -> {"spheres": [], "line_set": line_set}

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logging.info("Визуализатор (Multi-Person) запущен")

    def _get_color(self, person_id):
        return self.COLORS[person_id % len(self.COLORS)]

    def _create_person_geometry(self, person_id):
        color = self._get_color(person_id)
        spheres = []
        for _ in range(17):
            sphere = o3d.geometry.TriangleMesh.create_sphere(radius=0.04)
            sphere.paint_uniform_color(color)
            spheres.append(sphere)
        line_set = o3d.geometry.LineSet()
        line_set.paint_uniform_color(color)
        return {"spheres": spheres, "line_set": line_set}

    def _update_person_pose(self, vis, person_id, pose, geometries):
        spheres = geometries["spheres"]
        line_set = geometries["line_set"]

        # Обновляем сферы
        for i, sphere in enumerate(spheres):
            if i < len(pose):
                sphere.translate(pose[i] - sphere.get_center(), relative=False)
                vis.update_geometry(sphere)

        # Обновляем линии
        points = np.array(pose)
        lines_points = []
        for (i, j) in self.CONNECTIONS:
            if i < len(points) and j < len(points):
                lines_points.append(points[i])
                lines_points.append(points[j])

        if lines_points:
            lines_points = np.array(lines_points)
            new_line_set = o3d.geometry.LineSet()
            new_line_set.points = o3d.utility.Vector3dVector(lines_points)
            line_indices = [[i, i+1] for i in range(0, len(lines_points), 2)]
            new_line_set.lines = o3d.utility.Vector2iVector(line_indices)
            new_line_set.paint_uniform_color(self._get_color(person_id))

            vis.remove_geometry(line_set)
            line_set = new_line_set
            vis.add_geometry(line_set)
            geometries["line_set"] = line_set

    def _hide_person(self, vis, person_id, geometries):
        for sphere in geometries["spheres"]:
            sphere.translate([0, 0, 10] - sphere.get_center(), relative=False)
            vis.update_geometry(sphere)
        vis.remove_geometry(geometries["line_set"])

    def _run(self):
        vis = o3d.visualization.Visualizer()
        vis.create_window(window_name="WiFi DensePose — Multi-Person 3D Skeleton",
                          width=VIZ_WIDTH, height=VIZ_HEIGHT)

        # Координатные оси
        axis = o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.3, origin=[0, 0, 0])
        vis.add_geometry(axis)

        # Индикатор присутствия (зелёный/красный)
        presence_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=0.05)
        presence_sphere.paint_uniform_color([0, 1, 0])
        presence_sphere.translate([-0.5, 1.9, 0])
        vis.add_geometry(presence_sphere)

        while self.running:
            try:
                data = self.input_queue.get(timeout=0.1)
                self.poses = data.get('poses', [])
                self.present = data.get('present', False)
                self.person_count = data.get('count', 0)
            except queue.Empty:
                pass

            # Получаем ID людей из текущих данных
            current_ids = {p['id'] for p in self.poses}

            # Удаляем геометрию для людей, которых больше нет
            for pid in list(self.person_geometries.keys()):
                if pid not in current_ids:
                    self._hide_person(vis, pid, self.person_geometries[pid])
                    del self.person_geometries[pid]

            # Обновляем или создаём геометрию для каждого человека
            for person_data in self.poses:
                pid = person_data['id']
                pose = np.array(person_data['pose'])

                if pid not in self.person_geometries:
                    geom = self._create_person_geometry(pid)
                    self.person_geometries[pid] = geom
                    for sphere in geom["spheres"]:
                        vis.add_geometry(sphere)
                    vis.add_geometry(geom["line_set"])

                self._update_person_pose(vis, pid, pose, self.person_geometries[pid])

            # Обновляем индикатор присутствия
            if self.present and self.person_count > 0:
                presence_sphere.paint_uniform_color([0, 1, 0])
            else:
                presence_sphere.paint_uniform_color([1, 0, 0])
            vis.update_geometry(presence_sphere)

            vis.poll_events()
            vis.update_renderer()
            time.sleep(0.02)

        vis.destroy_window()
        logging.info("Визуализатор остановлен")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)