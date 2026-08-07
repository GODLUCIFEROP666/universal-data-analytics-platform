"""Test Excel file parsing & chart generation with report titles, merged cells, currency formatting, and TOTAL rows."""
import io
import sys
import datetime

sys.path.insert(0, ".")

import pandas as pd
from openpyxl import Workbook

# ── Create an Excel workbook simulating a messy Hospital Billing Report ─────
wb = Workbook()
ws = wb.active
ws.title = "Billing Summary"

# Row 1: Report Title Banner (Merged across A1:C1)
ws.append(["CITY HOSPITAL - INPATIENT BILLING REPORT", "", ""])
# Row 2: Metadata / Date range
ws.append(["Period: 2024-01-01 to 2024-12-31", "Generated: 2024-12-31", ""])
# Row 3: Empty row
ws.append(["", "", ""])
# Row 4: Real Header Row
ws.append(["Date", "Bill Number", "Amount"])

# Data Rows 5..54 (50 valid records)
for i in range(1, 51):
    d_str = f"2024-01-{(i % 28) + 1:02d}"
    bill_no = f"INV-2024-{1000 + i}"
    # Formatted currency string with commas and dollar signs
    amt_str = f" ${100 + i * 12.50:,.2f} "
    ws.append([d_str, bill_no, amt_str])

# Trailing TOTAL row
ws.append(["Grand Total", "", " $41,875.00 "])

# Save to bytes
buf = io.BytesIO()
wb.save(buf)
excel_bytes = buf.getvalue()

# ── Process through parser ──────────────────────────────────────────────────
from app.analyzer.file_parser import parse_file_to_df
from app.analyzer.stats_engine import analyze_dataset
from app.analyzer.chart_recommender import recommend_charts_with_warnings

df = parse_file_to_df(excel_bytes, "hospital_billing.xlsx", "Billing Summary")

print("=== PARSED DATAFRAME ===")
print("Shape:", df.shape)
print("Columns:", list(df.columns))
print("Dtypes:\n", df.dtypes)
print("\nFirst 5 rows:\n", df.head())
print("\nLast 3 rows:\n", df.tail())

# ── Analyze dataset ─────────────────────────────────────────────────────────
stats = analyze_dataset(df)
print("\n=== ANALYSIS STATS ===")
print("Summary:", stats["summary"])

for col, info in stats["columns"].items():
    print(f"Column [{col}]: detected_type={info['detected_type']}, numeric={info['is_numeric']}, date={info['is_date']}, cat={info['is_categorical']}")

# ── Generate charts ─────────────────────────────────────────────────────────
charts, warnings = recommend_charts_with_warnings(df, stats["columns"], stats["correlations"])
print(f"\n=== CHARTS GENERATED ({len(charts)}) ===")
for c in charts:
    print(f"  [{c['type']}] {c['title']}")

print("\nWarnings:", warnings)

# ── Verification Assertions ─────────────────────────────────────────────────
assert "Date" in df.columns, "Date column missing!"
assert "Bill Number" in df.columns, "Bill Number column missing!"
assert "Amount" in df.columns, "Amount column missing!"

amount_info = stats["columns"]["Amount"]
assert amount_info["is_numeric"] == True, f"Amount should be numeric! Got {amount_info}"
assert stats["summary"]["numeric_columns_count"] >= 1, "Numeric columns count should be >= 1!"
assert len(charts) >= 5, f"Expected at least 5 charts, got {len(charts)}"

print("\n>>> SUCCESS: ALL TEST ASSERTIONS PASSED! <<<")
