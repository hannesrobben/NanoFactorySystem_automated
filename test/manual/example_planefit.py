from nanofactorysystem.devices.coordinate_system import PlaneFit
from scidatacontainer import Container
import numpy as np

plane_zdc_path = path / "planefit" / "plane.zdc"  # path of the folder where the plane.zd file is
dc = Container(file=str(plane_zdc_path))

if self.drop_direction == DropDirection.DOWN:  # not really necessary to do it in dependence of this variable. also possible to just think and take the right points
    plane_points = dc["meas/result.json"]["low"][
        "points"]  # normally our case with 63x objective. If we change the objective or orientation of the substrate - this has to be changed!
else:
    plane_points = dc["meas/result.json"]["high"]["points"]

plane_fit_function = PlaneFit.from_points(np.asarray(plane_points))  # in um

# to get the corresponding z-value at an arbitrary point(x,y) , just do this
x, y = 0, 0
z = plane_fit_function(x, y)
