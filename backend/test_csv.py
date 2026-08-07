"""Test with the actual sales CSV sample."""
import sys
sys.path.insert(0, ".")

from app.analyzer.file_parser import parse_file_to_df
from app.analyzer.stats_engine import analyze_dataset
from app.analyzer.chart_recommender import recommend_charts_with_warnings

with open("samples/sales_data.csv", "rb") as f:
    data = f.read()

df = parse_file_to_df(data, "sales_data.csv")
print("Parsed shape:", df.shape)
print("Columns:", list(df.columns))

stats = analyze_dataset(df)
print("Summary:", stats["summary"])
print("Warnings:", stats.get("warnings", []))

charts, warnings = recommend_charts_with_warnings(df, stats["columns"], stats["correlations"])
print(f"\nCharts: {len(charts)}")
for c in charts:
    print(f"  [{c['type']}] {c['title']}")
print("Chart warnings:", warnings)
print("\nPASSED" if charts else "NO CHARTS")
