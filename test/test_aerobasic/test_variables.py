"""Tests for AeroBasic program variables (AerotechVariable, create_variable)."""
from nanofactorysystem.aerobasic.programs import AeroBasicProgram, AerotechVariable


def test_create_variable_declares_name_once():
    program = AeroBasicProgram()

    first = program.create_variable("dz")
    second = program.create_variable("dz")

    assert isinstance(first, AerotechVariable) and isinstance(second, AerotechVariable)
    assert program.variable_names == ["dz"]


def test_variable_assignment_via_send_and_call():
    program = AeroBasicProgram()
    dz = program.create_variable("dz")

    dz.set(0.5)
    dz("$global[0]")

    assert program.lines == ["$dz = 0.5", "$dz = $global[0]"]


def test_declaration_block_layout():
    program = AeroBasicProgram()
    program.create_variable("a").set(1)

    assert program.to_text(add_timestamp=False) == (
        "' Declare variables\n"
        "DVAR $a\n"
        "\n"
        "$a = 1\n"
        "END PROGRAM\n"
    )
    assert program.to_text(add_timestamp=False, compact=True) == "DVAR $a\n$a = 1\nEND PROGRAM\n"
