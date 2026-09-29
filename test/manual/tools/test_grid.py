##########################################################################
# Copyright (c) 2022-2024 Reinhard Caspary                               #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################

from nanofactorysystem import System, Layer, Grid, getLogger, mkdir

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
        "laserPower": 0.7,
        "stageSpeed": 200.0,
        "duration": 0.2,
        "dzCoarseDefault": 100.0,
        "dzFineDefault": 10.0,
        "resolution": 0.5,
        "beta": 0.7,
        },
    "grid": {
        "gridPitch": 40.0,
        "laserPower": 0.7,
        "duration": 1.0,
        },
    "dhm": {
        "host": "192.168.22.2",
        "port": 27182,
        "oplmode": "both",
        },
    }

nx = 5#9
ny = 5#7
off = 20
zlo = zup = 25200.0
dt = args["grid"]["duration"]

user = "Reinhard"
objective = "Zeiss 20x"
path = mkdir(f".test/grid-{dt:.1f}-{off:d}-{nx:d}x{ny:d}")
logger = getLogger(logfile=f"{path}/console.log")

logger.info("Initialize system object...")
with System(user, objective, logger, **args) as system:

    # Run motor scan
    logger.info("Motor scan...")
    mopt = system.dhm.opl_scan()
    m = system.dhm.device.MotorPos
    logger.info(f"Motor pos: {m:.1f} µm (set: {mopt:.1f} µm)")

    # Initialize layer object
    logger.info("Initialize layer object...")
    subpath = mkdir(f"{path}/layer")
    layer = Layer(system, logger, **args)

    # Store background image
    logger.info("Store background image...")
    layer.focus.imgBack.write(f"{subpath}/back.zdc")

    # Run layer detection
    pitch = args["grid"]["gridPitch"]
    x = system.x0 - (0.5*nx + 1)*pitch
    y = system.y0 - (0.5*ny + 1)*pitch
    layer.run(x, y, zlo, zup, path=subpath)

    # Run pitch detection
    logger.info("Run pitch detection...")
    ((pxx, pxy), (pyx, pyy)) = layer.pitch()
    logger.info(f"Camera pitch xx: {pxx:.3f} µm/px")
    logger.info(f"Camera pitch xy: {pxy:.3f} µm/px")
    logger.info(f"Camera pitch yx: {pyx:.3f} µm/px")
    logger.info(f"Camera pitch yy: {pyy:.3f} µm/px")

    # Store layer results
    logger.info("Store layer results...")
    dc = layer.container()
    dc.write(f"{subpath}/layer.zdc")
    result = dc["meas/result.json"]

    # Initialize grid object
    logger.info("Initialize grid object...")
    grid = Grid(system, logger, **args)
    
    # Grid center coordinates
    x = system.x0
    y = system.y0
    zlo = result["zLower"]
    zup = result["zUpper"]
    z = 0.5 * (zlo + zup)

    # Get pre-exposure hologram    
    logger.info("Get pre-exposure hologram...")
    delay = system["delay"]
    xh, yh, zh = system.stage_pos([x, y, z], [0, 0])
    system.moveabs(x=xh, y=yh, z=zh+off, wait=delay)
    dc = system.dhm.container(opt=True)
    fn = f"{path}/pre_holo.zdc"
    dc.write(fn)
    logger.info(f"Hologram container: {fn}")

    # Run grid exposure
    logger.info("Expose grid...")
    grid.run(x, y, z, nx, ny)
    print(system.transform.P)

    # Get post-exposure hologram    
    logger.info("Get post-exposure hologram...")
    delay = system["delay"]
    xh, yh, zh = system.stage_pos([x, y, z], [0, 0])
    system.moveabs(x=xh, y=yh, z=zh+off, wait=delay)
    dc = system.dhm.container(opt=True)
    fn = f"{path}/post_holo.zdc"
    dc.write(fn)
    logger.info(f"Hologram container: {fn}")
    
    # Store grid results
    logger.info("Store grid results...")
    dc = grid.container()
    dc.write(f"{path}/grid.zdc")
    print(dc)

    logger.info("Done.")
