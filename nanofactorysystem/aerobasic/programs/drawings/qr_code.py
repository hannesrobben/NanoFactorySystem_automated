from typing import Iterator, Optional

from enum import Enum

import numpy as np
import qrcode

from nanofactorysystem.aerobasic.programs.drawings import DrawableObject, DrawableAeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings.lines import ZLines, HatchingDirection, XLines, YLines
from nanofactorysystem.devices.coordinate_system import DropDirection, CoordinateSystem, Point2D, Point3D


class QrErrorCorrection(Enum):
    L = 0
    M = 1
    Q = 2
    H = 3


class QRCode(DrawableObject):
    def __init__(
            self,
            center: Point3D,
            text: str,
            *,
            version: Optional[int] = None,
            error_correction: Optional[QrErrorCorrection] = None,
            pixel_pitch: float,  # distance between pillars/ points of qr-code
            base_height: float,  # height of base rectangle
            anchor_height: float,  # ? - height of beginning of pillars?
            pixel_height: float,  # height of pillars
            hatch_size: float,
            slice_size: float,
            horizontal_velocity: float,
            horizontal_acceleration: float,
            vertical_velocity: float,
            vertical_acceleration: float,
    ):
        super().__init__()
        self.center = center
        self.text = str(text)
        assert version is None or (version >= 1 and version <= 40)
        self.version = version
        self.error_correction = error_correction or QrErrorCorrection.M
        self.pixel_pitch = float(pixel_pitch)
        self.base_height = float(base_height)
        self.anchor_height = float(anchor_height)
        self.pixel_height = float(pixel_height)

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.horizontal_velocity = horizontal_velocity
        self.horizontal_acceleration = horizontal_acceleration
        self.vertical_velocity = vertical_velocity
        self.vertical_acceleration = vertical_acceleration

        if self.error_correction == QrErrorCorrection.L:
            corr = qrcode.constants.ERROR_CORRECT_L
        elif self.error_correction == QrErrorCorrection.M:
            corr = qrcode.constants.ERROR_CORRECT_M
        elif self.error_correction == QrErrorCorrection.Q:
            corr = qrcode.constants.ERROR_CORRECT_Q
        elif self.error_correction == QrErrorCorrection.H:
            corr = qrcode.constants.ERROR_CORRECT_H
        else:
            raise ValueError(f"Unknown error correction {self.error_correction}!")
        qr = qrcode.QRCode(version=self.version, error_correction=corr)  #, image_factory=qrcode.image.svg.SvgPathImage)
        qr.add_data(self.text)
        qr.make(fit=self.version is None)
        self.qr_image = qr.make_image(fill_color="black", back_color="white")
        self.data = np.array(qr.modules, dtype=bool)

        self.n_layer = round(self.base_height / self.slice_size) + 1
        self.slice_size_opt = self.base_height / (self.n_layer - 1)

    @property
    def structure_length(self) -> float:
        return self.pixel_pitch * (self.data.shape[1] + 2)

    @property
    def structure_width(self) -> float:
        return self.pixel_pitch * (self.data.shape[0] + 2)

    @property
    def structure_height(self) -> float:
        return self.base_height + self.pixel_height

    @property
    def center_point(self) -> Point2D:
        return self.center

    def get_image(self):
        return self.qr_image

    def layer_to_z(self, layer_id: int) -> float:

        assert layer_id >= 0 and layer_id < self.n_layer
        if layer_id == self.n_layer - 1:
            return self.base_height - self.anchor_height + (self.anchor_height + self.pixel_height) / 2
        return self.slice_size_opt * layer_id

    def pixel_program(self, coordinate_system: CoordinateSystem) -> DrawableAeroBasicProgram:

        """
        Special layer. Draw a vertical line for each True pixel. Note: drawing must take place in the
        same direction for all lines to minimise disturbing effects of exposed resin: in negative z
        direction for a drop facing up, and in positive z direction for a drop facing down, where the
        layers are printed in reverse order as well (see DropDirection).
        """

        program = DrawableAeroBasicProgram(coordinate_system)

        # Note: z is relative to substrate surface
        z_top = self.base_height + self.pixel_height
        z_bottom = self.base_height - self.anchor_height
        if coordinate_system.drop_direction == DropDirection.DOWN:
            lines = [[z_bottom, z_top]]
        else:
            lines = [[z_top, z_bottom]]

        h, w = self.data.shape
        order = 1
        for j in range(h):
            y = self.pixel_pitch * (j - (w - 1) / 2)
            for i in range(w)[::order]:
                x = self.pixel_pitch * (i - (w - 1) / 2)
                if self.data[j, i]:
                    line = ZLines(
                        x=x,
                        y=y,
                        lines=lines,
                        velocity=self.vertical_velocity,
                        acceleration=self.vertical_acceleration)
                    program.add_programm(line.draw_on(coordinate_system))
            order *= -1
        return program

    def layer_program(self, coordinate_system: CoordinateSystem, layer_id: int) -> DrawableAeroBasicProgram:

        assert layer_id >= 0 and layer_id < self.n_layer
        if layer_id == self.n_layer - 1:
            return self.pixel_program(coordinate_system)

        program = DrawableAeroBasicProgram(coordinate_system)
        z = self.layer_to_z(layer_id)
        hatching_direction = [HatchingDirection.X, HatchingDirection.Y][layer_id % 2]

        if hatching_direction == HatchingDirection.X:
            line_program = XLines
        elif hatching_direction == HatchingDirection.Y:
            line_program = YLines
        else:
            raise ValueError(f"HatchingDirection not found: {hatching_direction}")

        size = self.structure_length
        n_hatch = round(size / self.hatch_size) + 1
        hatch_size_opt = size / (n_hatch - 1)
        order = 1
        for i in range(n_hatch):
            line_position = hatch_size_opt * (i - n_hatch / 2 + 0.5)
            line_start = size / 2
            lines = [[-line_start, line_start][::order]]
            line = line_program(
                line_position,
                z=z,
                lines=lines,
                velocity=self.horizontal_velocity,
                acceleration=self.horizontal_acceleration)
            program.add_programm(line.draw_on(coordinate_system))
            order *= -1
        return program

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)
        for layer_id in range(self.n_layer):
            yield self.layer_program(coordinate_system, layer_id)
        return program


if __name__ == '__main__':
    qr = QRCode(Point2D(0, 0), "Hello world",
                version=None,
                error_correction=QrErrorCorrection.Q,
                pixel_pitch=2,
                base_height=5.0,
                anchor_height=2.0,
                pixel_height=1.0,
                slice_size=0.1,
                hatch_size=0.1,
                horizontal_velocity=5000,
                horizontal_acceleration=10000,
                vertical_velocity=300,
                vertical_acceleration=10000
                )
    img=qr.get_image()
    import matplotlib.pyplot as plt
    plt.imshow(img)
    plt.show()
    img.save("test_qr.png")
    # print(qr.draw_on(CoordinateSystem()))
