
import unittest

from src.calculate_relative_value import (
    calculate_metrics,
    historical_stats,
    extract_curve,
)


class TestRelativeValue(unittest.TestCase):

    def setUp(self):
        self.curve = {
            2: 4.00,
            5: 4.50,
            10: 5.00,
            20: 5.40,
            30: 5.60,
        }

    def test_spreads(self):
        result = calculate_metrics(self.curve)
        self.assertAlmostEqual(result["2s10s"], 100)
        self.assertAlmostEqual(result["5s30s"], 110)
        self.assertAlmostEqual(result["10s30s"], 60)

    def test_butterflies(self):
        result = calculate_metrics(self.curve)
        self.assertAlmostEqual(result["2s5s10s"], 12.5)
        self.assertAlmostEqual(result["5s10s30s"], 4.0)
        self.assertAlmostEqual(result["10s20s30s"], 10.0)

    def test_missing_tenor(self):
        result = calculate_metrics({2: 4.0, 10: 5.0})
        self.assertNotIn("5s30s", result)

    def test_insufficient_history(self):
        stats = historical_stats(50, [40] * 10)
        self.assertIsNone(stats["20"])

    def test_zero_volatility(self):
        stats = historical_stats(50, [40] * 252)
        self.assertIsNone(stats["252"]["z_score"])

    def test_curve_extraction(self):
        record = {
            "curve": [
                {"tenor": "2Y", "yield": 4.2},
                {"tenor": "10Y", "yield": 5.2},
            ]
        }
        curve = extract_curve(record)
        self.assertEqual(curve[2], 4.2)
        self.assertEqual(curve[10], 5.2)


if __name__ == "__main__":
    unittest.main()
