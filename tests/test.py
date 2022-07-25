import logging
import os
import sys
import time
import math

import numpy as np
import pyopencl as cl


def compare_arrays():
    a = np.zeros((1000, 2000), np.float32)
    b = np.empty((2000, 2000), np.float32)
    stime = time.time()
    print((a == b).all())
    print(time.time() - stime)
    print(sys.getsizeof(b))


# 'renderer': {
#     'resolution': Int2(256, 256),
#     'subdivisions': 2,
#     'filter': Filter.BOX,
#     'filter_size': 2
# },
# 'aperture': {
#     'f-stop': 8,
#     'file': '',
#     'blades': 6,
#     'rotation': 0,
#     'corner_radius': 0,
#     'softness': 0,
# },
# 'ghost': {
#     'alpha': 0.1,
# }


def cl_get_buffer_size():
    logging.getLogger().setLevel(logging.DEBUG)
    context = cl.create_some_context(interactive=False)
    command_queue = cl.CommandQueue(context)

    # load source
    source = ''
    with open(os.path.join(os.path.dirname(__file__), '../api/cl', 'test.cl')) as f:
        source = f.read()

    program = cl.Program(context, source).build()
    kernel = cl.Kernel(program, 'get_buffer_size')

    # create output buffer

    debug = np.zeros([10], cl.cltypes.float)
    debug_cl = cl.Buffer(context, cl.mem_flags.WRITE_ONLY, debug.nbytes)
    logging.debug(debug_cl.get_info(cl.mem_info.MAP_COUNT))

    # run program
    # kernel.set_arg(0, debug_cl)

    global_work_size = debug.shape
    local_work_size = None
    cl.enqueue_nd_range_kernel(command_queue, kernel, global_work_size, local_work_size)

    # copy gpu buffer to cpu
    cl.enqueue_copy(command_queue, debug, debug_cl)
    logging.debug(debug)
    return debug


def distance_point_line(pos, point0, point1):
    m = (point1[1] - point0[1]) / (point1[0] - point0[0])
    q = point0[1] - m * point0[0]
    # logging.debug((f'y = {m} * x + {q}'))
    d = abs(m * pos[0] - pos[1] + q) / math.sqrt(m * m + 1)
    return d


def distance():
    pos = (0, 0)
    point0 = (1, -13 / 4)
    point1 = (-14 / 3, 1)
    logging.debug(3 * point1[0] + 4 * point1[1] + 10)
    logging.debug(distance_point_line(pos, point0, point1))


def opencl_version():
    platforms = cl.get_platforms()
    logging.debug(platforms[0].get_info(cl.platform_info.VERSION))


def int8():
    a = cl.cltypes.int8.type(bytes([0, 1, 2, 3, 4, 5, 6, 7]))

    logging.debug(a)


def barycentric():
    p = np.array((23, -83))

    p0 = np.array((27, -83))
    p1 = np.array((0, -84))
    p2 = np.array((0, -87))
    p3 = np.array((22, -83))

    s0 = p0 - p
    s1 = p1 - p
    s2 = p2 - p
    s3 = p3 - p

    a0 = s0[0] * s1[1] - s1[0] * s0[1]
    a1 = s1[0] * s2[1] - s2[0] * s1[1]
    a2 = s2[0] * s3[1] - s3[0] * s2[1]
    a3 = s3[0] * s0[1] - s0[0] * s3[1]
    print((a0, a1, a2, a3))

    d0 = np.dot(s0, s1)
    d1 = np.dot(s1, s2)
    d2 = np.dot(s2, s3)
    d3 = np.dot(s3, s0)
    print((d0, d1, d2, d3))

    r0 = np.linalg.norm(s0)
    r1 = np.linalg.norm(s1)
    r2 = np.linalg.norm(s2)
    r3 = np.linalg.norm(s3)
    print((r0, r1, r2, r3))

    if r0 == 0:
        return (1, 0, 0, 0)
    if r1 == 0:
        return (0, 1, 0, 0)
    if r2 == 0:
        return (0, 0, 1, 0)
    if r3 == 0:
        return (0, 0, 0, 1)

    if a0 == 0:
        return (r1 / (r0 + r1), r0 / (r0 + r1), 0, 0)
    if a1 == 0:
        return (0, r2 / (r1 + r2), r1 / (r1 + r2), 0)
    if a2 == 0:
        return (0, 0, r3 / (r2 + r3), r2 / (r2 + r3))
    if a3 == 0:
        return (r3 / (r0 + r3), 0, 0, r0 / (r0 + r3))

    t0 = (r0 * r1 - d0) / a0
    t1 = (r1 * r2 - d1) / a1
    t2 = (r2 * r3 - d2) / a2
    t3 = (r3 * r0 - d3) / a3
    print((t0, t1, t2, t3))

    w0 = (t3 + t0) / r0
    w1 = (t0 + t1) / r1
    w2 = (t1 + t2) / r2
    w3 = (t2 + t3) / r3
    print((w0, w1, w2, w3))

    weight_sum = w0 + w1 + w2 + w3

    weights = np.array((w0, w1, w2, w3)) / weight_sum
    print(weights)


def overlap(bounds, bins):
    return (
        bounds[0] <= bins[2]
        and bounds[2] >= bins[0]
        and bounds[1] <= bins[3]
        and bounds[3] >= bins[1]
    )


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    bounds = [27, -122, 122, -27]
    bins = [64, -130, 135, -90]
    print(overlap(bounds, bins))
