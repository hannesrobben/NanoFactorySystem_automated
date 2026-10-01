##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Names and version of the experiment file schema (docs/design/EXPERIMENT_STORAGE.md §5, §9)."""

FILE_TYPE = "nanofactory.experiment"
SCHEMA_VERSION = "1.0"
FILE_NAME = "experiment.h5"
LOCK_NAME = "experiment.lock"

# Status values of the experiment file (root attribute "status")
STATUS_CREATED = "created"
STATUS_BUILT = "built"
STATUS_PRINTING = "printing"
STATUS_FINISHED = "finished"
STATUS_ABORTED = "aborted"
STATUS_FAILED = "failed"

# Experiment constructor parameters: (constructor argument, key in experiment_dictionary.json,
# attribute in /metadata/experiment, kind). Kinds: "float", "int", "bool", "str",
# "vector" (float array), "ivector" (int array), "enum" (stored by name).
PARAMETERS = (
    ("default_power", "default_power", "default_power_mw", "float"),
    ("low_speed_um", "low_speed_um", "low_speed_um_s", "float"),
    ("high_speed_um", "high_speed_um", "high_speed_um_s", "float"),
    ("resin_corner_tr", "resin_corner_tr", "resin_corner_tr_um", "vector"),
    ("resin_corner_bl", "resin_corner_bl", "resin_corner_bl_um", "vector"),
    ("structure_size", "structure_size", "structure_size_um", "float"),
    ("margin", "margin", "margin_um", "float"),
    ("padding", "padding", "padding_um", "float"),
    ("absolute_grid_center", "absolute_grid_center", "center_um", "vector"),
    ("grid", "grid_size", "grid", "ivector"),
    ("n_mid_points", "n_mid_points", "n_mid_points", "int"),
    ("drop_direction", "drop_direction", "drop_direction", "enum"),
    ("corner_z", "corner_z", "corner_z_um", "float"),
    ("corner_width", "corner_width", "corner_width_um", "float"),
    ("corner_length", "corner_length", "corner_length_um", "float"),
    ("corner_height", "corner_height", "corner_height_um", "float"),
    ("corner_hatch", "corner_hatch", "corner_hatch_um", "float"),
    ("corner_slice", "corner_slice", "corner_slice_um", "float"),
    ("fov_dim", "fov_dim", "fov_um", "vector"),
    ("skip_corner", "skip_corner", "skip_corner", "bool"),
    ("plane_fit_mode", "plane_fit_mode", "plane_fit_mode", "enum"),
    ("setup", "setup", "setup", "str"),
    ("tilt_warning_um", "tilt_warning_um", "tilt_warning_um", "float"),
    ("camera_capture", "camera_capture", "camera_capture", "bool"),
    ("program_source", "program_source", "program_source", "enum"),
    ("resin_edges", "resin_edges", "resin_edges_um", "points"),
    ("layer_overhead_s", "layer_overhead_s", "layer_overhead_s", "float"),
    ("overview_capture", "overview_capture", "overview_capture", "bool"),
    ("overview_single_images", "overview_single_images", "overview_single_images", "bool"),
    ("overview_pixel_um", "overview_pixel_um", "overview_pixel_um", "float"),
)


def schema_major(version: str) -> int:
    """ Return the major number of a schema version string such as ``"1.0"``. """

    return int(str(version).split(".")[0])
