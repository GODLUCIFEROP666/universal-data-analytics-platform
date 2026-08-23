"""Unit test for Excel report parsing & chart generation."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from openpyxl import Workbook
from app.analyzer.file_parser import parse_file_to_df
from app.analyzer.stats_engine import analyze_dataset
from app.analyzer.chart_recommender import recommend_charts_with_warnings


class TestReportParsing(unittest.TestCase):

    def test_excel_report_parsing(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Billing Summary"

        ws.append(["CITY HOSPITAL - INPATIENT BILLING REPORT", "", ""])
        ws.append(["Period: 2024-01-01 to 2024-12-31", "Generated: 2024-12-31", ""])
        ws.append(["", "", ""])
        ws.append(["Date", "Bill Number", "Amount"])

        for i in range(1, 51):
            d_str = f"2024-01-{(i % 28) + 1:02d}"
            bill_no = f"INV-2024-{1000 + i}"
            amt_str = f" ${100 + i * 12.50:,.2f} "
            ws.append([d_str, bill_no, amt_str])

        ws.append(["Grand Total", "", " $41,875.00 "])

        buf = io.BytesIO()
        wb.save(buf)
        excel_bytes = buf.getvalue()

        df = parse_file_to_df(excel_bytes, "hospital_billing.xlsx", "Billing Summary")

        stats = analyze_dataset(df)
        charts, warnings = recommend_charts_with_warnings(df, stats["columns"], stats["correlations"])

        self.assertIn("Date", df.columns)
        self.assertIn("Bill Number", df.columns)
        self.assertIn("Amount", df.columns)
        self.assertTrue(stats["columns"]["Amount"]["is_numeric"])
        self.assertGreaterEqual(stats["summary"]["numeric_columns_count"], 1)
        self.assertGreaterEqual(len(charts), 5)


if __name__ == "__main__":
    unittest.main()
    
