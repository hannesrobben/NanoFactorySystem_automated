##########################################################################
# Copyright (c) 2022-2024 Reinhard Caspary                               #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################

from nanofactorysystem import System, Focus, getLogger, mkdir

args = {
    "attenuator": {
        "fitKind": "quadratic",
    },
    "controller": {
        "zMax": 25465.0,
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
}

dz = 10.0
dz_str = str(dz)[:-2]
power = 0.7
speed = 200.0
duration = 0.2

lateral_pitch = 4.0

user = "Hannes"
objective = "Zeiss 63x"
path = mkdir(f".test/{dz_str}dz/focus")
logger = getLogger(logfile=f"{path}/console.log")

logger.info("Initialize system object...")
with System(user, objective, logger, **args) as system:
    logger.info("Initialize focus object...")
    focus = Focus(system, logger, **args)

    logger.info("Store background image...")
    focus.imgBack.write(f"{path}/back.zdc")

    logger.info("Expose vertical line and detect focus...")
    z = system.z0
    x0 = system.x0
    y0 = system.y0

    x=x0
    # 10x10 grid for testing the focus
    for i in range(10):         # move in x direction
        x=x0+i*lateral_pitch
        for j in range(10):     # move in y-direction
            path = mkdir(f".test/{dz_str}dz/focus{i}_{j}")
            y=y0+j*lateral_pitch

            focus.run(x, y, z, dz, power, speed, duration)

            logger.info("Store images...")
            focus.imgPre.write(f"{path}/image_pre.zdc")
            focus.imgPost.write(f"{path}/image_post.zdc")

            logger.info("Store results...")
            dc = focus.container()
            dc.write(f"{path}/focus.zdc")

    logger.info("Done.")
