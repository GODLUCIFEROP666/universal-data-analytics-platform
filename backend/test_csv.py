"""Unit test for actual sales CSV sample parsing & recommendation."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from app.analyzer.file_parser import parse_file_to_df
from app.analyzer.stats_engine import analyze_dataset
from app.analyzer.chart_recommender import recommend_charts_with_warnings


class TestCSVSample(unittest.TestCase):

    def test_sales_csv_analysis(self):
        sample_path = os.path.join(os.path.dirname(__file__), "samples", "sales_data.csv")
        self.assertTrue(os.path.exists(sample_path), f"Sample file not found at {sample_path}")
        with open(sample_path, "rb") as f:
            data = f.read()

        df = parse_file_to_df(data, "sales_data.csv")
        self.assertGreater(df.shape[0], 0)

        stats = analyze_dataset(df)
        self.assertIn("summary", stats)

        charts, warnings = recommend_charts_with_warnings(df, stats["columns"], stats["correlations"])
        self.assertGreater(len(charts), 0)


if __name__ == "__main__":
    unittest.main()
