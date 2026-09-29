from nanofactorysystem.aerobasic import VelocityMode
from nanofactorysystem.aerobasic.constants.tasks import ProgrammingMode
from nanofactorysystem.aerobasic.programs import AeroBasicProgram


class DefaultSetup(AeroBasicProgram):
    def __init__(
            self,
            programming_mode: ProgrammingMode = ProgrammingMode.ABSOLUTE,
            velocity_mode: VelocityMode = VelocityMode.ON,
    ):
        super().__init__()
        self.send("PRIMARY")
        self.send("SECONDS")
        self.send(programming_mode.value)  # ABSOLUTE vs INCREMENTAL
        self.VELOCITY(velocity_mode)
        self.send("IFOV OFF")


class SetupIFOV(AeroBasicProgram):
    def __init__(
            self,
            objective,
            time=200,
            tracking_speed=7.5, # 5 or 10 -- mm/s, # 5000, # 10000,# max =100*self.ifov_size
            tracking_acceleration=600,  # 20000, # not higher than 1000 - better 600 for good results - mm/s²
            velocity_mode: VelocityMode = VelocityMode.ON,
    ):
        super().__init__()
        if objective=="Zeiss 20x":
            self.ifov_size = 0.500/2  # half FOV -CHANGE 0.5
        if objective=="Zeiss 63x":
            self.ifov_size = 0.150/2  # half FOV - CHANGE 0.15
        self.ifov_time = time
        self.ifov_tracking_speed = tracking_speed  # max =100*self.ifov_size
        self.ifov_tracking_acceleration = tracking_acceleration

        self.send("SECONDS")
        self.send("ABSOLUTE")  # ABSOLUTE has to be set for IFOV
        self.VELOCITY(velocity_mode)
        self.send("WAIT MODE AUTO")
        self.send("GALVO LASEROVERRIDE A AUTO")

        # Synchronize axes
        self.comment("\nSynchronize axes")
        self.send("IFOV AXISPAIR 0, A, X")
        self.send("IFOV AXISPAIR 1, B, Y")

        # IFOV Settings
        self.comment("\nIFOV Settings")
        self.send("IFOV OFF")
        self.send(f"IFOV TIME {self.ifov_time:f}")
        self.send(f"IFOV SIZE {self.ifov_size:f}")
        self.send(f"IFOV TRACKINGSPEED {tracking_speed:f}")
        self.send(f"IFOV TRACKINGACCEL {tracking_acceleration:f}")

        # Compensation of tilted GALVO Axis
        self.send("GALVO ROTATION A -0.6")
        # self.send("GALVO ROTATION B -1.1")
        #
        # # Has to be done in the IFOV program
        # power_not_in_mW=2.4
        # self.send(f"$A[0].A = {power_not_in_mW}")
        # # Set the speed in the program itself, because it depends on the structure
        # speed = 10
        # self.send(f"F {speed}")
        # self.send("RAPID A0 B0")
        # # move to the right position
        # self.send("RAPID X0 Y0")  # change
        # self.send("IFOV ON")


class SetupIFOV_OLD(AeroBasicProgram):
    def __init__(
            self,
            objective,
            size=0.5,
            time=10,
            tracking_speed=500,
            tracking_acceleration=500
    ):
        super().__init__()

        self.ifov_size = size
        self.ifov_time = time
        self.ifov_tracking_speed = tracking_speed
        self.ifov_tracking_acceleration = tracking_acceleration

        # Turn off IFOV until setup is completed
        self.comment("\nTurn off IFOV until setup is completed")
        self.send("IFOV OFF")

        # Set Galvo Delays and mode
        self.comment("\nSet Galvo Delays and mode")
        self.send("GALVO LASERONDELAY A 0")
        self.send("GALVO LASEROFFDELAY A 0")
        self.send("GALVO LASERMODE A 0")

        # Synchronize axes
        self.comment("\nSynchronize axes")
        self.send("IFOV AXISPAIR 0, A, X")
        self.send("IFOV AXISPAIR 1, B, Y")
        self.send("ENCODER OUT X ON 0,0")
        self.send("ENCODER OUT Y ON 0,0")
        self.send("IFOV SYNCAXES Z")

        # IFOV Settings
        self.comment("\nIFOV Settings")
        self.send(f"IFOV SIZE {size:f}")
        self.send(f"IFOV TIME {time:f}")
        self.send(f"IFOV TRACKINGSPEED {tracking_speed:f}")
        self.send(f"IFOV TRACKINGACCEL {tracking_acceleration:f}")

        # Turn on IFOV
        self.comment("\nTurn on IFOV")
        self.send("IFOV ON")
