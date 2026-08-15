"""Unit test for analysis engine logic."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from app.analyzer.file_parser import _safe_parse_dates
from app.analyzer.type_detector import detect_column_types
from app.analyzer.stats_engine import analyze_dataset
from app.analyzer.chart_recommender import recommend_charts_with_warnings


class TestAnalysisEngine(unittest.TestCase):

    def test_engine_workflow(self):
        rows = []
        for i in range(1, 51):
            date_val = datetime.datetime(2024, 1, (i % 28) + 1, 0, 0, 0)
            rows.append(
                {
                    "Date": date_val,
                    "Bill Number": f"BILL-{1000 + i}",
                    "Amount": float(100 + i * 7.5),
                    "Category": ["Lab", "OPD", "Pharmacy", "ICU"][i % 4],
                }
            )

        rows[5]["Date"] = "Not a date"
        rows[15]["Date"] = None

        df = pd.DataFrame(rows)
        normalized_date = _safe_parse_dates(df["Date"])
        self.assertEqual(normalized_date.isna().sum(), 2)

        types = detect_column_types(df)
        self.assertIn("Date", types)
        self.assertIn("Bill Number", types)
        self.assertIn("Amount", types)

        stats = analyze_dataset(df)
        self.assertEqual(stats["summary"]["total_rows"], 50)

        charts, chart_warnings = recommend_charts_with_warnings(
            df, stats["columns"], stats["correlations"]
        )
        self.assertGreater(len(charts), 0)


if __name__ == "__main__":
    unittest.main()
