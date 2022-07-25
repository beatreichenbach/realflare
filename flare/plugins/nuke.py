import numpy as np
import nuke


def get_nuke_buffer():
    node = nuke.toNode('Flare')

    width = node.width()
    height = node.height()

    buffer = np.empty([width, height])
    for w in range(0, width):
        for h in range(0, height):
            h_inverted = height - 1 - h
            buffer[h_inverted, w] = node.sample('red', w, h)

    buffer = buffer.astype(np.float32)

    return buffer
