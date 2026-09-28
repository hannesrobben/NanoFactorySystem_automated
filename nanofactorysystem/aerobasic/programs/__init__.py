import datetime
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from nanofactorysystem.aerobasic import AeroBasicAPI


class AerotechVariable(AeroBasicAPI):

    def __init__(self, name: str, program: "AeroBasicProgram"):
        super().__init__()
        self.name = name
        self.program = program

    def __call__(self, command: str) -> str:
        """ Assign the result of the given command to the variable, same as :meth:`send`. """
        return self.send(command)

    def send(self, command: str) -> str:
        return self.program.send(f"${self.name} = {command}")

    def set(self, value: str | int | float) -> str:
        """ Basically same as self.send, but used for values instead of commands """
        return self.program.send(f"${self.name} = {value}")


class AeroBasicProgram(AeroBasicAPI):

    def __init__(self):
        super().__init__()
        self.lines = []
        self.variable_names = []

    def __repr__(self):
        return f"{self.__class__.__name__}({len(self.lines)} lines. {len(self.variable_names)} variables)"

    def __str__(self) -> str:
        return self.to_text()

    def __add__(self, other: Any) -> "AeroBasicProgram":
        """
        :param other: Can be either AeroBasicProgram or str.
                      Typehint doesn't work with AeroBasicProgram...
        :return: New AeroBasic Program which is a combination of both programs
        """
        new_program = AeroBasicProgram()
        if isinstance(other, AeroBasicProgram):
            # Add two programs together
            new_program.lines = self.lines + other.lines
            new_variables = set(self.variable_names)
            new_variables.update(other.variable_names)
            new_program.variable_names = list(new_variables)
        elif isinstance(other, str):
            # Copy lines
            new_program.lines = self.lines + [other]
            new_program.variable_names = list(self.variable_names)
        else:
            raise TypeError(f"Cannot add {type(other)} to {self.__class__.__name__}.")

        return new_program

    def __iter__(self):
        for line in self.lines:
            yield line

    def __call__(self, program):
        if isinstance(program, str):
            for line in program.split("\n"):
                self.send(line)
        elif isinstance(program, AeroBasicProgram):
            self.add_programm(program)

    @property
    def n_lines(self):
        return len(self.lines)

    @contextmanager
    def critical_section(self):
        self.send("CRITICAL START")
        try:
            yield self
        finally:
            self.send("CRITICAL END")

    def send(self, command: str) -> str:
        if command.endswith("\n"):
            command = command[:-1]
        self.lines.append(command)
        return command

    def add_programm(self, program: "AeroBasicProgram"):
        # print(f"{len(program.lines)} lines \t{program.__str__()}")
        self.lines += program.lines

    def to_text(self, *, with_variables=True, with_ending=True, compact=False, add_timestamp=True) -> str:
        # TODO(dwoiwode): Make compact even more compact by multiple variable declarations per line
        s = ""
        if add_timestamp:
            s += f"' Created on {datetime.datetime.now():%Y-%m-%d %H:%M:%S.%f} by ({self.__class__.__name__})\n"
            # TODO(dwoiwode): More metadata?

        if with_variables and len(self.variable_names) > 0:
            if not compact:
                s += "' Declare variables\n"
            s += "".join(map(lambda var: f"DVAR ${var}\n", self.variable_names))
            if not compact:
                s += "\n"  # Extra line break for clarity

        s += "\n".join(self.lines)
        s += "\n"  # End last line
        if with_ending:
            s += "END PROGRAM\n"

        return s

    def write(self, file: Path | str, *, compact=False, create_folder=True) -> str:
        s = self.to_text(compact=compact, add_timestamp=True)
        if create_folder:
            Path(file).parent.mkdir(exist_ok=True, parents=True)
        Path(file).write_text(s)
        return s

    def create_variable(self, name: str) -> AerotechVariable:
        variable = AerotechVariable(name, self)
        if name not in self.variable_names:
            self.variable_names.append(name)
        return variable

    def comment(self, text: str) -> str:
        for line in text.split("\n"):
            if line:
                self.send(f"' {line}")
            else:
                self.send("")

    def optimize(self, *, remove_comments=False, remove_whitespace=False) -> "AeroBasicProgram":
        new_program = AeroBasicProgram()
        for line in self.lines:
            if remove_whitespace and line.strip() == "":
                continue
            if remove_comments and line.startswith("'"):
                continue

            # TODO: Mode check for e.g. VELOCITY ON, ABSOLUTE, ...

            new_program.send(line)

        return new_program
