"""
stats_engine.py — Dataset statistics with full per-column exception isolation.

Key hardening:
- Each column's stats block is wrapped in try/except.
- A failed column produces a minimal safe stats entry and a warning message;
  it never stops other columns from being analyzed.
- All numeric comparisons go through numeric_series() to avoid str<number errors.
- Datetime parsing goes through _safe_parse_dates() to avoid str<datetime errors.
- Returns a 'warnings' list alongside the stats so the frontend can display
  non-fatal issues without showing an error state.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from app.analyzer.file_parser import _safe_parse_dates, numeric_series
from app.analyzer.type_detector import detect_column_types

logger = logging.getLogger(__name__)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert a value to a Python float, avoiding NaN/Inf JSON issues."""
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    started = time.time()
    warnings: List[str] = []

    total_rows = int(len(df))
    total_columns = int(len(df.columns))

    if total_rows == 0 or total_columns == 0:
        return {
            "summary": {
                "total_rows": total_rows,
                "total_columns": total_columns,
                "missing_values": 0,
                "missing_percentage": 0.0,
                "duplicate_rows": 0,
                "memory_usage_mb": 0.0,
                "numeric_columns_count": 0,
                "categorical_columns_count": 0,
                "date_columns_count": 0,
                "boolean_columns_count": 0,
                "analysis_time_ms": 0.0,
            },
            "columns": {},
            "correlations": {},
            "insights": [
                {
                    "type": "summary",
                    "title": "Dataset is empty",
                    "description": "The uploaded file does not contain analyzable rows.",
                    "severity": "warning",
                }
            ],
            "warnings": [],
        }

    # --- Type detection (per-column isolation is inside detect_column_types) ---
    try:
        column_types = detect_column_types(df)
    except Exception as exc:
        logger.error("Type detection failed entirely: %s", exc, exc_info=True)
        warnings.append(f"Type detection encountered an error: {exc}")
        column_types = {col: _minimal_type_info() for col in df.columns}

    numeric_cols = [
        name
        for name, info in column_types.items()
        if info["is_numeric"] and not info["is_id"]
    ]
    categorical_cols = [
        name
        for name, info in column_types.items()
        if info["is_categorical"]
        or info["detected_type"] in {"Category", "Boolean", "Text"}
    ]
    date_cols = [name for name, info in column_types.items() if info["is_date"]]
    boolean_cols = [
        name for name, info in column_types.items() if info.get("detected_type") == "Boolean"
    ]

    # --- Basic summary stats ---
    total_cells = max(total_rows * total_columns, 1)
    try:
        missing_values = int(df.isna().sum().sum())
    except Exception:
        missing_values = 0
    missing_percentage = _safe_float(round((missing_values / total_cells) * 100, 2))

    try:
        duplicate_rows = int(df.duplicated().sum())
    except Exception:
        duplicate_rows = 0
        warnings.append("Could not compute duplicate row count.")

    try:
        memory_usage_mb = _safe_float(
            round(float(df.memory_usage(deep=True).sum()) / (1024 * 1024), 3)
        )
    except Exception:
        memory_usage_mb = 0.0

    # --- Per-column stats ---
    columns_stats: Dict[str, Any] = {}
    cleaned_numeric_frame = pd.DataFrame(index=df.index)

    for column in df.columns:
        try:
            col_stat = _analyze_column(df[column], column, total_rows, column_types)
            columns_stats[column] = col_stat
            if column_types.get(column, {}).get("is_numeric") and not column_types.get(column, {}).get("is_id"):
                try:
                    cleaned_numeric_frame[column] = numeric_series(df[column])
                except Exception as exc:
                    logger.warning("Could not build numeric series for '%s': %s", column, exc)
        except Exception as exc:
            logger.warning("Stats computation failed for column '%s': %s", column, exc)
            warnings.append(f"Column '{column}' could not be fully analyzed: {exc}")
            columns_stats[column] = _minimal_column_stat(df[column], column, column_types)

    # --- Correlation matrix ---
    try:
        correlations = _correlation_matrix(cleaned_numeric_frame, numeric_cols)
    except Exception as exc:
        logger.warning("Correlation matrix failed: %s", exc)
        warnings.append(f"Correlation matrix could not be computed: {exc}")
        correlations = {}

    # --- Insights ---
    try:
        insights = _build_insights(columns_stats, correlations, total_rows, duplicate_rows, missing_percentage)
    except Exception as exc:
        logger.warning("Insights generation failed: %s", exc)
        warnings.append(f"Automated insights could not be generated: {exc}")
        insights = []

    return {
        "summary": {
            "total_rows": total_rows,
            "total_columns": total_columns,
            "missing_values": missing_values,
            "missing_percentage": missing_percentage,
            "duplicate_rows": duplicate_rows,
            "memory_usage_mb": memory_usage_mb,
            "numeric_columns_count": len(numeric_cols),
            "categorical_columns_count": len(categorical_cols),
            "date_columns_count": len(date_cols),
            "boolean_columns_count": len(boolean_cols),
            "analysis_time_ms": _safe_float(round((time.time() - started) * 1000, 2)),
        },
        "columns": columns_stats,
        "correlations": correlations,
        "insights": insights,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Per-column analysis
# ---------------------------------------------------------------------------

def _analyze_column(
    series: pd.Series,
    column: Any,
    total_rows: int,
    column_types: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    info = column_types.get(str(column), _minimal_type_info())
    null_count = int(series.isna().sum())
    null_pct = _safe_float(round((null_count / max(total_rows, 1)) * 100, 2))

    col_stat: Dict[str, Any] = {
        "name": str(column),
        "detected_type": info["detected_type"],
        "is_numeric": info["is_numeric"],
        "is_date": info["is_date"],
        "is_categorical": info["is_categorical"],
        "is_id": info["is_id"],
        "exclude_from_charts": info["exclude_from_charts"],
        "null_count": null_count,
        "null_percentage": null_pct,
        "unique_count": int(series.nunique(dropna=True)),
    }

    # --- Numeric stats ---
    if info["is_numeric"] and not info["is_id"]:
        try:
            numeric_s = numeric_series(series)
            clean = numeric_s.dropna()
            if not clean.empty:
                q1 = _safe_float(clean.quantile(0.25))
                q3 = _safe_float(clean.quantile(0.75))
                iqr = _safe_float(q3 - q1)
                outliers = clean[(clean < (q1 - 1.5 * iqr)) | (clean > (q3 + 1.5 * iqr))]
                modes = clean.mode()
                mode_val = (
                    _safe_float(modes.iloc[0])
                    if not modes.empty
                    else _safe_float(clean.median())
                )
                col_stat["stats"] = {
                    "min": _safe_float(clean.min()),
                    "max": _safe_float(clean.max()),
                    "mean": _safe_float(round(clean.mean(), 4)),
                    "median": _safe_float(clean.median()),
                    "mode": mode_val,
                    "variance": _safe_float(round(clean.var(), 4)) if len(clean) > 1 else 0.0,
                    "std_dev": _safe_float(round(clean.std(), 4)) if len(clean) > 1 else 0.0,
                    "q1": round(q1, 4),
                    "q3": round(q3, 4),
                    "iqr": round(iqr, 4),
                    "outliers_count": int(len(outliers)),
                    "skewness": _safe_float(round(clean.skew(), 4)) if len(clean) > 2 else 0.0,
                    "kurtosis": _safe_float(round(clean.kurtosis(), 4)) if len(clean) > 3 else 0.0,
                    "most_frequent_values": _frequency_items(series, descending=True),
                    "least_frequent_values": _frequency_items(series, descending=False),
                    "distribution": _distribution(clean),
                }
        except Exception as exc:
            logger.warning("Numeric stats failed for '%s': %s", column, exc)
            col_stat["stats"] = None

    # --- Categorical top values ---
    if info["is_categorical"] or info["detected_type"] in {"Category", "Boolean", "Text", "Unique IDs"}:
        try:
            col_stat["top_values"] = _frequency_items(series, descending=True)
            col_stat["bottom_values"] = _frequency_items(series, descending=False)
        except Exception as exc:
            logger.warning("Frequency items failed for '%s': %s", column, exc)

    # --- Date stats ---
    if info["is_date"]:
        try:
            parsed = _safe_parse_dates(series).dropna()
            if not parsed.empty:
                # Ensure timezone-naive for formatting
                if hasattr(parsed.dt, "tz") and parsed.dt.tz is not None:
                    parsed = parsed.dt.tz_localize(None)
                has_time = _has_time(parsed)
                fmt = "%Y-%m-%d %H:%M:%S" if has_time else "%Y-%m-%d"
                col_stat["date_range"] = {
                    "min_date": parsed.min().strftime(fmt),
                    "max_date": parsed.max().strftime(fmt),
                }
                col_stat["distribution"] = _date_distribution(parsed)
        except Exception as exc:
            logger.warning("Date stats failed for '%s': %s", column, exc)

    return col_stat


def _minimal_column_stat(
    series: pd.Series, column: Any, column_types: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Return the smallest safe column stat dict when analysis fails."""
    info = column_types.get(str(column), _minimal_type_info())
    try:
        null_count = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))
    except Exception:
        null_count = 0
        unique_count = 0
    return {
        "name": str(column),
        "detected_type": info["detected_type"],
        "is_numeric": info["is_numeric"],
        "is_date": info["is_date"],
        "is_categorical": info["is_categorical"],
        "is_id": info["is_id"],
        "exclude_from_charts": True,
        "null_count": null_count,
        "null_percentage": 0.0,
        "unique_count": unique_count,
    }


def _minimal_type_info() -> Dict[str, Any]:
    return {
        "detected_type": "Text",
        "is_id": False,
        "is_numeric": False,
        "is_date": False,
        "is_categorical": False,
        "exclude_from_charts": True,
        "unique_count": 0,
        "null_count": 0,
    }


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def _frequency_items(
    series: pd.Series, descending: bool = True, limit: int = 10
) -> List[Dict[str, Any]]:
    try:
        counts = series.dropna().astype(str).value_counts(ascending=not descending).head(limit)
        total = max(int(series.dropna().shape[0]), 1)
        return [
            {
                "value": str(index),
                "count": int(count),
                "percentage": _safe_float(round((count / total) * 100, 2)),
            }
            for index, count in counts.items()
        ]
    except Exception:
        return []


def _distribution(series: pd.Series) -> Dict[str, Any]:
    try:
        if series.empty:
            return {"type": "empty", "buckets": []}
        bins = min(10, max(3, int(np.sqrt(len(series)))))
        counts, edges = np.histogram(series, bins=bins)
        return {
            "type": "histogram",
            "buckets": [
                {
                    "label": f"{_safe_float(round(float(edges[i]), 2))} - {_safe_float(round(float(edges[i + 1]), 2))}",
                    "count": int(counts[i]),
                }
                for i in range(len(counts))
            ],
        }
    except Exception:
        return {"type": "empty", "buckets": []}


def _date_distribution(series: pd.Series) -> Dict[str, Any]:
    try:
        if series.empty:
            return {"type": "empty", "buckets": []}
        tz_naive = series.dt.tz_localize(None) if series.dt.tz is not None else series
        try:
            periods = tz_naive.dt.to_period("M").astype(str).value_counts().sort_index()
        except Exception:
            periods = tz_naive.dt.strftime("%Y-%m").value_counts().sort_index()
        return {
            "type": "monthly",
            "buckets": [
                {"label": str(index), "count": int(value)}
                for index, value in periods.items()
            ],
        }
    except Exception:
        return {"type": "empty", "buckets": []}


def _correlation_matrix(
    numeric_frame: pd.DataFrame, numeric_cols: List[str]
) -> Dict[str, Any]:
    if len(numeric_cols) < 2:
        return {}
    try:
        valid_cols = [c for c in numeric_cols if c in numeric_frame.columns]
        if len(valid_cols) < 2:
            return {}
        corr = numeric_frame[valid_cols].corr().fillna(0).round(4)
        corr_values = corr.values
        corr_values = np.nan_to_num(corr_values, nan=0.0, posinf=1.0, neginf=-1.0)
        clean_matrix = [
            [_safe_float(round(float(cell), 4)) for cell in row]
            for row in corr_values.tolist()
        ]
        return {"columns": list(corr.columns), "values": clean_matrix}
    except Exception as exc:
        logger.warning("Correlation matrix computation failed: %s", exc)
        return {}


def _build_insights(
    columns_stats: Dict[str, Any],
    correlations: Dict[str, Any],
    total_rows: int,
    duplicate_rows: int,
    missing_percentage: float,
) -> List[Dict[str, Any]]:
    insights: List[Dict[str, Any]] = []

    try:
        quality = (
            "excellent"
            if missing_percentage < 2 and duplicate_rows == 0
            else "good"
            if missing_percentage < 10
            else "attention"
        )
        insights.append(
            {
                "type": "summary",
                "title": f"Dataset health is {quality}",
                "description": (
                    f"Analyzed {total_rows:,} rows with {missing_percentage}% missing cells "
                    f"and {duplicate_rows:,} duplicate rows."
                ),
                "severity": "info" if quality != "attention" else "warning",
            }
        )
    except Exception:
        pass

    try:
        if duplicate_rows > 0:
            insights.append(
                {
                    "type": "quality",
                    "title": "Duplicate rows detected",
                    "description": f"{duplicate_rows:,} duplicate rows were found and should be reviewed.",
                    "severity": "warning",
                }
            )
    except Exception:
        pass

    try:
        high_missing = [
            f"{name} ({info['null_percentage']}%)"
            for name, info in columns_stats.items()
            if info.get("null_percentage", 0) >= 20
        ]
        if high_missing:
            insights.append(
                {
                    "type": "quality",
                    "title": "Columns with substantial missing data",
                    "description": ", ".join(high_missing[:5]),
                    "severity": "warning",
                }
            )
    except Exception:
        pass

    try:
        if correlations and correlations.get("columns"):
            cols = correlations["columns"]
            vals = correlations["values"]
            strongest = None
            for i in range(len(cols)):
                for j in range(i + 1, len(cols)):
                    corr = float(vals[i][j])
                    if abs(corr) >= 0.7 and (strongest is None or abs(corr) > abs(strongest[2])):
                        strongest = (cols[i], cols[j], corr)
            if strongest:
                direction = "positive" if strongest[2] > 0 else "negative"
                insights.append(
                    {
                        "type": "correlation",
                        "title": f"Strong {direction} relationship found",
                        "description": (
                            f"{strongest[0]} and {strongest[1]} have a correlation of {strongest[2]:.2f}."
                        ),
                        "severity": "success",
                    }
                )
    except Exception:
        pass

    try:
        for name, info in columns_stats.items():
            stats = info.get("stats")
            if stats and stats.get("outliers_count", 0) > 0:
                outlier_pct = round((stats["outliers_count"] / max(total_rows, 1)) * 100, 1)
                if outlier_pct >= 3:
                    insights.append(
                        {
                            "type": "outlier",
                            "title": f"Outliers in {name}",
                            "description": f"{stats['outliers_count']:,} values fall outside the 1.5x IQR boundary.",
                            "severity": "warning",
                        }
                    )
                    break
    except Exception:
        pass

    try:
        for name, info in columns_stats.items():
            top_values = info.get("top_values") or []
            if top_values and top_values[0]["percentage"] >= 40:
                insights.append(
                    {
                        "type": "distribution",
                        "title": f"Dominant category in {name}",
                        "description": (
                            f"{top_values[0]['value']} accounts for {top_values[0]['percentage']}% of the column."
                        ),
                        "severity": "info",
                    }
                )
                break
    except Exception:
        pass

    return insights[:6]


def _has_time(series: pd.Series) -> bool:
    try:
        return (
            (series.dt.hour != 0).any()
            or (series.dt.minute != 0).any()
            or (series.dt.second != 0).any()
        )
    except Exception:
        return False
