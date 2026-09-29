import abc
import datetime
import hashlib
import random
import time
from os import PathLike
from pathlib import Path
from typing import Optional

from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface
from nanofactorysystem.aerobasic.constants import TaskState
from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings import DrawableObject, DrawableAeroBasicProgram
from nanofactorysystem.devices.aerotech import Task
from nanofactorysystem.devices.coordinate_system import CoordinateSystem
from nanofactorysystem.utils.visualization import read_text, plot_movements


class LayerFactory(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def next_layer(self, feedback) -> AeroBasicProgram:
        pass


class ListLayerFactory(LayerFactory):
    def __init__(self, layers: list[AeroBasicProgram]):
        super().__init__()
        self.layers = layers
        self.index = 0

    def next_layer(self, feedback) -> AeroBasicProgram:
        if self.index > len(self.layers):
            raise StopIteration()
        layer = self.layers[self.index]
        self.index += 1
        return layer


class SingleLayerFactory(ListLayerFactory):
    def __init__(self, layer: AeroBasicProgram):
        super().__init__([layer])


class ExecutableObject:
    def __init__(self):
        pass

    @abc.abstractmethod
    def execute(self, api: AerotechAsciiInterface):
        pass


class MultiStageTask(ExecutableObject):
    def __init__(self, drawable_object: DrawableObject, coordinate_system:CoordinateSystem):
        super().__init__()
        self.layer_factory = drawable_object
        self.coordinate_system = coordinate_system

        self._before_drawing_functions = []
        self._after_drawing_functions = []

        self._before_layer_functions = []
        self._after_layer_functions = []

    def execute(self, api: AerotechAsciiInterface):
        for function in self._before_drawing_functions:
            function()

        layer_iterator = self.layer_factory.iterate_layers(self.coordinate_system)
        program_step = 0
        full_program = DrawableAeroBasicProgram(self.coordinate_system)
        while True:
            try:
                layer_program = next(layer_iterator)
                full_program.add_programm(layer_program)
                program_file_path = path / "programs" / "layers" / f"structure_{program_step:02d}.{program_step:03d}.txt"
                layer_program.write(program_file_path)
                t1 = time.time()
                try:
                    task = run_program_as_task(layer, task_id=1)
                    task.wait_to_finish()
                    task.finish()
                    measure(system, structure_center_absolute_mm, f"Structure_{i:02d}_{layer_id:03d}",
                                save_folder=path)
                except AerotechError as e:
                    logger.error(f"Program failed for structure {i:02d}: {e}")

                program_step += 1
            except StopIteration:
                break

        movements = read_text(full_program.to_text())
        plot_movements(movements)


    def run_program_as_task(
            self,
            program: PathLike | AeroBasicProgram,
            *,
            task_id: Optional[int] = None,
            program_ready_timeout=10,  # Seconds
            program_start_running_timeout=10,  # Seconds
    ) -> Task:
        # Either use path as program or convert AeroBasicProgram to temporary file
        if isinstance(program, AeroBasicProgram):
            now = datetime.datetime.now()
            hash_str = hashlib.sha256(str(random.random()).encode()).hexdigest()
            path = Path(f"{now :%Y%m%d_%H%M%S}_automatic_program_{hash_str[:5]}.pgm")
            path.parent.mkdir(exist_ok=True, parents=True)
            program.write(path)
        else:
            path = Path(program)

        # Load program
        if task_id is None:
            task_id = 2
        self.api.PROGRAM_LOAD(task_id, path)

        # Wait for program to be ready
        task = Task(self.api, task_id, file_path=path)
        query_delay = 0.1
        for i in range(int(program_ready_timeout / query_delay)):
            task.update()
            if task.task_state == TaskState.program_ready:
                break
            time.sleep(query_delay)
        else:
            raise RuntimeError(f"Could not load program {path} after {program_ready_timeout} seconds!")

        # Start program
        self.api.PROGRAM_START(task_id)

        # Wait for program to run
        for i in range(int(program_start_running_timeout / query_delay)):
            task.update()
            if task.task_state == TaskState.program_running:
                break
            time.sleep(query_delay)
        else:
            raise RuntimeError("Program did not start")

        return task

if __name__ == '__main__':
    def measure():
        pass

