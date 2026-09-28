##########################################################################
# Copyright (c) 2022-2024 Reinhard Caspary                               #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################

from nanofactorysystem import System, Layer, getLogger, mkdir

args = {
    "attenuator": {
        "fitKind": "quadratic",
        },
    "controller": {
        "zMax": 25700.0,
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
    }

user = "Reinhard"
objective = "Zeiss 20x"
path = mkdir(".test/layer")
logger = getLogger(logfile=f"{path}/console.log")

logger.info("Initialize system object...")
with System(user, objective, logger, **args) as system:

    logger.info("Initialize layer object...")
    layer = Layer(system, logger, **args)

    logger.info("Store background image...")
    layer.focus.imgBack.write(f"{path}/back.zdc")

    logger.info("Run layer detection...")
    x = system.x0
    y = system.y0
    zlo = zup = system.z0
    layer.run(x, y, zlo, zup, path=path)

    logger.info("Run pitch detection...")
    ((pxx, pxy), (pyx, pyy)) = layer.pitch()
    logger.info(f"Camera pitch xx: {pxx:.3f} µm/px")
    logger.info(f"Camera pitch xy: {pxy:.3f} µm/px")
    logger.info(f"Camera pitch yx: {pyx:.3f} µm/px")
    logger.info(f"Camera pitch yy: {pyy:.3f} µm/px")
    
    logger.info("Store results...")
    dc = layer.container()
    dc.write(f"{path}/layer.zdc")
    logger.info("Done.")
