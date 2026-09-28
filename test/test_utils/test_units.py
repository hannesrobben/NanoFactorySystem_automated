from unittest import TestCase

import numpy as np

from nanofactorysystem.devices.coordinate_system import Unit


class UnitFloat:
    def __init__(self, value, unit: Unit = Unit.mm):
        self.value = value
        self.unit = unit

    def __float__(self) -> float:
        return self.value * self.unit.value

    def __str__(self) -> str:
        return f"{self.value}{self.unit.name}"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.value}, {self.unit})"

    def __add__(self, other: "UnitFloat") -> "UnitFloat":
        if not isinstance(other, UnitFloat):
            raise TypeError(
                f"{self.__class__.__name__} cannot be added with {type(other)}. "
                f"Needs another {self.__class__.__name__}"
            )

        if self.unit == other.unit:
            return UnitFloat(self.value + other.value, unit=self.unit)
        return UnitFloat(float(self) + float(other), unit=Unit.mm)

    def __mul__(self, other: int | float) -> "UnitFloat":
        if not isinstance(other, (int, float)):
            raise TypeError(f"{self.__class__.__name__} can only be multiplied with float or int.")

        return UnitFloat(self.value * other, unit=self.unit)

    def __rmul__(self, other) -> "UnitFloat":
        return self.__mul__(other)

    def __eq__(self, other):
        return float(self) == float(other)

    def to(self, unit: Unit) -> "UnitFloat":
        if unit == self.unit:
            return UnitFloat(self.value, unit=unit)
        return UnitFloat(float(self) / unit.value, unit=unit)

    def to_um(self) -> "UnitFloat":
        return self.to(Unit.um)

    def to_cm(self) -> "UnitFloat":
        return self.to(Unit.cm)

    def to_nm(self) -> "UnitFloat":
        return self.to(Unit.nm)


class TestUnits(TestCase):
    def assertIsUnitFloat(self, b):
        assert isinstance(b, UnitFloat)
        assert isinstance(b.value, float)
        assert isinstance(b.unit, Unit)

    def test_float_behaviour(self):
        a = UnitFloat(2.54, Unit.um)
        b = UnitFloat(1.23, Unit.um)
        c = a + b
        self.assertIsUnitFloat(a)
        self.assertIsUnitFloat(b)
        self.assertIsUnitFloat(c)

        self.assertEqual(Unit.um, c.unit)
        self.assertEqual(3.77, c.value)
        self.assertEqual(0.00377, c)

        # Other unit
        d = UnitFloat(1.23, Unit.mm)
        e = a + d
        self.assertIsUnitFloat(d)
        self.assertIsUnitFloat(e)
        self.assertEqual(Unit.mm, e.unit)
        self.assertEqual(1.23254, e.value)
        self.assertEqual(1.23254, e)

    def test_to_unit(self):
        a = UnitFloat(573.123, unit=Unit.um)
        self.assertAlmostEqual(float(a), 0.573123)

        for value, unit in [
            (0.0573123, Unit.cm),  # 1 cm = 10 mm
            (0.573123, Unit.mm),
            (573.123, Unit.um),
            (573123, Unit.nm),
        ]:
            b = a.to(unit)
            self.assertIsUnitFloat(b)
            self.assertAlmostEqual(value, b.value)
            self.assertEqual(unit, b.unit)
            self.assertAlmostEqual(float(b), 0.573123)

    def test_multiplication(self):
        a = UnitFloat(2.3, unit=Unit.um)
        b = a * 3
        self.assertIsUnitFloat(a)
        self.assertIsUnitFloat(b)
        self.assertAlmostEqual(b.value, 6.9)
        self.assertEqual(b.unit, Unit.um)

        c = 4 * a
        self.assertIsUnitFloat(c)
        self.assertAlmostEqual(c.value, 9.2)
        self.assertEqual(c.unit, Unit.um)

    def test_numpy(self):
        a = [UnitFloat(3.2, unit=Unit.mm), UnitFloat(5.2, unit=Unit.um)]
        a_np = np.asarray(a)
        print(a_np)


        # Multiplication
        b_np = a_np * 2
        self.assertIsUnitFloat(b_np[0])
        self.assertIsUnitFloat(b_np[1])
        self.assertAlmostEqual(6.4, b_np[0].value)
        self.assertAlmostEqual(10.4, b_np[1].value)
        self.assertAlmostEqual(Unit.um, b_np[1].unit)

        # Addition
        c_np = a_np + UnitFloat(123, Unit.um)
        self.assertAlmostEqual(3.323, c_np[0].value)
        self.assertAlmostEqual(128.2, c_np[1].value)
        self.assertEqual(Unit.mm, c_np[0].unit)
        self.assertEqual(Unit.um, c_np[1].unit)

        self.assertRaises(TypeError, lambda: c_np * a_np)

        # As float
        a = [UnitFloat(3.2, unit=Unit.mm), UnitFloat(5.2, unit=Unit.um)]
        a_np = np.asarray(a)
        d_np = a_np.astype(float)
        print(d_np)
        self.assertAlmostEqual(3.2, d_np[0])
        self.assertAlmostEqual(0.0052, d_np[1])
