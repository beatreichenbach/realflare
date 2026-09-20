import dataclasses
import random
from collections.abc import MutableSequence, Sequence

import numpy as np


@dataclasses.dataclass
class Point:
    x: float
    y: float


@dataclasses.dataclass
class Circle:
    c: Point
    r: float


def length(a: Point, b: Point) -> float:
    return float(np.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2))


def is_inside(circle: Circle, point: Point) -> bool:
    return length(circle.c, point) <= circle.r


def get_circle_from_three(a: Point, b: Point, c: Point) -> Circle:
    det = (a.x - b.x) * (b.y - c.y) - (b.x - c.x) * (a.y - b.y)
    if abs(det) < 1.0e-6:
        return Circle(Point(0, 0), 0)

    a2 = a.x**2 + a.y**2
    b2 = b.x**2 + b.y**2
    c2 = c.x**2 + c.y**2

    d = (a2 - b2) / 2
    e = (b2 - c2) / 2

    cx = (d * (b.y - c.y) - e * (a.y - b.y)) / det
    cy = (e * (a.x - b.x) - d * (b.x - c.x)) / det
    center = Point(cx, cy)
    radius = length(center, a)
    return Circle(center, radius)


def get_circle_from_two(a: Point, b: Point) -> Circle:
    center = Point((a.x + b.x) / 2, (a.y + b.y) / 2)
    radius = length(a, b) / 2
    return Circle(center, radius)


def get_circle(points: Sequence[Point]) -> Circle:
    if not points:
        return Circle(Point(0, 0), 0)
    elif len(points) == 1:
        return Circle(points[0], 0)
    elif len(points) == 2:
        return get_circle_from_two(points[0], points[1])

    for i in range(3):
        for j in range(i + 1, 3):
            circle = get_circle_from_two(points[i], points[j])
            if all(is_inside(circle, point) for point in points):
                return circle
    return get_circle_from_three(points[0], points[1], points[2])


def _welzl(
    points: MutableSequence[Point], remainder: Sequence[Point], num_points: int
) -> Circle:
    if num_points == 0 or len(remainder) == 3:
        remainder_copy = remainder[:]
        return get_circle(remainder_copy)

    # index = random.randint(0, num_points - 1)
    index = 0
    point = points[index]
    points[index], points[num_points - 1] = points[num_points - 1], points[index]

    circle = _welzl(points, remainder, num_points - 1)

    if is_inside(circle, point):
        return circle

    remainder_copy = (*remainder, point)
    return _welzl(points, remainder_copy, num_points - 1)


def welzl(points: Sequence[Point]) -> Circle:
    points_copy = list(points)
    random.shuffle(points_copy)
    return _welzl(points_copy, [], len(points_copy))


def main() -> None:
    test_points = [
        Point(5, -2),
        Point(-3, -2),
        Point(-2, 5),
        Point(1, 6),
        Point(0, 2),
    ]

    circle = welzl(test_points)
    print(circle)


if __name__ == '__main__':
    main()
