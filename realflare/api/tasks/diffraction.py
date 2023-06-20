import sys

import cv2
import numpy as np
from PySide2 import QtCore, QtWidgets

from qt_extensions import theme
from qt_extensions.parameters import FloatParameter
from qt_extensions.viewer import Viewer
from realflare.api.path import File
from realflare.utils.ciexyz import CIEXYZ

# from realflare.utils.illuminantd65 import ILLUMINANTD65

m = 1.0
cm = 1e-2
um = 1e-6
mm = 1e-3
nm = 1e-9
W = 1

LAMBDA_MIN = 390
LAMBDA_MAX = 790


def load_file(
    file: File,
    resolution: QtCore.QSize,
    threshold: float = 1,
) -> np.ndarray:
    file_path = str(file)

    # load array
    array = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE | cv2.IMREAD_ANYDEPTH)

    # resize array
    array = cv2.resize(array, (resolution.width(), resolution.height()))

    # convert to float32
    if array.dtype == np.uint8:
        array = np.divide(array, 255)
    array = np.float32(array)

    # apply threshold
    if threshold != 1:
        threshold, array = cv2.threshold(array, threshold, 1, cv2.THRESH_BINARY)

    # return image
    return array


def angular_spectrum_method(fft, distance, wavelength, fxx, fyy):
    argument = (2 * np.pi) ** 2 * ((1.0 / wavelength) ** 2 - fxx**2 - fyy**2)

    # Calculate the propagating and the evanescent (complex) modes
    tmp = np.sqrt(np.abs(argument))
    kz = np.where(argument >= 0, tmp, 1j * tmp)

    # propagate the angular spectrum a distance
    spectrum = fft * np.exp(1j * kz * distance)
    spectrum = np.fft.ifft2(np.fft.ifftshift(spectrum))

    return spectrum


class PolychromaticField:
    def __init__(
        self,
        spectrum_size=400,
        spectrum_divisions=10,
    ):
        self.step = spectrum_size / spectrum_divisions
        if not self.step.is_integer():
            raise ValueError("spectrum_size/spectrum_divisions must be an integer")

        self.spectrum_divisions = spectrum_divisions
        step = (LAMBDA_MAX - LAMBDA_MIN) / self.spectrum_divisions
        self.wavelengths = np.arange(LAMBDA_MIN, LAMBDA_MAX, step)

        aperture = load_file(
            File(r'C:\Users\Beat\.realflare\resources\aperture\hexagon.png'),
            QtCore.QSize(1024, 1024),
        )

        extent = 10 * mm
        self.height, self.width = aperture.shape[:2]

        # compute angular spectrum
        self.fft = np.fft.fftshift(np.fft.fft2(aperture))

        dx = extent / self.width
        dy = extent / self.height
        fx = np.fft.fftshift(np.fft.fftfreq(self.width, d=dx))
        fy = np.fft.fftshift(np.fft.fftfreq(self.height, d=dy))
        self.fxx, self.fyy = np.meshgrid(fx, fy)

    def get_colors(self, distance):
        output = np.zeros((self.height, self.width, 3))

        for i in range(self.spectrum_divisions):
            wavelength = self.wavelengths[i] * nm
            spectrum = angular_spectrum_method(
                self.fft, distance, wavelength, self.fxx, self.fyy
            )

            # intensity = np.real(spectrum * np.conjugate(spectrum))
            intensity = spectrum.real**2 + spectrum.imag**2

            xyz = np.array(CIEXYZ[i * int(self.step)][1:])
            output += np.dstack((intensity, intensity, intensity)) * xyz

        return output


class Widget(Viewer):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        # illuminant = [x for w, x in ILLUMINANTD65 if LAMBDA_MIN <= w < LAMBDA_MAX]
        # array = np.array(illuminant, np.float32)

        self.field = PolychromaticField()

        parm = FloatParameter('distance')
        self.layout().addWidget(parm)
        parm.value_changed.connect(self.change)
        parm.value = 1

    def change(self, value):
        rgb = self.field.get_colors(value)
        self.set_array(rgb)


def main():
    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(theme.monokai)

    viewer = Widget()
    viewer.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
