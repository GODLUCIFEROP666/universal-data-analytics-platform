"""Functional test for the hardened analysis engine."""
import sys
import datetime

sys.path.insert(0, ".")

import pandas as pd

# ── Simulate what openpyxl returns for a billing Excel ──────────────────────
# Date column has a mix of Python datetime objects + stray strings + None
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

# Inject a stray string and None into Date column (the original crash scenario)
rows[5]["Date"] = "Not a date"
rows[15]["Date"] = None

df = pd.DataFrame(rows)
print("Input dtypes:", dict(df.dtypes))
print("Date sample:", df["Date"].head(10).tolist())

# ── Test file_parser normalization ───────────────────────────────────────────
from app.analyzer.file_parser import _safe_parse_dates

normalized_date = _safe_parse_dates(df["Date"])
print("Normalized date dtype:", normalized_date.dtype)
print("Normalized date NaT count:", normalized_date.isna().sum())

# ── Test type detection ───────────────────────────────────────────────────────
from app.analyzer.type_detector import detect_column_types

types = detect_column_types(df)
for col, info in types.items():
    print(
        f"  {col}: {info['detected_type']} | numeric={info['is_numeric']}"
        f" | date={info['is_date']} | cat={info['is_categorical']}"
    )

# ── Test stats engine ─────────────────────────────────────────────────────────
from app.analyzer.stats_engine import analyze_dataset

stats = analyze_dataset(df)
print("Stats summary:", stats["summary"])
print("Stats warnings:", stats.get("warnings", []))

# ── Test chart recommender ────────────────────────────────────────────────────
from app.analyzer.chart_recommender import recommend_charts_with_warnings

charts, chart_warnings = recommend_charts_with_warnings(
    df, stats["columns"], stats["correlations"]
)
print(f"\nCharts generated: {len(charts)}")
for c in charts:
    print(f"  [{c['type']}] {c['title']}")
print("Chart warnings:", chart_warnings)

print()
if len(charts) > 0:
    print("ALL TESTS PASSED - Charts generated successfully!")
else:
    print("NO CHARTS GENERATED - check logic")
    sys.exit(1)
