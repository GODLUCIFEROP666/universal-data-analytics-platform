"""
type_detector.py — Per-column type detection with strict 80% numeric rule & exception isolation.

Key rules:
1. 80%+ numeric rule: If >= 80% of non-null values can be converted to numbers
   (after stripping currency, commas, %, spaces), the column IS NUMERIC.
2. 70%+ date rule: If >= 70% of non-null values parse as dates, the column IS DATE.
3. Categorical / Text: All remaining columns. Bill Number / IDs are not excluded from charts.
4. Complete exception safety per column.
"""
from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^\+?[\d\s\-\(\)]{7,20}$")
URL_REGEX = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
IMAGE_URL_REGEX = re.compile(
    r"^https?://[^\s]+\.(jpg|jpeg|png|gif|webp|svg)(\?.*)?$", re.IGNORECASE
)
FILE_URL_REGEX = re.compile(
    r"^https?://[^\s]+\.(pdf|doc|docx|zip|rar|csv|xlsx|xls)(\?.*)?$", re.IGNORECASE
)
CURRENCY_STRIP_REGEX = re.compile(r"[\$,£€¥₹]")
WHITESPACE_REGEX = re.compile(r"\s+")
ID_KEYWORDS = {"id", "uuid", "guid", "key", "code", "sk", "pk", "no", "number"}
BOOLEAN_VALUES = {"true", "false", "yes", "no", "y", "n", "1", "0"}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def detect_column_types(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    column_info: Dict[str, Dict[str, Any]] = {}

    for column in df.columns:
        try:
            column_info[column] = _detect_single_column(df[column], column)
        except Exception as exc:
            logger.warning("Type detection failed for column '%s': %s", column, exc)
            column_info[column] = _fallback_info(df[column], column)

    return column_info


# ---------------------------------------------------------------------------
# Per-column detection (isolated)
# ---------------------------------------------------------------------------

def _detect_single_column(series: pd.Series, column: Any) -> Dict[str, Any]:
    column_str = str(column).strip()
    column_lower = column_str.lower()

    non_null = series.dropna()
    sample_size = int(len(non_null))

    if sample_size == 0:
        return {
            "detected_type": "Text",
            "is_id": False,
            "is_numeric": False,
            "is_date": False,
            "is_categorical": False,
            "exclude_from_charts": True,
            "unique_count": 0,
            "null_count": int(series.isna().sum()),
        }

    unique_count = int(series.nunique(dropna=True))

    # Safe string series for regex / stripping
    str_series = non_null.apply(
        lambda x: str(x)
        if x is not None and not (isinstance(x, float) and np.isnan(x))
        else ""
    )

    # ── 1. TEST NUMERIC (Strict 80% Rule) ─────────────────────────────────
    cleaned_num_str = (
        str_series.str.replace(CURRENCY_STRIP_REGEX, "", regex=True)
        .str.replace("%", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(WHITESPACE_REGEX, "", regex=True)
    )
    parsed_nums = pd.to_numeric(cleaned_num_str, errors="coerce")
    valid_num_count = int(parsed_nums.notna().sum())
    numeric_ratio = valid_num_count / sample_size if sample_size > 0 else 0.0

    if numeric_ratio >= 0.8:
        # The column IS NUMERIC!
        has_percent = str_series.str.contains("%", regex=False).mean() > 0.2
        has_currency = (
            str_series.str.contains(CURRENCY_STRIP_REGEX, regex=True).mean() > 0.2
            or any(k in column_lower for k in ["amount", "price", "cost", "bill", "salary", "fee", "revenue", "income", "sales", "total"])
        )
        valid_vals = parsed_nums.dropna()
        is_integer = (
            (valid_vals.mod(1) == 0).all() if not valid_vals.empty else False
        )

        if has_percent:
            detected_type = "Percentage"
        elif has_currency:
            detected_type = "Currency"
        elif is_integer:
            detected_type = "Integer"
        else:
            detected_type = "Float"

        return {
            "detected_type": detected_type,
            "is_id": False,
            "is_numeric": True,
            "is_date": False,
            "is_categorical": False,
            "exclude_from_charts": False,
            "unique_count": unique_count,
            "null_count": int(series.isna().sum()),
        }

    # ── 2. TEST DATE (Strict 80% Rule) ─────────────────────────────────────
    if _series_has_datetime_objects(non_null) or pd.api.types.is_datetime64_any_dtype(series):
        detected_type = "Datetime" if _objects_have_time(non_null) else "Date"
        return {
            "detected_type": detected_type,
            "is_id": False,
            "is_numeric": False,
            "is_date": True,
            "is_categorical": False,
            "exclude_from_charts": False,
            "unique_count": unique_count,
            "null_count": int(series.isna().sum()),
        }

    parsed_dates = pd.to_datetime(str_series, errors="coerce", format="mixed")
    valid_date_count = int(parsed_dates.notna().sum())
    date_ratio = valid_date_count / sample_size if sample_size > 0 else 0.0

    if date_ratio >= 0.8:
        has_time = (
            (parsed_dates.dt.hour != 0).any() or (parsed_dates.dt.minute != 0).any()
            if not parsed_dates.dropna().empty
            else False
        )
        detected_type = "Datetime" if has_time else "Date"
        return {
            "detected_type": detected_type,
            "is_id": False,
            "is_numeric": False,
            "is_date": True,
            "is_categorical": False,
            "exclude_from_charts": False,
            "unique_count": unique_count,
            "null_count": int(series.isna().sum()),
        }

    # ── 3. TEST BOOLEAN (Strict 80% Rule) ──────────────────────────────────
    bool_matches = str_series.str.strip().str.lower().isin(BOOLEAN_VALUES)
    bool_ratio = bool_matches.sum() / sample_size if sample_size > 0 else 0.0

    if bool_ratio >= 0.8:
        return {
            "detected_type": "Boolean",
            "is_id": False,
            "is_numeric": False,
            "is_date": False,
            "is_categorical": True,
            "exclude_from_charts": False,
            "unique_count": unique_count,
            "null_count": int(series.isna().sum()),
        }

    # ── 4. CATEGORICAL / TEXT / ID ─────────────────────────────────────────
    name_tokens = re.split(r"[\s_\-]+", column_lower)
    name_has_id = (
        any(token in ID_KEYWORDS for token in name_tokens)
        or column_lower.endswith("id")
        or column_lower.startswith("id_")
    )

    is_id = False
    if name_has_id:
        is_id = True
        detected_type = "Unique IDs"
    elif str_series.str.match(EMAIL_REGEX).mean() > 0.8:
        detected_type = "Email"
    elif str_series.str.match(IMAGE_URL_REGEX).mean() > 0.8:
        detected_type = "Image URL"
    elif str_series.str.match(FILE_URL_REGEX).mean() > 0.8:
        detected_type = "File URL"
    elif str_series.str.match(URL_REGEX).mean() > 0.8:
        detected_type = "URL"
    elif str_series.str.match(PHONE_REGEX).mean() > 0.8:
        detected_type = "Phone Number"
    else:
        detected_type = "Category" if unique_count <= 100 else "Text"

    exclude = detected_type in {"Email", "URL", "Image URL", "File URL", "Phone Number"}

    return {
        "detected_type": detected_type,
        "is_id": is_id,
        "is_numeric": False,
        "is_date": False,
        "is_categorical": True,
        "exclude_from_charts": exclude,
        "unique_count": unique_count,
        "null_count": int(series.isna().sum()),
    }


def _fallback_info(series: pd.Series, column: Any) -> Dict[str, Any]:
    try:
        unique_count = int(series.nunique(dropna=True))
        null_count = int(series.isna().sum())
    except Exception:
        unique_count = 0
        null_count = 0
    return {
        "detected_type": "Text",
        "is_id": False,
        "is_numeric": False,
        "is_date": False,
        "is_categorical": True,
        "exclude_from_charts": False,
        "unique_count": unique_count,
        "null_count": null_count,
    }


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _series_has_datetime_objects(series: pd.Series) -> bool:
    try:
        return series.apply(
            lambda x: isinstance(x, (datetime.datetime, datetime.date, pd.Timestamp))
        ).any()
    except Exception:
        return False


def _objects_have_time(series: pd.Series) -> bool:
    try:
        for v in series.head(20):
            if isinstance(v, datetime.datetime) and (v.hour != 0 or v.minute != 0 or v.second != 0):
                return True
            if isinstance(v, pd.Timestamp) and (v.hour != 0 or v.minute != 0 or v.second != 0):
                return True
        return False
    except Exception:
        return False
