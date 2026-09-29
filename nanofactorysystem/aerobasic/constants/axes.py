import enum
from enum import auto, Flag
from typing import Iterator

from nanofactorysystem.aerobasic.constants import DataItemEnum


class AxisError(Exception):
    pass


class SingleAxis(Flag):
    _NO_AXIS = 0

    # Stages 1
    X = auto()
    Y = auto()
    Z = auto()

    # Stages 2
    A = auto()
    B = auto()

    def __iter__(self) -> Iterator["SingleAxis"]:
        for axis in SingleAxis.__members__.values():
            if axis.value == 0:
                continue
            if axis in self:
                yield axis

    # Axis combinations: "|" may combine any axes, also of different stages
    # (e.g. Axis.YZ | Axis.AB in Aerotech3200.home()). Operations that would
    # produce axes that were not asked for, or none at all, are errors.

    def __invert__(self):
        raise AxisError(f"Inverting axes is not supported ({self!r})")

    def __xor__(self, other):
        raise AxisError(f"XOR of axes is not supported ({self!r} ^ {other!r})")

    __rxor__ = __xor__

    def __and__(self, other):
        result = super().__and__(other)
        if isinstance(result, SingleAxis) and result.value == 0:
            raise AxisError(f"{self!r} & {other!r} has no common axis")
        return result

    __rand__ = __and__

    @enum.property
    def parameter_name(self) -> str:
        return " ".join(map(lambda x: x.name, self))

    def is_from_same_stage(self) -> bool:
        return any(self in axis for axis in [Stages.all()])

    def is_single_axis(self) -> bool:
        return self is not SingleAxis._NO_AXIS and self in SingleAxis.__members__.values()


class Axis:
    # Stages 1
    X = SingleAxis.X
    Y = SingleAxis.Y
    Z = SingleAxis.Z
    XY = SingleAxis.X | SingleAxis.Y
    YZ = SingleAxis.Y | SingleAxis.Z
    XZ = SingleAxis.X | SingleAxis.Z
    XYZ = SingleAxis.X | SingleAxis.Y | SingleAxis.Z

    # Stages 2
    A = SingleAxis.A
    B = SingleAxis.B
    AB = SingleAxis.A | SingleAxis.B

    def __new__(cls, name):
        if isinstance(name, SingleAxis):
            return name
        if not isinstance(name, str):
            raise TypeError(f"Needs to be SingleAxis or string for instantiation. Got type {type(name)}: {name}")
        if name == "":
            raise AxisError("Cannot instantiate an empty axis!")

        axis = SingleAxis._NO_AXIS
        for axis_name in name.upper():
            try:
                axis |= SingleAxis.__members__[axis_name]
            except KeyError:
                raise AxisError(f"Could not identify Axis with name {axis_name}")

        return axis


class Stages:
    XYZ = SingleAxis.X | SingleAxis.Y | SingleAxis.Z
    AB = SingleAxis.A | SingleAxis.B

    def __new__(cls, name):
        if isinstance(name, SingleAxis):
            axis = name
        elif isinstance(name, str):
            axis = SingleAxis._NO_AXIS
            for axis_name in name:
                axis |= SingleAxis.__members__[axis_name]
        else:
            raise TypeError(f"Needs to be SingleAxis or string for instantiation. Got type {type(name)}: {name}")

        if axis in Stages.XYZ:
            return Stages.XYZ
        if axis in Stages.AB:
            return Stages.AB

        raise RuntimeError(f"Stage not found for axis {axis} (derived from {name})")

    @classmethod
    def all(cls):
        return [Stages.XYZ, Stages.AB]


class AxisStatusDataItem(DataItemEnum):
    AccelerationCommand = auto()
    AccelerationCommandRaw = auto()
    AccelerationError = auto()
    AccelerationFeedback = auto()
    AccelerationMode = auto()
    AccelerationRate = auto()
    AccelerationTime = auto()
    AccelerationType = auto()
    AccuracyCorrectionEndingPosition = auto()
    AccuracyCorrectionStartingPosition = auto()
    AnalogInput0 = auto()
    AnalogInput1 = auto()
    AnalogInput2 = auto()
    AnalogInput3 = auto()
    AnalogOutput0 = auto()
    AnalogOutput1 = auto()
    AnalogOutput2 = auto()
    AnalogOutput3 = auto()
    AxisFault = auto()
    AxisParameter = auto()
    AxisStatus = auto()
    Backlash = auto()
    CommunicationRealTimeErrors = auto()
    CoordinatedDistanceRemaining = auto()
    CoordinatedPositionTarget = auto()
    CurrentCommand = auto()
    CurrentError = auto()
    CurrentFeedback = auto()
    CurrentFeedbackAverage = auto()
    DecelerationMode = auto()
    DecelerationRate = auto()
    DecelerationTime = auto()
    DecelerationType = auto()
    DigitalInput = auto()
    DigitalOutput = auto()
    DistanceLog = auto()
    DriveStatus = auto()
    FixtureOffset = auto()
    GalvoLaserOffDelay = auto()
    GalvoLaserOnDelay = auto()
    GalvoLaserOutputRaw = auto()
    JerkCommandRaw = auto()
    PeakCurrent = auto()
    PiezoVoltageCommand = auto()
    PiezoVoltageFeedback = auto()
    PositionCalibration2D = auto()
    PositionCalibrationAll = auto()
    PositionCommand = auto()
    PositionCommandRaw = auto()
    PositionCommandRollover = auto()
    PositionError = auto()
    PositionFeedback = auto()
    PositionFeedbackAuxiliary = auto()
    PositionFeedbackAuxiliaryRollover = auto()
    PositionFeedbackRollover = auto()
    PositionOffset = auto()
    ProgramPosition = auto()
    ProgramPositionCommand = auto()
    ProgramPositionFeedback = auto()
    ProgramVelocityCommand = auto()
    ProgramVelocityFeedback = auto()
    SpeedTarget = auto()
    SpeedTargetActual = auto()
    Stability0SettleTime = auto()
    Stability1SettleTime = auto()
    STOStatus = auto()
    TotalMoveTime = auto()
    VelocityCommand = auto()
    VelocityCommandRaw = auto()
    VelocityError = auto()
    VelocityFeedback = auto()
    VelocityFeedbackAverage = auto()


class AxisStatus(Flag):
    Homed = 0x00000001
    Profiling = 0x00000002
    WaitDone = 0x00000004
    CommandValid = 0x00000008
    Homing = 0x00000010
    Enabling = 0x00000020
    JogGenerating = 0x00000080
    Jogging = 0x00000100
    DrivePending = 0x00000200
    DriveAbortPending = 0x00000400
    TrajectoryFiltering = 0x00000800
    IFOVEnabled = 0x00001000
    NotVirtual = 0x00002000
    CalEnabled1D = 0x00004000
    CalEnabled2D = 0x00008000
    MasterSlaveControl = 0x00010000
    JoystickControl = 0x00020000
    BacklashActive = 0x00040000
    GainMappingEnabled = 0x00080000
    Stability0 = 0x00100000
    MotionBlocked = 0x00200000
    MoveDone = 0x00400000
    MotionClamped = 0x00800000
    GantryAligned = 0x01000000
    GantryRealigning = 0x02000000
    Stability1 = 0x04000000
    ThermoCompEnabled = 0x08000000


class DriveStatusFlags(Flag):
    Enabled = 0x00000001
    CwEOTLimit = 0x00000002
    CcwEOTLimit = 0x00000004
    HomeLimit = 0x00000008
    MarkerInput = 0x00000010
    HallAInput = 0x00000020
    HallBInput = 0x00000040
    HallCInput = 0x00000080
    SineEncoderError = 0x00000100
    CosineEncoderError = 0x00000200
    ESTOPInput = 0x00000400
    BrakeOutput = 0x00000800
    GalvoPowerCorrection = 0x00001000
    NoMotorSupply = 0x00004000
    CurrentClamp = 0x00008000
    MarkerLatch = 0x00010000
    PowerLimiting = 0x00020000
    PSOHaltLatch = 0x00040000
    HighResMode = 0x00080000
    GalvoCalEnabled = 0x00100000
    AutofocusActive = 0x00200000
    ProgramFlash = 0x00400000
    ProgramMXH = 0x00800000
    ServoControl = 0x01000000
    InPosition = 0x02000000
    MoveActive = 0x04000000
    AccelPhase = 0x08000000
    DecelPhase = 0x10000000
    EncoderClipping = 0x20000000
    DualLoopActive = 0x40000000
    InPosition2 = 0x80000000


class AxisFault(Flag):
    PositionError = 0x00000001
    OverCurrent = 0x00000002
    CwEOTLimit = 0x00000004
    CcwEOTLimit = 0x00000008
    CwSoftLimit = 0x00000010
    CcwSoftLimit = 0x00000020
    AmplifierFault = 0x00000040
    PositionFbk = 0x00000080
    VelocityFbk = 0x00000100
    HallFault = 0x00000200
    MaxVelocity = 0x00000400
    EstopFault = 0x00000800
    VelocityError = 0x00001000
    ProbeFault = 0x00004000
    ExternalFault = 0x00008000
    MotorTemp = 0x00020000
    AmplifierTemp = 0x00040000
    EncoderFault = 0x00080000
    CommLost = 0x00100000
    GantryMisalign = 0x00400000
    FbkScalingFault = 0x00800000
    MrkSearchFault = 0x01000000
    SafeZoneFault = 0x02000000
    InPosTimeout = 0x04000000
    VoltageClamp = 0x08000000
    PowerSupply = 0x10000000
    MissedInterrupt = 0x20000000
    Internal = 0x40000000

