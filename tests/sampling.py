import logging
import bisect

import numpy as np
import matplotlib.pyplot as plt


def lanczos(x, a=2):
    if -a < x and x < a:
        return np.sinc(x) * np.sinc(x / a)
    else:
        return 0


def box(x, a=2):
    return 1


def triangle(x, a=2):
    return 1 - (x / a) if x < a else 0


def gaussian(x, a=2):
    x *= 2 / a
    return np.exp(-2 * x**2)


def get_filter(size):
    center = (size / 2) - 1
    halfsize = size / 2
    scale = 1
    samples = np.zeros((size, size), np.float32)
    for y in range(samples.shape[0]):
        for x in range(samples.shape[1]):
            distance = np.linalg.norm([y - center, x - center]) / halfsize / scale
            samples[y, x] = gaussian(distance)
            # samples[y, x] = distance
    return samples


def get_uniform(size):
    rand_samples = np.random.uniform(0, 1, size=(2, size))
    samples = np.zeros((size, size), np.float32)
    sample_count = 64
    for i in range(sample_count):
        xi0 = int(rand_samples[0, i] * size)
        xi1 = int(rand_samples[1, i] * size)
        samples[xi1, xi0] = 1
    return samples


def get_filter_samples(buffer_shape, width=3, sample_count=16):
    resolution = 512
    cdf = cdf_evaluate(resolution, width, lanczos)
    cdf_inv = cdf_invert(resolution, width, cdf)
    # plt.plot(range(len(cdf) - 1), cdf[:-1], 'r', range(len(cdf_inv)), cdf_inv, 'b')
    # plt.show()

    samples = np.zeros((*buffer_shape, sample_count, 2), np.float32)

    for y in range(buffer_shape[0]):
        for x in range(buffer_shape[1]):
            rng = np.random.default_rng(y * buffer_shape[1] + x)
            rand_samples = rng.uniform([-1, -1], [1, 1], size=(sample_count, 2))
            for i in range(sample_count):
                pos = rand_samples[i]
                distance = np.linalg.norm(pos)
                direction = pos / distance

                index = int(distance * (resolution - 1))
                if index >= resolution:
                    continue
                samples[y, x, i] = direction * cdf_inv[index] * width
    return samples


# this is essentially our p(u), it's |f(u)|/F with F being the integral (sum of all f(u))
# cdf(x): probability of lanczos(x) < x
# for example: cdf(2) = 1 because that contains all possible outcomes
# cdf(x) is the how likely will it be that f(x) will return value below x
def cdf_evaluate(resolution, width, functor):
    cdf = np.zeros(resolution + 1, np.float32)

    for i in range(resolution):
        x = width * i / (resolution - 1)
        y = functor(x, width)
        cdf[i + 1] = cdf[i] + abs(y)

    for i in range(resolution + 1):
        cdf[i] /= cdf[resolution]
    return cdf


# cdf_inv(p) what value of x would make cdf(x) return value of p
# for example, what distance would x have to be at for p to this likely.
# basically we're sampling a random value but most likely we'll get something back
# where lanczos(x) will most likely to give high values.
def cdf_invert(resolution, width, cdf):
    inv_cdf = np.zeros((resolution), np.float32)
    inv_resolution = 1 / resolution
    for i in range(resolution):
        x = i / (resolution - 1)
        index = bisect.bisect_right(cdf, x)
        if index < resolution - 1:
            t = (x - cdf[index]) / (cdf[index + 1] - cdf[index])
        else:
            t = 0
            index = resolution
        inv_cdf[i] = (index + t) * inv_resolution
    return inv_cdf


def main():
    logging.getLogger().setLevel(logging.DEBUG)

    resolution = 512
    width = 1
    sample_count = 512

    # output = get_filter(resolution)
    # output = get_uniform(resolution)
    output = get_filter_samples(
        buffer_shape=(16, 16), width=width, sample_count=sample_count
    )
    plt.plot(output[0, 0, :, 0], output[0, 0, :, 1], 'r.')
    plt.gca().set_aspect('equal', adjustable='box')
    plt.xlim([-width, width])
    plt.ylim([-width, width])
    plt.show()

    # buffer = np.dstack((output, output, output))
    # app = QtWidgets.QApplication(sys.argv)
    # viewer = Viewer()
    # viewer.update_image(buffer)
    # viewer.show()
    # sys.exit(app.exec_())


if __name__ == '__main__':
    main()
