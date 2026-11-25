"""Standard parameter test prints (phase 11, design docs/design/TEST_PRINT_PTD01.md).

Library for test fields: a field is one ``DrawableObject`` whose cells each have their own
parameters (power, z, hatch, slice distance). The modules are independent of
``nanofactorysystem.experiment`` so that every field can be built and tested without a system.

- ``structure``: ``ParameterFieldStructure``, toolpath IR → IFOV layer programs (T137)
- ``cells``: cell primitives and analytic height maps, aligned z grid, substrate anchoring (T138)
- ``ordering``: in-layer ordering strategies, registered by name (T139)
- ``field``: ``ParameterField``, ``CellSpec``, header, validation, cell table (T139)
- ``voxel_fit``: ``VoxelFitModel`` w(P), l(P) (T150)
- ``calibration``: ``ProcessCalibration``, ``StageAAxes`` (T140)
"""
from .calibration import ProcessCalibration, StageAAxes
from .field import CellSpec, FieldLayoutError, ParameterField
from .ordering import ordering_names, register_ordering
from .structure import ParameterFieldStructure, field_builder, field_builder_names, register_field_builder
from .voxel_fit import VoxelFitModel

__all__ = ["CellSpec", "FieldLayoutError", "ParameterField", "ParameterFieldStructure", "ProcessCalibration",
           "StageAAxes", "VoxelFitModel", "field_builder", "field_builder_names", "ordering_names",
           "register_field_builder", "register_ordering"]
