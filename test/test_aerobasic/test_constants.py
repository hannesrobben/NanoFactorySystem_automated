from unittest import TestCase

from nanofactorysystem.aerobasic.constants import Axis, Stages, SingleAxis, AxisError


class TestConstants(TestCase):
    def test_str_parsing_normal(self):
        x = Axis("X")
        y = Axis("Y")
        self.assertNotEqual(x, y)

        xy = Axis("XY")
        yx = Axis("YX")
        xy_gt = Axis.XY

        self.assertEqual(xy, xy_gt)
        self.assertEqual(yx, xy_gt)
        self.assertEqual(xy, yx)

    def test_str_parsing_lower_case(self):
        x = Axis("x")
        y = Axis("y")
        self.assertNotEqual(x, y)

        xy = Axis("xY")
        yx = Axis("yX")
        yx_2 = Axis("yx")

        xy_gt = Axis.XY

        self.assertEqual(xy, xy_gt)
        self.assertEqual(yx, xy_gt)
        self.assertEqual(yx_2, xy_gt)
        self.assertEqual(xy, yx)

    def test_str_parsing_invalid(self):
        self.assertRaises(AxisError, lambda: Axis("Invalid"))
        self.assertRaises(AxisError, lambda: Axis(""))
        self.assertRaises(AxisError, lambda: Axis(" "))

    def test_axis_parsing_invalid_value(self):
        # Combinations of defined axes are valid (28 = Z | A | B) ...
        self.assertEqual(SingleAxis(28), SingleAxis.Z | SingleAxis.A | SingleAxis.B)
        # ... values with undefined bits are not (Flag boundary STRICT since Python 3.11)
        self.assertRaises(ValueError, lambda: SingleAxis(124))
        self.assertRaises(ValueError, lambda: SingleAxis(252))

    def test_iterable(self):
        x = SingleAxis.X
        y = SingleAxis.Y
        xy = Axis.XY

        for i, axis in enumerate(xy):
            if i == 0:
                self.assertEqual(axis, x)
            elif i == 1:
                self.assertEqual(axis, y)
            else:
                raise RuntimeError("Test shouldn't reach this case")

        for i, axis in enumerate(x):
            if i == 0:
                self.assertEqual(axis, SingleAxis.X)
            else:
                raise RuntimeError("Test shouldn't reach this case")

    def test_simple(self):
        print(SingleAxis.X)  # Output: SingleAxis.X
        print(Axis.X)  # Output: Axis.X
        print(Axis.X | Axis.Y)  # Output: Axis.XY
        print(Axis.XYZ)  # Output: Axis.XYZ

        self.assertEqual(SingleAxis.X, Axis.X)

        self.assertTrue(SingleAxis.X in Stages.XYZ)
        self.assertTrue(Axis.XY in Stages.XYZ)
        self.assertTrue(Axis.XYZ in Stages.XYZ)
        self.assertTrue(Axis.XY not in Stages.AB)

    def test_instantiation(self):
        self.assertEqual(SingleAxis.X, Axis("X"))
        self.assertEqual(Axis.Y, Axis("Y"))
        self.assertEqual(Axis.Z, Axis(SingleAxis.Z))
        self.assertEqual(SingleAxis.A, Axis(Axis.A))
        self.assertEqual(Axis.XY, Axis("XY"))

    def test_values(self):
        # Axis lists are space-separated in AeroBasic commands, e.g. "ENABLE X Y"
        self.assertEqual("X Y", Axis.XY.parameter_name)

    def test_axis_combinations(self):
        # Maintainer decision (T23): mixing stages is allowed, e.g. Aerotech3200.home() homes Y Z A B at once
        x = SingleAxis.X
        y = SingleAxis.Y
        b = SingleAxis.B

        xy = x | y

        # Mixing axes of different stages is allowed
        self.assertEqual("X Y B", (xy | b).parameter_name)
        self.assertEqual("X B", (x | b).parameter_name)

        # Common axes with '&'
        self.assertEqual(x, xy & x)

        # Inverting axis should never work
        self.assertRaises(AxisError, lambda: ~x)

        # XOR axis is also not valid
        self.assertRaises(AxisError, lambda: x ^ y)
        self.assertRaises(AxisError, lambda: xy ^ y)

        # Empty axis with '&'
        self.assertRaises(AxisError, lambda: x & y)

    def test_single_axis(self):
        x = SingleAxis.X
        y = SingleAxis.Y
        z = SingleAxis.Z

        xy = x | y
        xz = x | z

        ab = Stages.AB

        # Test Single axes
        self.assertTrue(x.is_single_axis())
        self.assertTrue(y.is_single_axis())
        self.assertTrue(z.is_single_axis())

        # Test Multi axes
        self.assertFalse(xy.is_single_axis())
        self.assertFalse(xz.is_single_axis())
        self.assertFalse(ab.is_single_axis())
