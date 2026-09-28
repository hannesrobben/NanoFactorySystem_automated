##########################################################################
# Copyright (c) 2022-2025 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################

import datetime
import os
from pathlib import Path
from tkinter import messagebox
import numpy as np

from typing import Tuple, List

from nanofactorysystem import mkdir, getLogger
from nanofactorysystem.aerobasic.programs.drawings.lines import Stair, Rectangle3D
from nanofactorysystem.aerobasic.programs.drawings.lens import AsphericalLens
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import Experiment, StructureType

sys_args = {
    "attenuator": {
        "fitKind": "quadratic",
    },
    "sample": {
        "name": "#1",
        "orientation": "top",
        "substrate": "boro-silicate glass",
        "substrateThickness": 700.0,
        "material": "SZ2080",
        "materialThickness": 75.0,
    },
    "focus": {},
    "layer": {
        "beta": 0.7,
    },
    "plane": {},
}


def focal_point_matrix_maker(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
                             objective="Zeiss 20x", user="Hannes"):
    """
        absolute_center: Point2D with x- and y-coordinate of the center of this experiment
        resin_dimension: list of the coordinates of the edges of the resin
                [[right edge],   Example:   [[100, 18550],
                [left edge],                [200, 26300],
                [near edge],                [-3500, 22400],
                [far edge]]                 [4000, 22400]]
        ask_continue_box: bool -> controls the asking box
        path: Path argument for root directory where the experimental data will be safe in a subdirectory called ...
                If nothing is given, the export_path will be in the subdirectory .output
    """
    # deleting all the different data of previous prints
    if path is None:
        path = Path(mkdir(f".output/focal_point/{datetime.datetime.now():%Y%m%d}", clean=False))
    else:
        assert (path, Path)
        path = Path(mkdir(os.path.join(path, "focal_point")))
    logger = getLogger(logfile=f"{path}/console.log")

    # Size of (oval) resin drop in micrometres
    edges = np.asarray(resin_dimension)
    resin_corner_tr = Point2D(*np.max(edges, axis=0))
    resin_corner_bl = Point2D(*np.min(edges, axis=0))
    absolute_grid_center = absolute_center

    if objective == "Zeiss 20x":
        fov = 500
        zmax = 25700.0
        # Corner settings
        c_width = 50
        c_length = 300
        c_height = 7
        c_hatch = 0.5
        c_slice = 0.75
        # printing area settings
        margin = 200
        padding = 100

    elif objective == "Zeiss 63x":
        fov = 150
        zmax = 25500.0  # could possibly be up to 25550 µm
        # Corner settings
        c_width = 30
        c_length = 120
        c_height = 7
        c_hatch = 0.3
        c_slice = 0.75
        # printing area settings
        margin = 50
        padding = 100

    else:
        raise Exception(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")

    sys_args.update({"controller": {
        "zMax": zmax, }
    })

    with Experiment(
            path=path,
            user=user,
            objective=objective,
            logger=logger,
            sys_args=sys_args,
            default_power=0.7,
            low_speed_um=1000,
            high_speed_um=5000,
            resin_corner_tr=resin_corner_tr,
            resin_corner_bl=resin_corner_bl,
            structure_size=fov,
            margin=10,
            padding=10,
            absolute_grid_center=absolute_grid_center,
            grid=(2, 3),  # ToDo: changing depending on experiment
            n_mid_points=0,  # ToDo changing depending on experiment
            plane_fit_mode=1,  # only plane-fitting on the four edges
            drop_direction=DropDirection.DOWN,
            corner_z=-2,
            corner_width=c_width,
            corner_length=c_length,
            corner_height=c_height,
            corner_hatch=c_hatch,
            corner_slice=c_slice) as experiment:

        # Visualize experiment
        experiment.plot_experiment(show=True)

        # Get substrate surface plane
        if ask_continue_box and not messagebox.askyesno(message="Run plane fitting?"): return
        experiment.plane_fit(force=False)

        # Optical path length for DHM
        if ask_continue_box and not messagebox.askyesno(message="Run OPL motor scan?"): return
        experiment.opl_scan(m0=3847.0, force=False)

        # TODO: Take image of whole scene
        # center = experiment.coordinate_system_grid_to_absolute.convert({"X": 0, "Y": 0, "Z": 0})
        # experiment.measure(coordinate=center, name="before")

        # ----------------------------------------------------------------------------------------------------------------------
        # ----------------------------------------------------------------------------------------------------------------------
        # Add structures

        experiment.skip_structure()
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="stair_galvo",
            axes="ABZ",
            power=700, #change!
            structure=Stair(
                Point3D(0, 0, -2),
                n_steps=6,
                step_height=0.6,
                step_length=20,
                step_width=50,
                hatch_size=0.125,
                slice_size=0.3,
                socket_height=7,
                velocity=5000,
                acceleration=experiment.accel_a_um))
        # ----------------------------------------------------------------------------------------------------------------------
        # ----------------------------------------------------------------------------------------------------------------------

        # Build corner and structure programs
        if ask_continue_box:
            if messagebox.askyesno(message="Create programs for all structures?"):
                experiment.build_programs()
            else:
                if messagebox.askyesno(message="Programs already created?"):
                    experiment.retrieve_programs()
        else:
            experiment.build_programs()

        # Print corners and structures
        if ask_continue_box and not messagebox.askyesno(message="FINAL STEP: Print experiment?"): return
        experiment.print_experiment()

        # TODO: Take image of whole scene
        # experiment.measure(coordinate=center, name="after")

"""
------------------------------------------------------------------------------------------------------------------------
"""
    # generate a x-y list for possible points
    # validate if points are minimum of min_dist away from each other
    # speed and power have to be given

    # not possible as a program - because of capturing image? Maybe direct control of the system
    # --- program ---
    # move to x y z
    # take image (before)
    # laser on
    # move dz down/ up
    # laser off
    # take image (after)

# ToDo Put this in front of the area where the zline matrix is executed

from scidatacontainer import Container
from nanofactorysystem.devices.coordinate_system import PlaneFit
"""
plane_zdc_path = path / "planefit" / "plane.zdc"  # main experiment path!
dc = Container(file=str(plane_zdc_path))

if self.drop_direction == DropDirection.DOWN:
    plane_points = dc["meas/result.json"]["low"]["points"]
else:
    plane_points = dc["meas/result.json"]["high"]["points"]

plane_fit_function = PlaneFit.from_points(np.asarray(plane_points))  # in um

"""
# log.info(str(plane_fit_function))

def initiate_container(config, parameter, **kwargs):
    # General metadata
    content = {
        "containerType": {"name": "Focal Point maker", "version": 1.1},
    }
    meta = {
        "title": "Focal lines for AI classifier",
        "description": "Image of pre and post z-line exposure used for AI classifier.",
        "author": config["author"]
    }
    # Container dictionary
    items = {
        "content.json": content,
        "meta.json": meta,
        "data/general_information.json": parameter,
    }
    # initiate container here and then only update it after each iteration
    # Hint possible that the config doesnt qwork because the config (author) has to be i meta
    return Container(items=items, config=config, **kwargs)


def make_dict(img_pre, img_post, exposure_dict, focal_point_number):
    # ToDo add further information's to the dictionary
    """ Return results as SciDataContainer. """

    # Container dictionary
    tmp_dict = {
        f"focal_point_{focal_point_number}/data/exposure.json": exposure_dict,
        f"focal_point_{focal_point_number}/meas/img_pre.png": img_pre,
        f"focal_point_{focal_point_number}/meas/img_post.png": img_post,
    }

    return tmp_dict


def z_line_exposure(system, x, y, z, z_camera_offset, fast, delay, speed, duration, power, dz):
    # Move to point position to capture image
    system.moveabs(fast, delay, x=x, y=y, z=z + z_camera_offset)
    # Take pre exposure camera image
    img0 = system.getimage()
    # move to correct z-position
    system.moveabs(fast, delay, z=z)

    # ToDo : Check if dz will be split in half or if it will be printed continuously
    # ToDo: probably recalculate z with dz/2
    # Expose axial line
    if dz != 0.0:
        v = min(speed, dz / duration)
        dt = dz / v
        system.zline(power, fast, v, dz)
        system.wait("XYZ", delay)

    # Expose a dot
    else:
        v = 0.0
        dz = 0.0
        dt = duration
        system.pulse(power, dt)

    # Take post exposure camera image
    system.moveabs(fast, delay, z=z + z_camera_offset)
    img1 = system.getimage()

    # Exposure data
    exposure = {
        "x": x,
        "y": y,
        "zCenter": z,
        "zLength": dz,
        "fastSpeed": fast,
        "destinationDelay": delay,
        "setSpeed": speed,
        "setDuration": duration,
        "speed": v,
        "duration": dt,
    }
    return img0, img1, exposure


def z_line_matrix(experiment,
                  n_points: int, min_distance: Tuple[float, float], dz: float,
                  boundary: Tuple[Tuple[float, float], Tuple[float, float]],
                  speed: float, power: float,
                  plane_fit_function, save_path, number_of_field=0):
    # ToDo:
    #   - define min_distance
    #   - define different dz -- maybe also with an additional noise parameter so that it is always somewhat different
    #   - define boundary -- important
    #   - implement all the other variable etc above this methods in the script

    # Hint: could be that this will fail! - see focus.container self.config in parameter.py
    author = experiment.user.get("name", None),
    email = experiment.user.get("email", None),
    organization = experiment.user.get("organization", None),
    orcid = experiment.user.get("orcid", None)

    config = {
        "autor": author,
        "email": email,
        "organization": organization,
        "orcid": orcid,
    }
    current_index = 0  # running variable for differentiate the focal lines
    tmp_dict = {}  # temporary dictionary to save all img and corresponding data

    # sampling n points for z-line
    points_coords = random_point_sampling(n_points, min_distance, boundary)
    system = experiment.system

    z_camera_offset = -5.0  # default value taken from focus.py (14.01.25)
    duration = 0.2  # default value taken from layer.py (14.01.25)

    # Maximum Speed and Delay time after stages reached their destination
    fast = system["speed"]
    delay = system["delay"]

    parameter_infos = {
        "zOffsetCamera": z_camera_offset,
        "duration": duration,
        "laserPower": power,
        "plane_fit_function": str(plane_fit_function),
        "minimalDistance": min_distance,
        "boundary": boundary,
        "numberOfPoints": n_points,
        "lineLength": dz,
        "fieldOfExperiment": number_of_field,
    }

    z_line_zdc_path = f"{save_path}/z_line_matrix_{number_of_field}.zdc"
    # todo check if z_line_zdc_path already exists
    dc = initiate_container(config, parameter_infos)  # Container for all results
    dc.write(z_line_zdc_path)

    for x, y in points_coords:
        current_index += 1
        z = plane_fit_function(x, y)
        dz_exposure = dz  # ToDo : add noise here , so the dz's are all a little bit different
        img0, img1, exposure_dict = z_line_exposure(system, x, y, z, z_camera_offset, fast, delay, speed, duration,
                                                    power, dz_exposure)
        tmp = make_dict(img0, img1, exposure_dict, focal_point_number=current_index)
        tmp_dict.update(tmp)

    dc_old = dc.items()  # get prior items
    dc_old.update(tmp_dict)  # update with all images and infos
    dc_new = Container(items=dc_old, config=config)
    dc_new.write(z_line_zdc_path)


def random_point_sampling(n_points: int, min_distance: Tuple[float, float],
                          boundary: Tuple[Tuple[float, float], Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Generate random points with minimum distance constraints between their coordinates.

    Args:
        n_points: Number of points to generate
        min_distance: (min_x_distance, min_y_distance) minimum distances between points
        boundary: ((min_x, max_x), (min_y, max_y)) boundary constraints

    Returns:
        List of (x, y) coordinate tuples
    """
    points_coords = []
    max_attempts = 50  # Prevent infinite loops

    for i in range(n_points):
        valid_point = False
        attempts = 0

        while not valid_point and attempts < max_attempts:
            # Generate random point
            x = np.random.uniform(boundary[0][0], boundary[0][1])
            y = np.random.uniform(boundary[1][0], boundary[1][1])

            if not points_coords:  # First point is always valid
                valid_point = True
            else:
                # Check distance from all previous points
                too_close = False
                for prev_x, prev_y in points_coords:
                    x_diff = abs(x - prev_x)
                    y_diff = abs(y - prev_y)

                    if x_diff < min_distance[0] or y_diff < min_distance[1]:
                        # If too close, adjust the point by adding the remaining distance needed
                        if x_diff < min_distance[0]:
                            adjustment = min_distance[0] - x_diff
                            x = x + adjustment if x >= prev_x else x - adjustment
                        if y_diff < min_distance[1]:
                            adjustment = min_distance[1] - y_diff
                            y = y + adjustment if y >= prev_y else y - adjustment

                        # Ensure point stays within boundaries
                        x = np.clip(x, boundary[0][0], boundary[0][1])
                        y = np.clip(y, boundary[1][0], boundary[1][1])

                        too_close = True
                        break

                if not too_close:
                    valid_point = True

            attempts += 1

        if valid_point:
            points_coords.append((x, y))
        else:
            print(f"Warning: Could not find valid position for point {i} after {max_attempts} attempts")

    return points_coords


if __name__ == '__main__':
    path = r"C:\Users\hanne\Desktop\test_scidatacontainer"
    os.makedirs(path, exist_ok=True)

    config = {
        "author": "Hannes",
        "email": "email@von.hannes",
        "organization": "Here",
        "orcid": "Zahlen",
    }
    test_infos = {
        "zOffsetCamera": 1,
        "duration": 2,
        "laserPower": 3,
    }
    test_dict = test_infos

    # release technique
    dc = initiate_container(config=config, parameter=test_infos)
    dc.write(f"{path}/container_original.zdc")
    dc.release()
    dc["data/test.json"] = test_dict
    dc.write(f"{path}/container_original.zdc")
    # items technique
    dc1 = dc.items()
    dc_container = Container(items=dc1)
    dc_container.write(f"{path}/container_original.zdc")
