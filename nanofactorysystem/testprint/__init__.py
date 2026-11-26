"""Standard parameter test prints (phase 11, design docs/design/TEST_PRINT_PTD01.md).

Library for test fields: a field is one ``DrawableObject`` whose cells each have their own
parameters (power, z, hatch, slice distance). The modules are independent of
``nanofactorysystem.experiment`` so that every field can be built and tested without a system.

- ``structure``: ``ParameterFieldStructure``, toolpath IR → IFOV layer programs (T137)
- ``cells``: cell primitives and analytic height maps, aligned z grid, substrate anchoring (T138)
- ``ordering``: in-layer ordering strategies, registered by name (T139)
- ``field``: ``ParameterField``, ``CellSpec``, header, validation, cell table (T139)
- ``voxel_fit``: ``VoxelFitModel`` w(P), l(P) (T150)
- ``calibration``: ``ProcessCalibration`` (T140), the evaluation result of the voxel fit

Parameter tests version 2 (design ``docs/design/PARAMETER_TESTS.md``; single stage, absolute axes):

- ``inputs``: ``ParameterTestInputs``, the material start file of all three tests (T158)
- ``parameter_tests``: field builders of Quick PT, Full PT-01 and Voxel PT-01 (T159–T161)
- ``pt_factories``: named structure factories ``quick_pt.*``, ``full_pt01.*``, ``voxel_pt01.gap``

The two-stage PTD-01 of version 1 (``ptd01``, ``factories``, ``StageAAxes``, ``mains/Experiments/ptd01/``) was moved
to the attic (T164, ``docs/ATTIC_INDEX.md``).
"""
from .calibration import ProcessCalibration
from .field import CellSpec, FieldLayoutError, ParameterField
from .ordering import ordering_names, register_ordering
from .structure import ParameterFieldStructure, field_builder, field_builder_names, register_field_builder
from .voxel_fit import VoxelFitModel
from .inputs import ParameterTestInputs  # noqa: E402
from . import parameter_tests  # noqa: E402,F401  registers the parameter-test field builders
from . import pt_factories  # noqa: E402,F401  registers the parameter-test structure factories

__all__ = ["CellSpec", "FieldLayoutError", "ParameterField", "ParameterFieldStructure", "ProcessCalibration",
           "VoxelFitModel", "ParameterTestInputs", "field_builder", "field_builder_names", "ordering_names",
           "register_field_builder", "register_ordering"]
