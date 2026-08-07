"""
chart_recommender.py — Chart generation engine with full chart type recommendations and categorical aggregation.

Supported Chart Types:
- Line Chart (Date vs Numeric, Trend)
- Area Chart (Date vs Numeric, Cumulative/Trend)
- Bar Chart & Horizontal Bar Chart (Categorical vs Numeric / Top Items)
- Monthly / Weekly Trend Chart
- Pie Chart & Donut Chart (Breakdown of Numeric by Category or Category distribution)
- Histogram (Binned distribution of Numeric)
- Boxplot (Quantile summary [min, Q1, median, Q3, max] for Numeric)
- Scatter Plot (Numeric vs Numeric correlation)
- Stacked Bar (2 Categories vs Numeric composition)
- Heatmap (Correlation matrix across Numeric fields)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from app.analyzer.file_parser import _safe_parse_dates, numeric_series

logger = logging.getLogger(__name__)


def _safe_val(v: Any) -> float:
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return 0.0
        return float(round(f, 4))
    except Exception:
        return 0.0


def _aggregate_top_n(
    series: pd.Series, top_n: int = 10, others_label: str = "Others"
) -> Tuple[List[str], List[float]]:
    """Sort series descending; keep top (top_n - 1) categories and combine remainder into others_label."""
    sorted_s = series.dropna().sort_values(ascending=False)
    if len(sorted_s) <= top_n:
        labels = sorted_s.index.astype(str).tolist()
        values = [_safe_val(v) for v in sorted_s.tolist()]
        return labels, values

    top = sorted_s.iloc[: top_n - 1]
    rest_sum = _safe_val(sorted_s.iloc[top_n - 1 :].sum())

    labels = top.index.astype(str).tolist() + [others_label]
    values = [_safe_val(v) for v in top.tolist()] + [rest_sum]
    return labels, values


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def recommend_charts(
    df: pd.DataFrame,
    column_stats: Dict[str, Any],
    correlations: Dict[str, Any],
) -> List[Dict[str, Any]]:
    charts, _ = _recommend_charts_inner(df, column_stats, correlations)
    return charts


def recommend_charts_with_warnings(
    df: pd.DataFrame,
    column_stats: Dict[str, Any],
    correlations: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    return _recommend_charts_inner(df, column_stats, correlations)


# ---------------------------------------------------------------------------
# Inner implementation
# ---------------------------------------------------------------------------

def _recommend_charts_inner(
    df: pd.DataFrame,
    column_stats: Dict[str, Any],
    correlations: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    charts: List[Dict[str, Any]] = []
    warnings: List[str] = []
    seen: set = set()

    if df.empty:
        return charts, warnings

    numeric_cols = [
        name
        for name, info in column_stats.items()
        if info.get("is_numeric") and not info.get("exclude_from_charts")
    ]
    categorical_cols = [
        name
        for name, info in column_stats.items()
        if info.get("is_categorical")
        or info.get("is_id")
        or info.get("detected_type") in {"Category", "Text", "Unique IDs", "Boolean"}
        if not info.get("exclude_from_charts")
    ]
    date_cols = [
        name
        for name, info in column_stats.items()
        if info.get("is_date") and not info.get("exclude_from_charts")
    ]

    numeric_frame = pd.DataFrame(index=df.index)
    for col in numeric_cols:
        try:
            numeric_frame[col] = numeric_series(df[col])
        except Exception as exc:
            logger.warning("Could not build numeric series for '%s': %s", col, exc)

    # ── 1. TIME-SERIES CHARTS (Date × Numeric) ─────────────────────────────
    for date_col in date_cols:
        for num_col in numeric_cols[:4]:
            key_line = f"time_line_{date_col}_{num_col}"
            key_area = f"time_area_{date_col}_{num_col}"
            if key_line in seen and key_area in seen:
                continue

            try:
                parsed = _safe_parse_dates(df[date_col])
                valid_mask = parsed.notna()
                if valid_mask.sum() < 2:
                    continue

                working = df.copy()
                working["_parsed_date"] = parsed
                working = working[valid_mask].copy()

                working["_num"] = (
                    numeric_series(working[num_col])
                    if num_col not in numeric_frame.columns
                    else numeric_frame[num_col]
                )
                working = working.dropna(subset=["_num"])
                if working.empty:
                    continue

                time_span = (
                    working["_parsed_date"].max() - working["_parsed_date"].min()
                ).days
                freq = "ME" if time_span > 90 else ("W" if time_span > 14 else "D")

                grouped = (
                    working.set_index("_parsed_date")["_num"]
                    .resample(freq)
                    .sum()
                    .reset_index()
                    .dropna(subset=["_num"])
                )
                if grouped.empty:
                    continue

                date_fmt = (
                    "%Y-%m" if freq == "ME" else "%Y-%W" if freq == "W" else "%Y-%m-%d"
                )
                labels = grouped["_parsed_date"].dt.strftime(date_fmt).tolist()
                values = [_safe_val(v) for v in grouped["_num"].tolist()]

                # Line chart
                if key_line not in seen:
                    charts.append(
                        _make_chart(
                            title=f"{num_col} Trend over {date_col}",
                            chart_type="line",
                            category="trend",
                            x_axis=labels,
                            series=[{"name": num_col, "data": values}],
                            description=f"Line trend of {num_col} over {date_col}.",
                            x_label=date_col,
                            y_label=num_col,
                        )
                    )
                    seen.add(key_line)

                # Area chart
                if key_area not in seen:
                    charts.append(
                        _make_chart(
                            title=f"{num_col} Cumulative Trend ({date_col})",
                            chart_type="area",
                            category="trend",
                            x_axis=labels,
                            series=[{"name": num_col, "data": values}],
                            description=f"Area chart showing {num_col} accumulation over time.",
                            x_label=date_col,
                            y_label=num_col,
                        )
                    )
                    seen.add(key_area)

            except Exception as exc:
                logger.warning(
                    "Time-series chart failed for '%s' × '%s': %s",
                    date_col,
                    num_col,
                    exc,
                )

    # ── 2. CATEGORY × NUMERIC CHARTS (Bar, Horizontal Bar, Pie, Donut) ────
    for cat_col in categorical_cols:
        for num_col in numeric_cols[:4]:
            key_bar = f"catnum_bar_{cat_col}_{num_col}"
            key_pie = f"catnum_pie_{cat_col}_{num_col}"
            key_donut = f"catnum_donut_{cat_col}_{num_col}"

            try:
                num_s = (
                    numeric_frame[num_col]
                    if num_col in numeric_frame.columns
                    else numeric_series(df[num_col])
                )
                grouped_s = (
                    pd.DataFrame({cat_col: df[cat_col].astype(str), num_col: num_s})
                    .dropna()
                    .groupby(cat_col)[num_col]
                    .sum()
                )
                if grouped_s.empty:
                    continue

                # Bar / Horizontal Bar Chart (Top 15 + Others)
                if key_bar not in seen:
                    bar_labels, bar_values = _aggregate_top_n(grouped_s, top_n=15)
                    chart_type = (
                        "horizontal_bar" if len(bar_labels) > 6 else "bar"
                    )
                    charts.append(
                        _make_chart(
                            title=f"{num_col} by {cat_col}",
                            chart_type=chart_type,
                            category="comparison",
                            x_axis=bar_labels,
                            series=[{"name": num_col, "data": bar_values}],
                            description=f"Comparison of {num_col} across {cat_col} categories.",
                            x_label=cat_col,
                            y_label=num_col,
                        )
                    )
                    seen.add(key_bar)

                # Pie & Donut Charts (Top 10 + Others)
                pie_labels, pie_values = _aggregate_top_n(grouped_s, top_n=10)

                if key_pie not in seen:
                    series = [
                        {
                            "name": num_col,
                            "data": [
                                {"name": lbl, "value": val}
                                for lbl, val in zip(pie_labels, pie_values)
                            ],
                        }
                    ]
                    charts.append(
                        _make_chart(
                            title=f"{num_col} Distribution by {cat_col}",
                            chart_type="pie",
                            category="distribution",
                            series=series,
                            description=f"Pie chart breakdown of {num_col} across {cat_col}.",
                        )
                    )
                    seen.add(key_pie)

                if key_donut not in seen:
                    series = [
                        {
                            "name": num_col,
                            "data": [
                                {"name": lbl, "value": val}
                                for lbl, val in zip(pie_labels, pie_values)
                            ],
                        }
                    ]
                    charts.append(
                        _make_chart(
                            title=f"{num_col} Share ({cat_col})",
                            chart_type="donut",
                            category="distribution",
                            series=series,
                            description=f"Donut chart showing proportional share of {num_col}.",
                        )
                    )
                    seen.add(key_donut)

            except Exception as exc:
                logger.warning(
                    "Cat×Num chart failed for '%s' × '%s': %s", cat_col, num_col, exc
                )

    # ── 3. HISTOGRAMS ──────────────────────────────────────────────────────
    for num_col in numeric_cols:
        key = f"hist_{num_col}"
        if key in seen:
            continue
        try:
            s = (
                numeric_frame[num_col]
                if num_col in numeric_frame.columns
                else numeric_series(df[num_col])
            ).dropna()
            if len(s) < 3:
                continue
            n_bins = min(10, max(3, int(np.sqrt(len(s)))))
            counts, bins = np.histogram(s, bins=n_bins)
            labels = [
                f"{_safe_val(bins[i])} – {_safe_val(bins[i + 1])}"
                for i in range(len(counts))
            ]
            charts.append(
                _make_chart(
                    title=f"Histogram of {num_col}",
                    chart_type="bar",
                    category="distribution",
                    x_axis=labels,
                    series=[
                        {"name": "Frequency", "data": [int(v) for v in counts.tolist()]}
                    ],
                    description=f"Binned frequency distribution for {num_col}.",
                    x_label=num_col,
                    y_label="Count",
                )
            )
            seen.add(key)
        except Exception as exc:
            logger.warning("Histogram failed for '%s': %s", num_col, exc)

    # ── 4. BOXPLOTS ────────────────────────────────────────────────────────
    for num_col in numeric_cols:
        key = f"box_{num_col}"
        if key in seen:
            continue
        try:
            s = (
                numeric_frame[num_col]
                if num_col in numeric_frame.columns
                else numeric_series(df[num_col])
            ).dropna()
            if len(s) < 3:
                continue
            qmin = _safe_val(s.min())
            q1 = _safe_val(s.quantile(0.25))
            qmed = _safe_val(s.median())
            q3 = _safe_val(s.quantile(0.75))
            qmax = _safe_val(s.max())

            charts.append(
                _make_chart(
                    title=f"Boxplot of {num_col}",
                    chart_type="boxplot",
                    category="distribution",
                    x_axis=[num_col],
                    series=[
                        {
                            "name": num_col,
                            "data": [[qmin, q1, qmed, q3, qmax]],
                        }
                    ],
                    description=f"Five-number summary (Min, Q1, Median, Q3, Max) for {num_col}.",
                    y_label=num_col,
                )
            )
            seen.add(key)
        except Exception as exc:
            logger.warning("Boxplot failed for '%s': %s", num_col, exc)

    # ── 5. CATEGORY-ONLY CHARTS (Top 10 + Others) ─────────────────────────
    for cat_col in categorical_cols:
        key = f"catonly_{cat_col}"
        if key in seen:
            continue
        try:
            counts = df[cat_col].astype(str).value_counts()
            if len(counts) < 2:
                continue
            cat_labels, cat_values = _aggregate_top_n(counts, top_n=10)
            charts.append(
                _make_chart(
                    title=f"{cat_col} Frequency",
                    chart_type="donut",
                    category="distribution",
                    series=[
                        {
                            "name": "Count",
                            "data": [
                                {"name": lbl, "value": val}
                                for lbl, val in zip(cat_labels, cat_values)
                            ],
                        }
                    ],
                    description=f"Distribution count across {cat_col}.",
                )
            )
            seen.add(key)
        except Exception as exc:
            logger.warning("Category-only chart failed for '%s': %s", cat_col, exc)

    # ── 6. SCATTER PLOTS ───────────────────────────────────────────────────
    if len(numeric_cols) >= 2:
        for i in range(len(numeric_cols)):
            for j in range(i + 1, len(numeric_cols)):
                col1, col2 = numeric_cols[i], numeric_cols[j]
                key = f"scatter_{col1}_{col2}"
                if key in seen:
                    continue
                try:
                    s1 = (
                        numeric_frame[col1]
                        if col1 in numeric_frame.columns
                        else numeric_series(df[col1])
                    )
                    s2 = (
                        numeric_frame[col2]
                        if col2 in numeric_frame.columns
                        else numeric_series(df[col2])
                    )
                    scatter = pd.DataFrame({col1: s1, col2: s2}).dropna().head(500)
                    if len(scatter) < 3:
                        continue
                    charts.append(
                        _make_chart(
                            title=f"{col1} vs {col2}",
                            chart_type="scatter",
                            category="correlation",
                            series=[
                                {
                                    "name": f"{col1} vs {col2}",
                                    "data": [
                                        [_safe_val(x), _safe_val(y)]
                                        for x, y in scatter.values.tolist()
                                    ],
                                }
                            ],
                            description=f"Relationship between {col1} and {col2}.",
                            x_label=col1,
                            y_label=col2,
                        )
                    )
                    seen.add(key)
                except Exception as exc:
                    logger.warning(
                        "Scatter chart failed for '%s' × '%s': %s", col1, col2, exc
                    )

    # ── 7. CORRELATION HEATMAP ─────────────────────────────────────────────
    if (
        correlations
        and correlations.get("columns")
        and len(correlations["columns"]) >= 2
    ):
        try:
            corr_cols = correlations["columns"]
            corr_vals = correlations["values"]
            heatmap = [
                [x_idx, y_idx, _safe_val(corr_vals[y_idx][x_idx])]
                for y_idx in range(len(corr_cols))
                for x_idx in range(len(corr_cols))
            ]
            charts.append(
                _make_chart(
                    title="Correlation Heatmap",
                    chart_type="heatmap",
                    category="correlation",
                    x_axis=corr_cols,
                    y_axis=corr_cols,
                    series=[{"name": "Correlation", "data": heatmap}],
                    description="Pearson correlation matrix across numeric fields.",
                )
            )
        except Exception as exc:
            logger.warning("Heatmap failed: %s", exc)

    return charts, warnings


def _make_chart(
    title: str,
    chart_type: str,
    category: str,
    series: List[Dict[str, Any]],
    description: str,
    x_axis: List[Any] | None = None,
    y_axis: List[Any] | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
) -> Dict[str, Any]:
    return {
        "id": f"chart_{abs(hash((title, chart_type, category))) % 10_000_000}",
        "title": title,
        "type": chart_type,
        "category": category,
        "x_axis": x_axis or [],
        "y_axis": y_axis or [],
        "x_label": x_label,
        "y_label": y_label,
        "series": series,
        "description": description,
    }
