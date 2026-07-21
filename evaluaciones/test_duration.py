"""Property-tests congelados para parse_duration. Oráculo independiente: no reutiliza la lógica del target."""
import random
import re
import unittest

from duration import parse_duration


def oracle(h, m, s):
    return h * 3600 + m * 60 + s


class TestParseDuration(unittest.TestCase):
    def test_hours_only(self):
        self.assertEqual(parse_duration("1h"), 3600)

    def test_seconds_only(self):
        self.assertEqual(parse_duration("90s"), 90)

    def test_minutes_only(self):
        self.assertEqual(parse_duration("45m"), 2700)

    def test_full_combo(self):
        self.assertEqual(parse_duration("2h15m30s"), 8130)

    def test_zero(self):
        self.assertEqual(parse_duration("0s"), 0)

    def test_partial_combo(self):
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration("10m5s"), 605)

    def test_property_random_compositions(self):
        rng = random.Random(1234)
        for _ in range(200):
            h = rng.randint(0, 99)
            m = rng.randint(0, 59)
            s = rng.randint(0, 59)
            text = f"{h}h{m}m{s}s"
            self.assertEqual(parse_duration(text), oracle(h, m, s), text)

    def test_invalid_empty_raises(self):
        with self.assertRaises(ValueError):
            parse_duration("")

    def test_invalid_garbage_raises(self):
        with self.assertRaises(ValueError):
            parse_duration("abc")

    def test_invalid_unit_before_number_raises(self):
        with self.assertRaises(ValueError):
            parse_duration("h1")

    def test_invalid_wrong_order_raises(self):
        with self.assertRaises(ValueError):
            parse_duration("30s2h")

    def test_invalid_duplicate_unit_raises(self):
        with self.assertRaises(ValueError):
            parse_duration("1h2h")

    def test_returns_int(self):
        self.assertIsInstance(parse_duration("1h1m1s"), int)


if __name__ == "__main__":
    unittest.main()
