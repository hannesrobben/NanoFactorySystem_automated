"""Standard parameter test prints (phase 11, design docs/design/TEST_PRINT_PTD01.md).

Library for test fields: a field is one ``DrawableObject`` whose cells each have their own
parameters (power, z, hatch, slice distance). The modules are independent of
``nanofactorysystem.experiment`` so that every field can be built and tested without a system.

- ``structure``: ``ParameterFieldStructure``, toolpath IR → IFOV layer programs (T137)
"""
from .structure import ParameterFieldStructure, field_builder, field_builder_names, register_field_builder

__all__ = ["ParameterFieldStructure", "field_builder", "field_builder_names", "register_field_builder"]
