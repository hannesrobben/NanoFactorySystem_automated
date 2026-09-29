##########################################################################
# Copyright (c) 2022-2024 Reinhard Caspary                               #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
import json
import logging
import os.path
import time
import uuid
from logging import Logger
from pathlib import Path
from typing import Iterator, Optional, Literal
from enum import Enum

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse, Rectangle
from scidatacontainer import Container

from nanofactorysystem import System, ImageContainer, Plane, mkdir, getLogger
from nanofactorysystem.aerobasic import SingleAxis, AxisStatusDataItem
from nanofactorysystem.aerobasic.ascii import AerotechError
from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings import DrawableObject, DrawableAeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings.lines import Corner
from nanofactorysystem.aerobasic.programs.drawings.qr_code import QRCode, QrErrorCorrection
from nanofactorysystem.aerobasic.programs.setups import DefaultSetup, SetupIFOV
from nanofactorysystem.backends import BackendLike
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, PlaneFit, DropDirection, Unit, \
    Point2D, Point3D, Coordinate, ZFunction
from nanofactorysystem.devices.power_calibration import PowerCalibration, power_calibration
from nanofactorysystem.dhm.optimage import optImageMedian
from nanofactorysystem.utils.visualization import read_file, plot_movements


class CornerPosition(Enum):
    TL = 0
    TR = 1
    BR = 2
    BL = 3


# test for merge

class StructureType(Enum):
    DUMMY = 0
    NORMAL = 1
    CORNER = 2
    QRCODE = 3
    STITCHING = 4
    IFOV = 5
    REPEAT = 6


class Experiment(object):
    def __init__(self,
                 path: Path,
                 user: str,
                 objective: str,
                 logger: Logger,
                 sys_args: dict,
                 default_power: float,
                 low_speed_um: float,
                 high_speed_um: float,
                 resin_corner_tr: Point2D,
                 resin_corner_bl: Point2D,
                 structure_size: float,
                 margin: float,
                 padding: float,
                 absolute_grid_center: Point2D,
                 grid: tuple[int, int],
                 n_mid_points: int,
                 drop_direction: DropDirection,
                 corner_z: float,
                 corner_width: float,
                 corner_length: float,
                 corner_height: float,
                 corner_hatch: float,
                 corner_slice: float,
                 fov_dim: tuple[float, float],
                 *,
                 skip_corner: bool = False,
                 plane_fit_mode: int = 0,
                 setup: Literal["IFOV_off", "IFOV_on"] = "IFOV_off",
                 substrate_information: dict=None,
                 backend: BackendLike = None):
        """ Experiment on one substrate.

        Only the new parameter is documented here; see the class attributes
        for the others.

        Parameters
        ----------
        backend : {"real", "dummy"}, Backend or None
            Hardware backend passed to :class:`System`. None or ``"real"``
            (default) uses the lab hardware, ``"dummy"`` or a
            ``DummyBackend`` object simulated devices.
        """

        self.path = path
        self.user = str(user)
        self.objective = str(objective)
        self.log = logger
        self.sys_args = sys_args
        self.default_power = float(default_power)
        self.low_speed_um = float(low_speed_um)
        self.high_speed_um = float(high_speed_um)

        self.resin_corner_tr = np.array(resin_corner_tr.as_tuple(), dtype=float)
        self.resin_corner_bl = np.array(resin_corner_bl.as_tuple(), dtype=float)
        self.structure_size = float(structure_size)
        self.margin = float(margin)
        self.padding = float(padding)
        self.absolute_grid_center = np.array(absolute_grid_center.as_tuple(), dtype=float)
        self.fov_dimensions = fov_dim

        self.grid = np.array(grid, dtype=int)
        assert self.grid.shape == (2,)
        assert self.grid[0] > 0 and self.grid[1] > 0

        self.n_mid_points = int(n_mid_points)
        assert self.n_mid_points >= 0

        self.drop_direction = drop_direction
        self.plane_fit_mode = plane_fit_mode

        # Corner dimensions
        self.corner_z = float(corner_z)
        self.corner_width = float(corner_width)
        self.corner_length = float(corner_length)
        self.corner_height = float(corner_height)
        self.corner_hatch = float(corner_hatch)
        self.corner_slice = float(corner_slice)

        # UUID for this experiment
        self.qr_text = str(uuid.uuid4())
        self.log.info(f"Experiment {self.qr_text}")

        # No plane fitting data yet
        self.plane_fit_function = None
        self.coordinate_system_grid_to_absolute = None

        # Init system object
        self.log.info("Initialize system object...")
        self.system = System(user, objective, logger, backend=backend, **sys_args)

        # Set default laser power
        self.system.controller.power(default_power)

        # AeroTech A3200 API
        self.a3200 = self.system.a3200_new
        if setup == "IFOV_off":
            self.a3200.api(DefaultSetup())
        elif setup == "IFOV_on":
            self.a3200.api(SetupIFOV(objective=self.objective))
            # raise NotImplementedError(
            #     "The IFOV setup has to be adjusted again")
        else:
            raise NotImplementedError("Please use an existing setup!")

        # Acceleration rates of stages and galvanometer
        self.accel_x_mm = float(
            self.a3200.api.AXISSTATUS(SingleAxis.X, AxisStatusDataItem.AccelerationRate).replace(",", "."))
        # note 07.05.2026 - change acceleration to x accel in ifov because of an error
        self.accel_a_mm = float(
            self.a3200.api.AXISSTATUS(SingleAxis.A, AxisStatusDataItem.AccelerationRate).replace(",", ".")) if setup == "IFOV_off" else self.accel_x_mm/2
        self.accel_z_mm = float(
            self.a3200.api.AXISSTATUS(SingleAxis.Z, AxisStatusDataItem.AccelerationRate).replace(",", "."))
        self.accel_x_um = self.accel_x_mm / Unit.um.value
        self.accel_a_um = self.accel_a_mm / Unit.um.value
        self.accel_z_um = self.accel_z_mm / Unit.um.value

        # Initialize structures list with corners
        self.structures = []
        if not skip_corner:  # Skipping printing process of Corner+QR-Code
            self.add_corner_structures()
            if self.qr_text:
                self.add_qrcode_structure()

        # No programs yet
        self.structure_programs = None
        self.structure_configs = None
        # create dictionary for restart purpose
        self._create_experiment_dictionary(skip_corner=skip_corner, setup=setup)
        calibration_file = self.system.controller.attenuator.data
        self._save_experimental_data(calibration_file=calibration_file, substrate=substrate_information)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.system.close()
        return

    def _save_experimental_data(self, calibration_file, substrate):
        # path has to be changed accordingly
        #   - substrate information is not only for one experiment!
        #   - calibration file is needed in each experiment and changes only during setup/ changing of system
        #   - experiment dictionary is only for 1 experiment

        self._save_exp_dict(path=self.path)
        # Calibration file first column are attenuator values, second column is laser power in mW.
        self._save_calibration(path=self.path, file=calibration_file)
        path = self.path.parent
        self._save_substrate_information(path=path, file = substrate)

    def _save_calibration(self, path, file):
        file_path = os.path.join(path, "calibration_file.npy")
        np.save(file_path, file)

    def _save_exp_dict(self, path):
        if self.exp_dict is None:
            self._create_experiment_dictionary(skip_corner=None, setup=None)
            raise Warning("No experiment dictionary. Created one with incomplete information!")
        file_path = path / "experiment_dictionary.json"
        file_path.write_text(json.dumps(self.exp_dict, indent=4))

    def _save_substrate_information(self, path, file):
        if file is None:
            return
        assert isinstance(file, dict), "Substrate information must be a dictionary!"
        file_path = Path(os.path.join(path, "substrate_information.json"))

        # If the file already exists (several experiments on one substrate), merge the new
        # information into it; new values replace old values with the same key.
        if file_path.exists():
            data = json.loads(file_path.read_text())
            data.update(file)
        else:
            data = file

        file_path.write_text(json.dumps(data, indent=4))

    def _log_file(self) -> Optional[str]:
        """ Return the file of the most recently added file handler of the logger, or None. """

        files = [h.baseFilename for h in self.log.handlers if isinstance(h, logging.FileHandler)]
        return files[-1] if files else None

    def _create_experiment_dictionary(self, *, skip_corner, setup):
        self.exp_dict = {"path": str(self.path),
                         "user": self.user,
                         "objective": self.objective,
                         "logger": self._log_file(),
                         "sys_args": self.sys_args,
                         "default_power": self.default_power,
                         "low_speed_um": self.low_speed_um,
                         "high_speed_um": self.high_speed_um,
                         "resin_corner_tr": str(self.resin_corner_tr),
                         "resin_corner_bl": str(self.resin_corner_bl),
                         "structure_size": self.structure_size,
                         "margin": self.margin,
                         "padding": self.padding,
                         "absolute_grid_center": str(self.absolute_grid_center),
                         "grid_size": str(self.grid),
                         "n_mid_points": self.n_mid_points,
                         "drop_direction": self.drop_direction.value,
                         "drop_direction_information": self.drop_direction.name,
                         "corner_z": self.corner_z,
                         "corner_width": self.corner_width,
                         "corner_length": self.corner_length,
                         "corner_height": self.corner_height,
                         "corner_hatch": self.corner_hatch,
                         "corner_slice": self.corner_slice,
                         "fov_dim": str(self.fov_dimensions),
                         "skip_corner": skip_corner,
                         "plane_fit_mode": self.plane_fit_mode,
                         "setup": setup
                         }

    @staticmethod
    def parameters_from_dictionary(path) -> dict:
        """ Rebuild the constructor arguments of a stored experiment.

        Reads ``experiment_dictionary.json``, which every experiment writes into
        its folder, e.g. to restart an aborted print with
        ``Experiment(**Experiment.parameters_from_dictionary(path))``.

        Parameters
        ----------
        path : str or Path
            Experiment folder.

        Returns
        -------
        dict
            Keyword arguments for :class:`Experiment`. ``logger`` writes to the
            stored log file (or ``console.log`` in the folder).
        """

        path = Path(path)
        data = json.loads((path / "experiment_dictionary.json").read_text())

        def vector(text) -> list[float]:
            # Stored with str(): "[5720. 27190.]" or "(500, 500)"
            return [float(v) for v in str(text).strip("[]() ").replace(",", " ").split()]

        logfile = data.get("logger") or path / "console.log"
        return {
            "path": Path(data["path"]),
            "user": data["user"],
            "objective": data["objective"],
            "logger": getLogger(logfile=logfile),
            "sys_args": data["sys_args"],
            "default_power": data["default_power"],
            "low_speed_um": data["low_speed_um"],
            "high_speed_um": data["high_speed_um"],
            "resin_corner_tr": Point2D(*vector(data["resin_corner_tr"])),
            "resin_corner_bl": Point2D(*vector(data["resin_corner_bl"])),
            "structure_size": data["structure_size"],
            "margin": data["margin"],
            "padding": data["padding"],
            "absolute_grid_center": Point2D(*vector(data["absolute_grid_center"])),
            "grid": tuple(int(v) for v in vector(data["grid_size"])),
            "n_mid_points": data["n_mid_points"],
            "drop_direction": DropDirection(data["drop_direction"]),
            "corner_z": data["corner_z"],
            "corner_width": data["corner_width"],
            "corner_length": data["corner_length"],
            "corner_height": data["corner_height"],
            "corner_hatch": data["corner_hatch"],
            "corner_slice": data["corner_slice"],
            "fov_dim": tuple(vector(data["fov_dim"])),
            "skip_corner": bool(data["skip_corner"]),
            "plane_fit_mode": data["plane_fit_mode"],
            "setup": data["setup"] or "IFOV_off",
        }

    def iter_experiment_locations(self) -> Iterator[tuple[float, float]]:
        """ Return experiment locations in um """
        for i in range(self.grid[0]):
            for j in range(self.grid[1]):
                rect_x = self.rectangle_tl[0] + self.margin + j * (self.structure_size + self.padding)
                rect_y = self.rectangle_tl[1] + self.margin + i * (self.structure_size + self.padding)
                yield rect_x + self.structure_size / 2, rect_y + self.structure_size / 2

    def structure_location(self, index) -> Point2D:
        i, j = divmod(index, self.grid[1])
        rect_x = self.rectangle_tl[0] + self.margin + j * (self.structure_size + self.padding)
        rect_y = self.rectangle_tl[1] + self.margin + i * (self.structure_size + self.padding)
        return Point2D(rect_x + self.structure_size / 2, rect_y + self.structure_size / 2)

    def corner_location(self, position: CornerPosition) -> Point2D:
        if position == CornerPosition.TL:
            point = self.rectangle_tl
        elif position == CornerPosition.TR:
            point = self.rectangle_tr
        elif position == CornerPosition.BL:
            point = self.rectangle_bl
        elif position == CornerPosition.BR:
            point = self.rectangle_br
        else:
            raise ValueError(f'Unknown position string "{position}"')
        return Point2D(*point)

    def qrcode_location(self) -> Point2D:
        point = (self.rectangle_tl + self.rectangle_tr) / 2
        return Point2D(*point)

    @property
    def center_point(self) -> np.ndarray:
        return (self.resin_corner_bl + self.resin_corner_tr) / 2

    @property
    def resin_size(self) -> np.ndarray:
        return self.resin_corner_tr - self.resin_corner_bl

    @property
    def grid_center(self) -> np.ndarray:
        return np.asarray([
            self.absolute_grid_center[0] - self.center_point[0],
            self.absolute_grid_center[1] - self.center_point[1]
        ]
        )

    @property
    def grid_width(self) -> float:
        return self.grid[1] * (self.structure_size + self.padding) - self.padding + 2 * self.margin

    @property
    def grid_height(self) -> float:
        return self.grid[0] * (self.structure_size + self.padding) - self.padding + 2 * self.margin

    @property
    def rectangle_tl(self) -> np.ndarray:
        return self.center_point + self.grid_center - [self.grid_width / 2, self.grid_height / 2]

    @property
    def rectangle_br(self) -> np.ndarray:
        return self.center_point + self.grid_center + [self.grid_width / 2, self.grid_height / 2]

    @property
    def rectangle_tr(self) -> np.ndarray:
        return self.center_point + self.grid_center + [self.grid_width / 2, -self.grid_height / 2]

    @property
    def rectangle_bl(self) -> np.ndarray:
        return self.center_point + self.grid_center + [-self.grid_width / 2, self.grid_height / 2]

    def sample_points_for_plane_fitting(self) -> list[tuple[float, float]]:
        n_rows = self.grid[0]  # + 1
        n_cols = self.grid[1]
        points = []
        if self.plane_fit_mode == 0:  # plane fitting points also in between structures
            for i in range(n_rows + 1):
                for j in range(n_cols + 1):
                    x = float(self.rectangle_tl[0]) + self.margin - 0.5 * self.padding + j * (
                            self.structure_size + self.padding)
                    y = float(self.rectangle_tl[1]) + self.margin - 0.5 * self.padding + i * (
                            self.structure_size + self.padding)
                    points.append((x, y))
        elif self.plane_fit_mode == 1:
            x0 = float(self.rectangle_tl[0]) + self.margin - 0.5 * self.padding
            x1 = float(self.rectangle_tl[0]) + self.margin - 0.5 * self.padding + n_cols * (
                    self.structure_size + self.padding)
            y0 = float(self.rectangle_tl[1]) + self.margin - 0.5 * self.padding
            y1 = float(self.rectangle_tl[1]) + self.margin - 0.5 * self.padding + n_rows * (
                    self.structure_size + self.padding)
            points.append((x0, y0))
            points.append((x0, y1))
            points.append((x1, y0))
            points.append((x1, y1))
        else:
            raise NotImplementedError(f"Plane fit mode {self.plane_fit_mode} is not implemented!")
        return points

    # def sample_points_for_plane_fitting_old(self) -> list[tuple[float, float]]:
    #     tl = self.rectangle_tl + self.margin / 2
    #     br = self.rectangle_br - self.margin / 2
    #     points = set()
    #     for x in np.linspace(tl[0], br[0], self.n_mid_points + 2):
    #         points.add((x, tl[1]))
    #         points.add((x, br[1]))
    #
    #     for y in np.linspace(tl[1], br[1], self.n_mid_points + 2):
    #         points.add((tl[0], y))
    #         points.add((br[0], y))
    #
    #     return list(points)

    def plot_experiment(self, show: bool = True):
        # Visualize experiment
        fig, ax = plt.subplots()
        assert isinstance(ax, plt.Axes)

        # Draw the ellipse
        ellipse = Ellipse(self.center_point, self.resin_size[0], self.resin_size[1], edgecolor='lightblue',
                          facecolor='none', lw=2, label="Resin Drop")
        ax.add_patch(ellipse)

        # Draw the outer rectangle
        outer_rectangle = Rectangle(self.rectangle_tl, self.grid_width, self.grid_height, edgecolor='blue',
                                    facecolor='none', lw=2, label="Experiment Field")
        ax.add_patch(outer_rectangle)

        # Draw the grid of rectangles
        center_xs = []
        center_ys = []
        for i, (x, y) in enumerate(self.iter_experiment_locations()):
            x_tl = x - self.structure_size / 2
            y_tl = y - self.structure_size / 2
            rect = Rectangle(
                (x_tl, y_tl),
                width=self.structure_size,
                height=self.structure_size,
                edgecolor='green',
                facecolor='none',
                lw=1
            )
            ax.text(x_tl, y_tl, f"{i}", color="green")
            ax.add_patch(rect)
            center_xs.append(x)
            center_ys.append(y)

        ax.scatter(center_xs, center_ys, s=3, marker="x", color="green", label="Structures")

        plane_fit_points = self.sample_points_for_plane_fitting()
        ax.scatter(*zip(*plane_fit_points), s=3, marker=".", color="red", label="Plane Fitting Probe Points")

        # Set limits and aspect ratio
        ax.set_xlim(self.resin_corner_bl[0], self.resin_corner_tr[0])
        ax.set_ylim(self.resin_corner_bl[1], self.resin_corner_tr[1])
        ax.set_xlabel("X [um]")
        ax.set_ylabel("Y [um]")
        ax.set_aspect('equal')
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.path / "experiment.png")
        if show:
            plt.show()

    def plane_fit(self, force: bool = False, *, plane: Optional[ZFunction] = None):
        """ Determine the substrate surface and the global coordinate system.

        Parameters
        ----------
        force : bool
            Measure again even if stored plane detection results exist.
        plane : ZFunction, optional
            Known substrate surface (z in µm as function of x, y in µm). If
            given, no measurement is done and this plane is used directly,
            e.g. for dry runs with the dummy backend.
        """
        if plane is not None:
            self.plane_fit_function = plane
            self.log.info(f"Using given substrate plane {plane!r} (no plane detection)")
            self._init_coordinate_system(plane)
            return

        path = self.path / "planefit"
        mkdir(path, clean=False)
        plane_dc_path = path / "plane.zdc"

        if not force and plane_dc_path.exists():
            self.log.info("Load plane detection results...")
            dc = Container(file=str(plane_dc_path))

        else:
            # Plane needs micrometer coordinates
            if self.system.objective['magnification'] == 63.0:
                zlo = self.system.z0
                zup = None
            else:
                zlo = zup = self.system.z0

            plane = Plane(zlo, zup, self.system, self.log, **self.sys_args)

            self.log.info("Store background image...")
            plane.layer.focus.imgBack.write(str(path / "back.zdc"))

            self.log.info("Run plane detection...")
            for x, y in self.sample_points_for_plane_fitting():
                plane.run(x, y, path=path)

            self.log.info("Store plane detection results...")
            dc = plane.container()
            dc.write(str(plane_dc_path))

        if self.drop_direction == DropDirection.DOWN:
            plane_points = dc["meas/result.json"]["low"]["points"]
        else:
            plane_points = dc["meas/result.json"]["high"]["points"]
        plane_fit_function = PlaneFit.from_points(np.asarray(plane_points))  # in um
        self.plane_fit_function = plane_fit_function
        self.log.info(str(plane_fit_function))
        self._init_coordinate_system(plane_fit_function)

    def _init_coordinate_system(self, z_function: ZFunction):
        """ Create the global coordinate system from the substrate surface. """

        self.coordinate_system_grid_to_absolute = CoordinateSystem(
            offset_x=self.absolute_grid_center[0],
            offset_y=self.absolute_grid_center[1],
            z_function=z_function,
            drop_direction=self.drop_direction,
            unit=Unit.um
        )

        self.log.info("Done.")

    def opl_scan(self, m0: float = None, force: bool = False) -> float:
        if self.system.dhm is None:
            return 0
        path = self.path / "oplscan"
        mkdir(path, clean=False)

        opl_dc_path = path / "opl.txt"
        if not force and opl_dc_path.exists():
            with open(opl_dc_path, "r") as fp:
                m0 = float(fp.readline())
            self.log.info(f"Retrieved OPL motor pos {m0:.1f} µm")
        else:
            image_center = self.coordinate_system_grid_to_absolute.convert({"X": 0, "Y": 0, "Z": 0})
            self.a3200.api.LINEAR(**image_center, F=2)  # Slower, as we also move in z direction and it is scary

            # Dummy call to avoid low intensity images on motorscan.
            optImageMedian(dhm=self.system.dhm, vmedian=127, logger=self.log)

            m0 = self.system.dhm.motorscan(m0)
            self.log.info(
                f"OPL motor pos at {image_center}: {self.system.dhm.device.MotorPos:.1f} µm (set: {m0:.1f} µm)")
            with open(opl_dc_path, "w") as fp:
                fp.write(str(m0))

        self.system.dhm.device.MotorPos = m0
        return m0

    def add_corner_structures(self):

        # Reference point (Note: reference <> center for corners)
        reference_point = Point3D(0, 0, self.corner_z)

        # Top-right corner
        corner = Corner(
            reference_point,
            length=self.corner_length,
            width=self.corner_width,
            height=self.corner_height,
            slice_size=self.corner_slice,
            hatch_size=self.corner_hatch,
            rotation_degree=90,
            F=self.high_speed_um,
            mark=False)
        self.add_structure(
            structure_type=StructureType.CORNER,
            name="corner_tr",
            structure=corner,
            corner=CornerPosition.TR)

        # Top-left corner (marked)
        corner = Corner(
            reference_point,
            length=self.corner_length,
            width=self.corner_width,
            height=self.corner_height,
            slice_size=self.corner_slice,
            hatch_size=self.corner_hatch,
            rotation_degree=0,
            F=self.high_speed_um,
            mark=True)
        self.add_structure(
            structure_type=StructureType.CORNER,
            name="corner_tl",
            structure=corner,
            corner=CornerPosition.TL)

        # Bottom-left corner
        corner = Corner(
            reference_point,
            length=self.corner_length,
            width=self.corner_width,
            height=self.corner_height,
            slice_size=self.corner_slice,
            hatch_size=self.corner_hatch,
            rotation_degree=270,
            F=self.high_speed_um,
            mark=False)
        self.add_structure(
            structure_type=StructureType.CORNER,
            name="corner_bl",
            structure=corner,
            corner=CornerPosition.BL)

        # Bottom-right corner
        corner = Corner(
            reference_point,
            length=self.corner_length,
            width=self.corner_width,
            height=self.corner_height,
            slice_size=self.corner_slice,
            hatch_size=self.corner_hatch,
            rotation_degree=180,
            F=self.high_speed_um,
            mark=False)
        self.add_structure(
            structure_type=StructureType.CORNER,
            name="corner_br",
            structure=corner,
            corner=CornerPosition.BR)

    def add_qrcode_structure(self):

        # Reference point (center of QR code)
        reference_point = Point3D(0, 0, self.corner_z)
        qrcode = QRCode(
            reference_point,
            text=self.qr_text,
            version=None,
            error_correction=QrErrorCorrection.Q,
            pixel_pitch=4.0,
            base_height=7.0,
            anchor_height=2.0,
            pixel_height=5.0,
            slice_size=self.corner_slice,
            hatch_size=self.corner_hatch,
            horizontal_velocity=self.high_speed_um,
            horizontal_acceleration=self.accel_a_um,
            vertical_velocity=300,
            vertical_acceleration=self.accel_z_um)
        qrcode.get_image().save(os.path.join(self.path, "qr_code_image.png"))
        self.add_structure(
            structure_type=StructureType.QRCODE,
            name="qrcode",
            structure=qrcode)

    def skip_structure(self):
        return self.add_structure(StructureType.DUMMY, "dummy")

    def add_structure(self,
                      structure_type: StructureType,
                      name: str,
                      structure: Optional[DrawableObject] = None,
                      corner: Optional[CornerPosition] = None,
                      axes: str = None,
                      power: float = None):

        # Make sure that each structure has an individual name
        names = [s["name"] for s in self.structures]
        if name in names:
            i = 1
            while f"{name}_({i})" in names:
                i += 1
            name = f"{name}_({i})"

        # Sanity checks for normal structure
        if structure_type == StructureType.DUMMY:
            pass

        # Sanity checks for normal structure
        elif structure_type == StructureType.NORMAL:
            assert structure is not None
            n_structures = sum(
                [s["structure_type"] in (
                    StructureType.NORMAL, StructureType.DUMMY, StructureType.REPEAT, StructureType.STITCHING,
                    StructureType.IFOV) for s in
                 self.structures])
            if n_structures >= self.grid[0] * self.grid[1]:
                raise ValueError(f"Too many structures for structure {name}!")

        # Sanity checks for corner structure
        elif structure_type == StructureType.CORNER:
            assert structure is not None
            assert isinstance(corner, CornerPosition)
            corners = [s["corner"] for s in self.structures if s["structure_type"] == StructureType.CORNER]
            if corner in corners:
                raise ValueError(f"Corner position {corner} added twice for corner {name}!")

        # Sanity checks for QR code
        elif structure_type == StructureType.QRCODE:
            assert structure is not None
            n_qrcodes = sum([s["structure_type"] == StructureType.QRCODE for s in self.structures])
            if n_qrcodes != 0:
                raise ValueError(f"More than one QR code given!")

        elif structure_type == StructureType.STITCHING:
            # process should be like serveral different strucutres printed after another?
            # strategy is then only tile wise
            pass

        elif structure_type == StructureType.IFOV:
            assert structure is not None
            n_structures = sum(
                [s["structure_type"] in (
                    StructureType.NORMAL, StructureType.DUMMY, StructureType.REPEAT, StructureType.STITCHING,
                    StructureType.IFOV) for s in
                 self.structures])
            if n_structures >= self.grid[0] * self.grid[1]:
                raise ValueError(f"Too many structures for structure {name}!")

        elif structure_type == StructureType.REPEAT:
            n_structures = sum(
                [s["structure_type"] in (
                    StructureType.NORMAL, StructureType.DUMMY, StructureType.REPEAT, StructureType.STITCHING,
                    StructureType.IFOV) for s in
                 self.structures])
            assert n_structures >= 1, "At least one structure has to be defined prior to repeat."

            s_2_repeat = (self.structures[-1]).copy
            repition_number = sum(
                s["name"].split("(")[0] in (s_2_repeat["name"].split("(")[0]) for s in self.structures)
            name = f"{s_2_repeat["name"]}({repition_number})"
            structure = s_2_repeat["structure"]
            axes = s_2_repeat["axes"]
            power = s_2_repeat["power"]

        # Unknown structure type
        else:
            raise ValueError(f"Unknown structure type {structure_type}!")

        # Power and axes have default values
        if power is None:
            power = self.default_power
        if axes is None:
            axes = "ABZ"

        # Add structure to list
        self.structures.append({
            "structure_type": structure_type,
            "name": name,
            "structure": structure,
            "axes": axes,
            "power": power,
            "corner": corner,
        })

        # Aware: name may have changed
        return name

    def structure_program(self,
                          x: float,
                          y: float,
                          structure: DrawableObject,
                          name: str,
                          printing_axes: str,
                          power: float,
                          path: Path,
                          n_dhm_img: int = 0,
                          stitching: bool = False):
        plotting_structure = False
        # if not stitching:
        #     plotting_structure = True
        self.log.info(f"Creating layer programs for {name}: {structure}")
        assert isinstance(structure, DrawableObject)

        path = path / name
        mkdir(path, clean=False)
        pgm_path = path / "programs"
        mkdir(pgm_path, clean=False)

        # Make sure that power is not None
        power = float(power)

        # Absolute center coordinates
        offset_x = structure.center_point.X
        offset_y = structure.center_point.Y
        z = self.plane_fit_function(x, y)
        structure_center_absolute_um = {
            "X": x + offset_x,
            "Y": y + offset_y,
            "Z": z,
        }
        structure_center_absolute_mm = {k: v * Unit.um.value for k, v in structure_center_absolute_um.items()}

        # Coordinate systems of stages and galvo scanner
        coordinate_system_stage = CoordinateSystem(
            offset_x=structure_center_absolute_um["X"],
            offset_y=structure_center_absolute_um["Y"],
            z_function=structure_center_absolute_um["Z"],
            drop_direction=self.drop_direction,
            unit=Unit.um
        )
        coordinate_system_galvo = CoordinateSystem(
            offset_x=-offset_x,
            offset_y=-offset_y,
            z_function=structure_center_absolute_um["Z"],
            drop_direction=self.drop_direction,
            unit=Unit.um
        )
        coordinate_system_galvo.axis_mapping = {"X": "A", "Y": "B"}

        # Generate structure and layer programs
        if printing_axes == "ABZ":
            coordinate_system = coordinate_system_galvo
        else:
            coordinate_system = coordinate_system_stage
        structure_pgm = DrawableAeroBasicProgram(coordinate_system)
        layer_pgm_paths = []
        # NOTE What to do with tiles
        x_structure_center = structure_center_absolute_mm["X"]
        y_structure_center = structure_center_absolute_mm["Y"]

        if stitching:
            for _ in structure.iterate_layers(coordinate_system):
                pass

        #     layer_pgm.add_programm(layer)
        #     # ... rest
        #
        #
        # for layer_id, layer in enumerate(structure.iterate_layers(coordinate_system)):
        #     # AeroBasic program for given layer
        #     layer_pgm = AeroBasicProgram()
        #
        #
        #     layer_pgm.LINEAR(X=x_center, Y=y_center)  # move to reference point for galvo scanner

        for layer_id, layer in enumerate(structure.iterate_layers(coordinate_system)):
            layer_pgm = AeroBasicProgram()

            if stitching:  # apparently works!
                x_offset, y_offset = structure.get_tile_center_for_layer(layer_id)
                x_value = x_structure_center + x_offset / 1000
                y_value = y_structure_center + y_offset / 1000
            else:
                x_value = x_structure_center
                y_value = y_structure_center

            layer_pgm.LINEAR(X=x_value, Y=y_value)

            layer_pgm.add_programm(layer)

            # Store layer program file
            layer_pgm_path = pgm_path / f"program_{name}.{layer_id:03d}.txt"
            layer_pgm.write(layer_pgm_path)
            layer_pgm_paths.append(str(layer_pgm_path))

            # Add layer program to structure program
            structure_pgm.add_programm(layer_pgm)

        # Store structure program file
        structure_pgm_path = path / f"program_{name}.txt"
        structure_pgm.write(structure_pgm_path)

        # Structure configuration
        structure_config = {
            "name": name,
            "axes": printing_axes,
            "power": power,
            "center_x": structure_center_absolute_um["X"],
            "center_y": structure_center_absolute_um["Y"],
            "center_z": structure_center_absolute_um["Z"],
            "structure": structure.to_json(),
            "program_file": str(structure_pgm_path),
            "layer_files": layer_pgm_paths,
            "number of dhm images": n_dhm_img,
        }

        if plotting_structure:
            # Plot structure to image file
            self.log.info(f"Plotting {name}")
            movements = read_file(structure_pgm_path)
            plot_movements(movements)
            plt.savefig(path / f"plot_{name}.png")
            plt.close()

        # Done
        return layer_pgm_paths, structure_config

    def build_programs(self):
        # Structures that set the laser power (IFOV) use the calibration of this system's attenuator
        with power_calibration(PowerCalibration(self.system.controller.attenuator.data)):
            self._build_programs()

    def _build_programs(self):

        path = self.path / "structures"
        mkdir(path, clean=False)

        self.structure_programs = []
        self.structure_configs = []
        structure_id = 0
        for structure_dict in self.structures:
            self.log.info(f'Creating program for {structure_dict["name"]}: {structure_dict["structure"]}')

            # Skip dummy structure
            if structure_dict["structure_type"] == StructureType.DUMMY:
                structure_id += 1
                n_dhm_img = 0
                continue

            # Reference point of normal structure
            elif structure_dict["structure_type"] == StructureType.NORMAL:
                x, y = self.structure_location(structure_id).as_tuple()
                n_dhm_img = 10
                structure_id += 1
                stitching = False

            elif structure_dict["structure_type"] == StructureType.STITCHING:
                x, y = self.structure_location(structure_id).as_tuple()
                n_dhm_img = 10
                structure_id += 1
                stitching = True

            elif structure_dict["structure_type"] == StructureType.IFOV:
                x, y = self.structure_location(structure_id).as_tuple()
                n_dhm_img = 10
                structure_id += 1
                stitching = False

            elif structure_dict["structure_type"] == StructureType.REPEAT:
                x, y = self.structure_location(structure_id).as_tuple()
                n_dhm_img = 10
                structure_id += 1
                stitching = False

            # Reference point of corner structure
            elif structure_dict["structure_type"] == StructureType.CORNER:
                corner_pos = structure_dict["corner"]
                x, y = self.corner_location(corner_pos).as_tuple()
                n_dhm_img = 1
                stitching = False
                dhm_stitching = True  # to be done in the future

            # Reference point of qrcode
            elif structure_dict["structure_type"] == StructureType.QRCODE:
                x, y = self.qrcode_location().as_tuple()
                n_dhm_img = 1
                stitching = False

            # Unknown structure type
            else:
                raise ValueError(f"Unknown structure type {structure_dict['structure_type']}!")

            # Store all layer programs and get path list and list of configuration dictionaries
            paths, config = self.structure_program(
                x=x,
                y=y,
                structure=structure_dict["structure"],
                name=structure_dict["name"],
                printing_axes=structure_dict["axes"],
                power=structure_dict["power"],
                path=path,
                n_dhm_img=n_dhm_img,
                stitching=stitching)
            self.structure_programs.append(paths)
            self.structure_configs.append(config)

        # Write JSON file with all configurations
        structure_configs_path = self.path / "structures.json"
        structure_configs_path.write_text(json.dumps(self.structure_configs, indent=4))

    def retrieve_programs(self):
        structure_configs_path = self.path / "structures.json"
        self.structure_configs = json.loads(open(structure_configs_path).read())

    def print_structure(self,
                        pgm_files_list: list[Path],
                        x: float,  # um
                        y: float,  # um
                        name: str,
                        power: float,
                        dhm_image_count: int = 0,
                        restart: bool = False):

        structure_path = self.path / "structures" / name
        camera_path = structure_path / "camera"
        mkdir(camera_path, clean=False)
        dhm_path = structure_path / "dhm"
        mkdir(dhm_path, clean=False)

        self.log.info(f"Printing {name}")
        # program files angucken
        # allgmein power

        # Set laser power
        self.system.controller.power(power)

        # Absolute coordinates of structure center
        structure_center_absolute_mm = {"X": x / 1000, "Y": y / 1000}

        # Images before structure writing
        if not restart:
            self.measure(
                coordinate=structure_center_absolute_mm,
                name=f"{name}_before",
                camera_path=structure_path,
                dhm_path=structure_path,
                dhm_image_count=dhm_image_count)

        # Prepare order of layer writing
        if self.drop_direction == DropDirection.UP:
            order = 1
        elif self.drop_direction == DropDirection.DOWN:
            order = -1
        else:
            raise ValueError(f"Unknown drop direction {self.drop_direction}!")

        # Write all layers of the structure
        layer_id = layer_count = None  # stay None if the structure has no layers
        t1 = time.time()
        for layer_count in range(len(pgm_files_list))[::order]:
            layer_pgm_path = pgm_files_list[layer_count]
            layer_id = int(str(layer_pgm_path).split('.')[-2])
            # Details about the program: if a program exceeds a certain size, consider splitting it
            try:
                task = self.a3200.run_program_as_task(layer_pgm_path, task_id=1)
                task.wait_to_finish()
                task.finish()
                self.measure(
                    coordinate=structure_center_absolute_mm,
                    name=f"{name}.{layer_id}",
                    camera_path=camera_path,
                    dhm_path=dhm_path,
                    dhm_image_count=dhm_image_count)
                self.update_print_progress(name, layer_id=layer_id, layer_count=layer_count, order=order,
                                           drop_direction=self.drop_direction)
            except AerotechError as e:
                self.log.error(f"Program failed for {name}: {e}")
                self._stop_failed_task(task_id=1)
                self.update_print_progress(name, layer_id=layer_id, layer_count=layer_count, order=order, error=e,
                                           drop_direction=self.drop_direction, error_log=True)
        t2 = time.time()
        self.log.info(f"Making {name} took {t2 - t1:.2f}s")

        # Images after structure writing
        self.measure(
            coordinate=structure_center_absolute_mm,
            name=f"{name}_after",
            camera_path=structure_path,
            dhm_path=structure_path,
            dhm_image_count=dhm_image_count + 10)
        self.update_print_progress(name, layer_id=layer_id, layer_count=layer_count, order=order,
                                   drop_direction=self.drop_direction, finished=True)

    def _stop_failed_task(self, task_id: int) -> None:
        """ Stop a task after a failed program, so that the next program can be loaded. """

        try:
            self.a3200.api.PROGRAM_STOP(task_id)
        except AerotechError as error:
            self.log.error(f"Could not stop task {task_id}: {error}")

    def print_experiment(self):
        if self.structure_configs is None:
            raise ValueError("No programs!")

        for structure_config in self.structure_configs:
            self.print_structure(
                [Path(p) for p in structure_config["layer_files"]],
                x=structure_config["center_x"],
                y=structure_config["center_y"],
                name=structure_config["name"],
                power=structure_config["power"],
                dhm_image_count=structure_config["number of dhm images"]
            )

    def update_print_progress(self,
                              name: str,
                              layer_id: int,
                              layer_count: int = None,
                              order: int = None,
                              error=None,
                              drop_direction=None,
                              finished: bool = False,
                              error_log: bool = False):
        save_path = self.path / "print_progress.json"

        if save_path.exists():
            data = json.loads(save_path.read_text())
        else:
            data = {
                "current_structure": {},
                "finished_structures": [],
                "error log": []
            }
        if error is not None:
            e = error
            print(e)
        if not finished:
            data["current_structure"] = {"name": name,
                                         "finished layer": layer_id,
                                         "layer count (n printed layers)": layer_count,
                                         "order": order,
                                         "error": str(error),
                                         "drop direction": drop_direction.to_text() if drop_direction is not None else "No information",
                                         "information": "order -1 -> Drop direction negative.\norder +1 -> Drop direction positive.\nlayer count varies, because if a print is aborted and restarted the layer count give the amount of printed layers in that print instance."
                                         }
            if error_log:
                data["error log"].append(data["current_structure"])
        else:
            # Without any printed layer there is no current structure yet; record at least its name
            completed_structure = data["current_structure"] or {"name": name, "finished layer": layer_id}
            data["finished_structures"].append(completed_structure)
            if error_log:
                data["error log"].append(data["current_structure"])
            data["current_structure"] = {}

        save_path.write_text(json.dumps(data, indent=4))

    def restart_experiment(self):
        progress_path = self.path / "print_progress.json"

        if not progress_path.exists():
            raise ValueError("No print progress file found.")

        # loading print progress data
        print_data = json.loads(progress_path.read_text())

        # retrieve original programs
        self.retrieve_programs()

        # finished structures
        finished_names = {
            s["name"] for s in print_data["finished_structures"]
        }

        # printed structure where the print was aborted - or an empty dictionary
        current_structure = print_data.get("current_structure", {})

        resume_name = None
        resume_layer_id = None
        resume_order = None

        if current_structure:
            resume_name = current_structure["name"]
            resume_layer_id = current_structure["finished layer"]
            resume_order = current_structure["order"]

        # filter out every finished structures
        remaining_structures = [
            s for s in self.structure_configs
            if s["name"] not in finished_names
        ]

        # Iterate over all remaining (not fully finished) structures
        for config in remaining_structures:

            name = config["name"]
            layer_files = [Path(p) for p in config["layer_files"]]

            # If this structure was partially printed, trim the layer list
            if name == resume_name:
                self.log.info(
                    f"Resuming structure '{name}' at layer {resume_layer_id}"
                )

                # OLD--------------------------------------------------------------
                #     if resume_order == 1:
                #         layer_files = layer_files[resume_layer + 1:]
                #     elif resume_order == -1:
                #         layer_files = layer_files[:resume_layer]
                #         layer_files = layer_files[::-1]  # reverse order
                #     else:
                #         raise ValueError("Invalid resume order")
                # NEW--------------------------------------------------------------
                # long version of the short for block below
                # for f in layer_files:
                #     layer_id = extract_layer_id(f)
                #
                #     if resume_order == 1:
                #         if layer_id > resume_layer_id:
                #             remaining_layers.append(f)
                #
                #     elif resume_order == -1:
                #         if layer_id < resume_layer_id:
                #             remaining_layers.append(f)
                #
                #     else:
                #         raise ValueError("Invalid resume order")

                # helper function to extract layer id from filename
                def extract_layer_id(path):
                    return int(str(path).split('.')[-2])

                # always sort ascending
                layer_files = sorted(layer_files, key=extract_layer_id)

                remaining_layers = []
                for f in layer_files:
                    layer_id = extract_layer_id(f)

                    if (layer_id - resume_layer_id) * resume_order > 0:
                        remaining_layers.append(f)

                layer_files = remaining_layers

            self.print_structure(
                layer_files,
                x=config["center_x"],
                y=config["center_y"],
                name=name,
                power=config["power"],
                dhm_image_count=config["number of dhm images"],
                restart=True
            )

    def measure(self,
                coordinate: Coordinate,
                name: str,
                camera_path: Path,
                dhm_path: Path,
                dhm_image_count: int = 0,
                ) -> tuple[Container, ImageContainer]:
        """
        Coordinate in mm in absolute coordinates
        """

        # Move to given absolute coordinate
        self.a3200.api.LINEAR(**coordinate, F=20)

        # Take DHM image
        if self.system.dhm is not None:
            dhm_container = self.system.dhm.container(opt=False, image_count=dhm_image_count)
            fn = dhm_path / f"dhm_{name}.zdc"
            dhm_container.write(fn)
            self.log.info(f"DHM image: '{fn}'")
        else:
            self.log.info(f"DHM images was not captured!")
            dhm_container = None

        # Take camera image
        camera_container = self.system.getimage()
        fn = camera_path / f"camera_{name}.zdc"
        camera_container.write(fn)
        self.log.info(f"Camera image: '{fn}'")

        # Return DHM image and camera image
        return dhm_container, camera_container

    # def measurement_factory(self,
    #         #system: System,
    #         coordinate: Coordinate,
    #         name: str,
    #         #*,
    #         #save_folder: Path
    # ) -> Callable[[int], None]:
    #     """
    #     Coordinate in mm in absolute coordinates
    #     """
    #
    #     def do_measurement(layer_id: int):
    #         # Move to given absolute coordinate
    #         self.a3200.api.LINEAR(**coordinate, F=20)
    #
    #         # Take DHM image
    #         dhm_container = self.system.dhm.container(opt=True)
    #         fn = self.path / "dhm" / f"hologram_{name}.{layer_id}.zdc"
    #         dhm_container.write(fn)
    #         self.log.info(f"Hologram image: '{fn}'")
    #
    #         # Take camera image
    #         camera_container = self.system.getimage()
    #         fn = self.path / "camera" / f"camera_{name}.{layer_id}.zdc"
    #         camera_container.write(fn)
    #         self.log.info(f"Camera image: '{fn}'")
    #
    #         return None
    #
    #     return do_measurement
