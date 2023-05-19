from importlib.resources import files
import os
import typing

import numpy as np
import pyopencl as cl
from PySide2 import QtCore


CL_PATH = os.path.abspath(str(files('realflare.api.tasks').joinpath('cl')))

LAMBDA_MIN = 390
LAMBDA_MAX = 730
LAMBDA_MID = (LAMBDA_MIN + LAMBDA_MAX) / 2

intersection_dtype = np.dtype(
    [
        ('pos', cl.cltypes.float3),
        ('normal', cl.cltypes.float3),
        ('incident', cl.cltypes.float),
        ('hit', cl.cltypes.int),
    ]
)

lens_element_dtype = np.dtype(
    [
        ('radius', cl.cltypes.float),
        ('distance', cl.cltypes.float),
        ('ior', cl.cltypes.float),
        ('height', cl.cltypes.float),
        ('center', cl.cltypes.float),
        ('is_apt', cl.cltypes.int),
        ('coating', cl.cltypes.float2),
        ('coefficients', cl.cltypes.float8),
    ]
)

# rrel: the biggest relative distance away from the optical axis relative to
# the lens (larger than 1 means the ray left the system)
# pos_apt: the xy position at which the ray moved through the aperture
ray_dtype = np.dtype(
    [
        ('pos', cl.cltypes.float3),
        ('dir', cl.cltypes.float3),
        ('pos_apt', cl.cltypes.float2),
        ('rrel', cl.cltypes.float),
        ('reflectance', cl.cltypes.float),
    ]
)

vertex_dtype = np.dtype(
    [
        ('pos', cl.cltypes.float2),
        ('uv', cl.cltypes.float2),
        ('rrel', cl.cltypes.float),
        ('reflectance', cl.cltypes.float),
        ('intensity', cl.cltypes.float),
    ]
)


class MemoryObject:
    # this objects helps to transfer data between host and devices
    # it also stores the args used to generate the data which are used to
    # make the object hashable

    def __init__(
        self,
        context: cl.Context,
        array: np.ndarray | None = None,
        args: typing.Any | None = None,
    ):
        self._args = args
        self._array = array
        self._hash = None

        self.context = context
        self.shape = array.shape if array is not None else []

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(self.args)
        return self._hash

    @property
    def array(self) -> np.ndarray:
        return self._array

    @property
    def args(self) -> typing.Any:
        return self._args

    @args.setter
    def args(self, value: typing.Any) -> None:
        self._hash = None
        self._args = value


class Image(MemoryObject):
    def __init__(
        self,
        context: cl.Context,
        array: np.ndarray | None = None,
        image: cl.Image | None = None,
        args: typing.Any | None = None,
    ):
        if array is None and image is None:
            raise ValueError('array and image cannot both be None')
        super().__init__(context, array, args)
        self._image = image

    @property
    def array(self) -> np.ndarray:
        if self._array is None:
            width, height = self._image.shape
            channels = self._image.format.channel_count

            shape = (height, width) if channels == 1 else (height, width, channels)

            self._array = np.ascontiguousarray(np.zeros(shape, np.float32))
            with cl.CommandQueue(self.context) as queue:
                cl.enqueue_copy(
                    queue,
                    self._array,
                    self._image,
                    origin=(0, 0),
                    region=(width, height),
                )
        return self._array

    @property
    def image(self) -> cl.Image:
        if self._image is None:
            if len(self._array.shape) == 3:
                channels = self._array.shape[2]
            elif len(self._array.shape) == 2:
                channels = 1
            else:
                raise ValueError(
                    f'array shape needs to have 2 or 3 dimensions,'
                    f'{len(self._array.shape)} given'
                )
            array = np.ascontiguousarray(self._array)
            self._image = cl.image_from_array(self.context, array, channels)
        return self._image

    def clear_image(self):
        self._image = None


class ImageArray(Image):
    @property
    def image(self):
        if self._image is None:
            if len(self._array.shape) == 4:
                channel_order = cl.channel_order.RGBA
            elif len(self._array.shape) == 3:
                channel_order = cl.channel_order.INTENSITY
            else:
                raise ValueError(
                    f'array shape needs to have 3 or 4 dimensions,'
                    f'{len(self._array.shape)} given'
                )

            image_format = cl.ImageFormat(channel_order, cl.channel_type.FLOAT)
            flags = cl.mem_flags.READ_ONLY
            height, width, count = self._array.shape[:3]
            shape = (width, height, count)
            self._image = cl.Image(
                self.context, flags, image_format, shape=shape, is_array=True
            )

            with cl.CommandQueue(self.context) as queue:
                for i in range(count):
                    array = np.ascontiguousarray(self._array[:, :, i])
                    cl.enqueue_copy(
                        queue,
                        dest=self._image,
                        src=array,
                        origin=(0, 0, i),
                        region=(width, height, 1),
                    )
        return self._image


class Buffer(MemoryObject):
    def __init__(
        self,
        context: cl.Context,
        array: np.ndarray,
        buffer: cl.Buffer | None = None,
        args: typing.Any | None = None,
    ):
        super().__init__(context, array, args)
        self._buffer = buffer

    @property
    def buffer(self) -> cl.Buffer:
        if self._buffer is None:
            flags = cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR
            self._buffer = cl.Buffer(self.context, flags, hostbuf=self._array)
        return self._buffer

    def clear_buffer(self):
        self._buffer = None


def devices() -> dict[str, str]:
    cl_devices = {
        platform.name: {device.name: device.name for device in platform.get_devices()}
        for platform in cl.get_platforms()
    }
    return cl_devices


def command_queue(device: str = '') -> cl.CommandQueue:
    for platform in cl.get_platforms():
        for cl_device in platform.get_devices():
            if device and cl_device.name != device:
                continue
            if cl_device.type != cl.device_type.GPU:
                continue

            context = cl.Context(devices=[cl_device])
            queue = cl.CommandQueue(context)
            return queue
    if device:
        raise ValueError(f'invalid device: {device}')
    else:
        raise ValueError('no supported device found')


class OpenCL:
    def __init__(self, queue: cl.CommandQueue) -> None:
        self.queue = queue
        self.context = queue.context
        self.dtypes = {}
        self.program = None
        self.source = ''
        self.rebuild = bool(os.getenv('REALFLARE_REBUILD'))

    def build(self, *args, **kwargs):
        self.program = cl.Program(self.context, self.source).build(*args, **kwargs)

    def register_dtype(self, name, dtype):
        # register dtypes with device so that memory is allocated correctly
        device = self.queue.device
        dtype, c_decl = cl.tools.match_dtype_to_c_struct(device, name, dtype)
        self.dtypes[name] = dtype
        self.source += c_decl + '\n'
        # logging.debug(f'{name}.size: {dtype.itemsize}')

    def update_image(
        self,
        resolution: QtCore.QSize,
        channel_order: cl.channel_order = cl.channel_order.RGBA,
        flags: cl.mem_flags = cl.mem_flags.WRITE_ONLY,
    ) -> Image:
        w, h = resolution.width(), resolution.height()
        image_format = cl.ImageFormat(channel_order, cl.channel_type.FLOAT)
        image_cl = cl.Image(self.context, flags, image_format, shape=(w, h))
        image = Image(self.context, image=image_cl)
        return image

    @staticmethod
    def read_source_file(file):
        with open(os.path.join(CL_PATH, file), encoding='utf-8') as f:
            return f.read()
