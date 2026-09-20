from collections import defaultdict

import numpy as np


class DiscMesh:
    @staticmethod
    def get_vertices(radius: float, resolution: int) -> np.ndarray:
        """Return the vertex positions for a triangulated disc."""

        length = 1 / resolution

        vertices = [(0.0, 0.0, 0.0)]
        for circle in range(resolution):
            scale = length * (circle + 1)
            angle = 2 * np.pi / ((circle + 1) * 6)
            for point in range((circle + 1) * 6):
                x = radius * np.cos(angle * point) * scale
                y = radius * np.sin(angle * point) * scale
                z = 0
                vertices.append((x, y, z))

        array = np.array(vertices, dtype=np.float32)
        return array

    @staticmethod
    def get_index(circle: int, point: int) -> int:
        """Return the index of a point in a circle."""

        if circle < 0:
            return 0

        local_count = (circle + 1) * 6
        local_index = point % local_count
        # index = center_point + number of points in previous circles + point
        index = 1 + (3 * circle * (circle + 1)) + local_index
        return index

    @staticmethod
    def get_indices(resolution: int) -> np.ndarray:
        """Return the triangle vertex indices for a triangulated disc mesh."""

        # Loop through the outer circle and create 2 triangles and every (circle + 1)
        # times a single triangle.
        indices = []
        for circle in range(resolution):
            inner_circle = circle - 1
            inner_point = 0
            point_count = (circle + 1) * 6
            for point in range(point_count):
                if point % (circle + 1) == 0:
                    indices.append(
                        (
                            DiscMesh.get_index(inner_circle, inner_point),
                            DiscMesh.get_index(circle, point + 1),
                            DiscMesh.get_index(circle, point),
                        )
                    )
                else:
                    indices.append(
                        (
                            DiscMesh.get_index(inner_circle, inner_point),
                            DiscMesh.get_index(inner_circle, inner_point + 1),
                            DiscMesh.get_index(circle, point),
                        )
                    )
                    indices.append(
                        (
                            DiscMesh.get_index(inner_circle, inner_point + 1),
                            DiscMesh.get_index(circle, point + 1),
                            DiscMesh.get_index(circle, point),
                        )
                    )
                    inner_point += 1

        array = np.array(indices)
        return array

    @staticmethod
    def get_triangles(radius: float, resolution: int) -> np.ndarray:
        """Return the vertex positions for a triangulated disc mesh."""

        vertices = DiscMesh.get_vertices(radius=radius, resolution=resolution)
        indices = DiscMesh.get_indices(resolution=resolution)
        array = vertices[indices.flatten()]
        return array

    @staticmethod
    def get_positions(radius: float, resolution: int) -> np.ndarray:
        """Return the unique vertex positions for a triangulated disc mesh."""

        vertices = DiscMesh.get_vertices(radius=radius, resolution=resolution)
        indices = DiscMesh.get_indices(resolution=resolution)
        array = vertices[np.unique(indices)]
        return array

    @staticmethod
    def get_neighbors(resolution: int) -> np.ndarray:
        """Return an array with all neighbors (face ids) per vertex."""

        tris = DiscMesh.get_indices(resolution)

        data = defaultdict(list)
        for face_id, vertex_ids in enumerate(tris):
            for vertex_id in vertex_ids:
                data[vertex_id].append(face_id)

        neighbors = -np.ones((len(data), 6), np.int32)
        for vertex_id, face_ids in data.items():
            neighbors[vertex_id, : len(face_ids)] = face_ids

        return neighbors

    @staticmethod
    def get_triangle_area(radius: float, resolution: int) -> float:
        """Return the original area for a triangle."""

        # Because not all triangles are the same size, the easiest approximation is to
        # get the area of the disc mesh and divide ti by the number of triangles.
        area_disc = np.pi * radius**2
        triangle_count = DiscMesh.get_triangle_count(resolution)
        area = area_disc / triangle_count
        return area

    @staticmethod
    def get_vertex_count(resolution: int) -> int:
        """Return the number of vertices in a disc mesh."""

        return 1 + (3 * resolution * (resolution + 1))

    @staticmethod
    def get_triangle_count(resolution: int) -> int:
        """Return the number of triangles in a disc mesh."""

        return resolution**2 * 6
