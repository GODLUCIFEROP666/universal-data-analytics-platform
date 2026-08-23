"""
file_parser.py — Robust file parsing for CSV, XLS, and XLSX files.

Key features:
- Smart header-row probability detection: skips decorative title banners and merged-cell headers.
- Total/Subtotal row filtering: automatically strips trailing summary/footer rows.
- Numeric & Date conversion: applies canonical coercion for detected types.
- Excel error-cell scrubbing: replaces #N/A, #REF!, #VALUE! etc. with NaN.
"""
from __future__ import annotations

import datetime
import io
import logging
import re
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MAX_PREVIEW_ROWS = 50
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SUPPORTED_EXTENSIONS = {"csv", "xls", "xlsx"}

CURRENCY_STRIP_PATTERN = r"[\$,£€¥₹,%]"
WHITESPACE_STRIP_PATTERN = r"\s+"

_EXCEL_ERRORS = frozenset(
    ["#N/A", "#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NULL!", "#NUM!", "#ERROR!"]
)

TOTAL_ROW_PATTERN = re.compile(
    r"^\s*(grand\s+)?(total|subtotal|summary|balance|net\s+total|amount\s+in\s+words|page\s+\d+|report\s+generated|notes?|disclaimer|\*\*\*)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def numeric_series(series: pd.Series) -> pd.Series:
    """Canonical numeric conversion for a Pandas series.
    Strips currency symbols, percentage signs, commas, and whitespace.
    """
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    
    str_series = series.apply(_safe_str_or_nan)
    cleaned = (
        str_series
        .str.replace(CURRENCY_STRIP_PATTERN, "", regex=True)
        .str.replace(WHITESPACE_STRIP_PATTERN, "", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _safe_str_or_nan(v: Any) -> Any:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    if isinstance(v, str):
        s = v.strip()
        return np.nan if s in _EXCEL_ERRORS or s == "" else s
    return str(v).strip()


def _normalize_extension(filename: str) -> str:
    if not filename or "." not in filename:
        raise ValueError("A valid CSV, XLS, or XLSX filename is required.")
    return filename.rsplit(".", 1)[-1].lower().strip()


def _validate_file_content(file_bytes: bytes, ext: str) -> None:
    """Validate file magic bytes/content format matching extension."""
    if ext == "xlsx":
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise ValueError("Invalid file content for .xlsx extension (missing ZIP header).")
    elif ext == "xls":
        if not file_bytes.startswith(b"\xd0\xcf\x11\xe0"):
            raise ValueError("Invalid file content for .xls extension (missing OLE/BIFF header).")
    elif ext == "csv":
        try:
            sample = file_bytes[:4096]
            sample.decode("utf-8")
        except UnicodeDecodeError:
            try:
                sample.decode("latin1")
            except Exception as exc:
                raise ValueError("CSV file content is corrupt or unreadable binary.") from exc


# ---------------------------------------------------------------------------
# Inspect
# ---------------------------------------------------------------------------

def inspect_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    ext = _normalize_extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported file format. Upload CSV, XLS, or XLSX only.")

    if len(file_bytes) == 0:
        raise ValueError("The uploaded file is empty.")

    _validate_file_content(file_bytes, ext)

    if ext == "csv":
        return {"format": ext, "sheets": ["CSV Data"], "selected_sheet": "CSV Data"}

    try:
        excel_file = pd.ExcelFile(
            io.BytesIO(file_bytes),
            engine="openpyxl" if ext == "xlsx" else "xlrd",
        )
        sheets = excel_file.sheet_names
        excel_file.close()
        if not sheets:
            raise ValueError("The Excel file does not contain any readable sheets.")
        return {"format": ext, "sheets": sheets, "selected_sheet": sheets[0]}
    except ValueError:
        raise
    except Exception as exc:
        exc_str = str(exc).lower()
        if "password" in exc_str or "encrypted" in exc_str or "protected" in exc_str:
            raise ValueError("This file appears to be password-protected. Please remove the password and re-upload.") from exc
        raise ValueError(f"Failed to read Excel structure: {exc}") from exc


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

def parse_file_to_df(
    file_bytes: bytes,
    filename: str,
    sheet_name: Optional[str] = None,
) -> pd.DataFrame:
    ext = _normalize_extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported file format. Upload CSV, XLS, or XLSX only.")

    if len(file_bytes) == 0:
        raise ValueError("The uploaded file is empty.")

    _validate_file_content(file_bytes, ext)

    try:
        if ext == "csv":
            df = _read_csv(file_bytes)
        else:
            df = _read_excel(file_bytes, ext, sheet_name)
    except ValueError:
        raise
    except Exception as exc:
        exc_str = str(exc).lower()
        if "password" in exc_str or "encrypted" in exc_str or "protected" in exc_str:
            raise ValueError("This file appears to be password-protected. Please remove the password and re-upload.") from exc
        raise ValueError(f"Error parsing file data: {exc}") from exc

    if df is None or df.empty:
        return pd.DataFrame()

    return _clean_dataframe(df)


def _read_csv(file_bytes: bytes) -> pd.DataFrame:
    last_error: Optional[Exception] = None
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            return pd.read_csv(
                io.BytesIO(file_bytes),
                encoding=encoding,
                sep=None,
                engine="python",
                header=None,
                dtype=object,
                keep_default_na=False,
                na_values=list(_EXCEL_ERRORS) + ["", "NA", "N/A", "NULL", "None"],
            )
        except Exception as exc:
            last_error = exc
    raise ValueError(f"Failed to read CSV file: {last_error}")


def _read_excel(file_bytes: bytes, ext: str, sheet_name: Optional[str]) -> pd.DataFrame:
    engine = "openpyxl" if ext == "xlsx" else "xlrd"
    kwargs: Dict[str, Any] = {
        "sheet_name": sheet_name if sheet_name else 0,
        "engine": engine,
        "header": None,
        "dtype": object,
        "keep_default_na": False,
        "na_values": list(_EXCEL_ERRORS),
    }
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), **kwargs)
    except Exception as exc:
        exc_str = str(exc).lower()
        if "password" in exc_str or "encrypted" in exc_str or "protected" in exc_str:
            raise ValueError("This file appears to be password-protected. Please remove the password and re-upload.") from exc
        logger.warning("Raw Excel read failed (%s); retrying fallback.", exc)
        fallback_kwargs: Dict[str, Any] = {
            "sheet_name": sheet_name if sheet_name else 0,
            "engine": engine,
            "dtype": object,
        }
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), **fallback_kwargs)
        except Exception as fb_exc:
            fb_str = str(fb_exc).lower()
            if "password" in fb_str or "encrypted" in fb_str or "protected" in fb_str:
                raise ValueError("This file appears to be password-protected. Please remove the password and re-upload.") from fb_exc
            raise fb_exc
    return df


# ---------------------------------------------------------------------------
# Smart Header Detection & Cleaning
# ---------------------------------------------------------------------------

def _is_pure_number(v: Any) -> bool:
    if isinstance(v, (int, float)):
        return not np.isnan(v)
    if isinstance(v, str):
        clean = v.replace(",", "").replace("$", "").replace("€", "").replace("£", "").replace("%", "").strip()
        try:
            float(clean)
            return True
        except ValueError:
            return False
    return False


def _is_date_str(v: Any) -> bool:
    if isinstance(v, (datetime.datetime, datetime.date, pd.Timestamp)):
        return True
    if isinstance(v, str):
        v = v.strip()
        if len(v) >= 6 and not v.isdigit():
            try:
                res = pd.to_datetime(v, errors="coerce")
                return pd.notna(res)
            except Exception:
                return False
    return False


def _detect_header_row(df: pd.DataFrame) -> int:
    """Scan top 30 rows to find row index with highest probability of being column headers."""
    max_scan = min(30, len(df))
    best_row = 0
    best_score = -1e9
    max_cols = len(df.columns)

    header_keywords = {
        "date", "time", "bill", "number", "no", "id", "amount", "price", "cost", "total",
        "category", "type", "name", "customer", "product", "qty", "quantity", "status",
        "description", "patient", "department", "segment", "region", "sales", "discount", "code"
    }

    for row_idx in range(max_scan):
        row = df.iloc[row_idx]
        non_null = row.dropna()
        non_null_count = len(non_null)

        if non_null_count == 0:
            continue

        # Skip rows with only 1 cell filled out of many (likely merged title banner)
        if non_null_count < 2 and max_cols >= 3:
            continue

        string_cols = 0
        unique_strings = set()
        for v in non_null:
            v_str = str(v).strip()
            if not v_str:
                continue
            if _is_pure_number(v_str) or _is_date_str(v_str):
                continue
            if len(v_str) < 50:
                string_cols += 1
                unique_strings.add(v_str.lower())

        if string_cols == 0:
            continue

        score = (len(unique_strings) * 15.0) + (non_null_count * 5.0)

        matched = sum(1 for s in unique_strings if any(k in s for k in header_keywords))
        score += matched * 20.0

        # Data density bonus in subsequent row
        if row_idx + 1 < len(df):
            next_row = df.iloc[row_idx + 1].dropna()
            data_cells = sum(
                1 for v in next_row
                if _is_pure_number(str(v).strip()) or _is_date_str(str(v).strip()) or len(str(v).strip()) < 30
            )
            if data_cells >= 2:
                score += 30.0

        if score > best_score:
            best_score = score
            best_row = row_idx

    return best_row


def _apply_header_row(raw_df: pd.DataFrame, header_row: int) -> pd.DataFrame:
    new_columns = []
    for c in range(len(raw_df.columns)):
        val = raw_df.iloc[header_row, c]
        s_val = str(val).strip() if pd.notna(val) else ""
        new_columns.append(s_val if s_val and s_val != "nan" else f"Column_{c + 1}")

    data_df = raw_df.iloc[header_row + 1:].copy().reset_index(drop=True)
    data_df.columns = new_columns
    return data_df


def _filter_total_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out trailing or embedded TOTAL/SUBTOTAL/FOOTER rows using vectorized ops."""
    if df.empty:
        return df

    # Check only the first 3 string columns for total-row patterns (vectorized)
    check_cols = df.columns[:3]
    is_total = pd.Series(False, index=df.index)
    for col in check_cols:
        try:
            str_col = df[col].astype(str).str.strip()
            is_total = is_total | str_col.str.match(TOTAL_ROW_PATTERN, na=False)
        except Exception:
            pass

    return df[~is_total].reset_index(drop=True)


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Full cleaning pipeline."""
    try:
        # Step 1: Detect header row & promote column names
        header_row = _detect_header_row(df)
        df = _apply_header_row(df, header_row)

        # Step 2: Drop completely empty rows and columns
        df = df.dropna(how="all").dropna(how="all", axis=1)
        if df.empty:
            return df

        # Step 3: Filter out TOTAL / SUBTOTAL / FOOTER rows
        df = _filter_total_rows(df)
        if df.empty:
            return df

        # Step 4: Clean & deduplicate column names
        cleaned_columns: List[str] = []
        seen: Dict[str, int] = {}
        for index, col in enumerate(df.columns):
            name = str(col).strip()
            if not name or name.startswith("Unnamed:") or name == "nan":
                name = f"Column_{index + 1}"
            occurrence = seen.get(name, 0)
            cleaned_columns.append(name if occurrence == 0 else f"{name}_{occurrence + 1}")
            seen[name] = occurrence + 1

        df = df.copy()
        df.columns = cleaned_columns

        # Step 5: Type-guided column normalization
        from app.analyzer.type_detector import detect_column_types
        types_info = detect_column_types(df)

        for col in df.columns:
            info = types_info.get(col, {})
            try:
                if info.get("is_numeric"):
                    df[col] = numeric_series(df[col])
                elif info.get("is_date"):
                    df[col] = _safe_parse_dates(df[col])
                else:
                    df[col] = df[col].apply(lambda v: _safe_str_or_nan(v))
            except Exception as exc:
                logger.warning("Normalizing column '%s' failed: %s", col, exc)

        # Step 6: Drop rows that became all NaN
        df = df.dropna(how="all")
        return df

    except Exception as exc:
        logger.error("DataFrame cleaning failed: %s", exc, exc_info=True)
        return df if df is not None else pd.DataFrame()


# ---------------------------------------------------------------------------
# Filter / sort / preview helpers
# ---------------------------------------------------------------------------

def apply_filters(
    df: pd.DataFrame,
    search_query: Optional[str] = None,
    category_filters: Optional[Dict[str, List[str]]] = None,
    numeric_ranges: Optional[Dict[str, Dict[str, float]]] = None,
    date_ranges: Optional[Dict[str, Dict[str, str]]] = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    filtered = df.copy()

    if category_filters:
        for column, values in category_filters.items():
            if column in filtered.columns and values:
                try:
                    allowed = {str(v) for v in values}
                    filtered = filtered[filtered[column].astype(str).isin(allowed)]
                except Exception as exc:
                    logger.warning("Category filter failed for '%s': %s", column, exc)

    if numeric_ranges:
        for column, limits in numeric_ranges.items():
            if column not in filtered.columns:
                continue
            try:
                num = numeric_series(filtered[column])
                mask = pd.Series(True, index=filtered.index)
                if limits.get("min") is not None:
                    mask &= num >= float(limits["min"])
                if limits.get("max") is not None:
                    mask &= num <= float(limits["max"])
                filtered = filtered[mask.fillna(False)]
            except Exception as exc:
                logger.warning("Numeric range filter failed for '%s': %s", column, exc)

    if date_ranges:
        for column, limits in date_ranges.items():
            if column not in filtered.columns:
                continue
            try:
                parsed = _safe_parse_dates(filtered[column])
                mask = pd.Series(True, index=filtered.index)
                if limits.get("start"):
                    mask &= parsed >= pd.to_datetime(limits["start"], errors="coerce")
                if limits.get("end"):
                    mask &= parsed <= pd.to_datetime(limits["end"], errors="coerce")
                filtered = filtered[mask.fillna(False)]
            except Exception as exc:
                logger.warning("Date range filter failed for '%s': %s", column, exc)

    if search_query:
        query = search_query.strip().lower()
        if query:
            try:
                text_frame = filtered.astype(str).apply(lambda col: col.str.lower())
                filtered = filtered[
                    text_frame.apply(lambda row: row.str.contains(query, na=False)).any(axis=1)
                ]
            except Exception as exc:
                logger.warning("Search query filter failed: %s", exc)

    return filtered


def sort_dataframe(
    df: pd.DataFrame, sort_by: Optional[str], sort_direction: str = "desc"
) -> pd.DataFrame:
    if df.empty or not sort_by or sort_by not in df.columns:
        return df

    try:
        ascending = sort_direction.lower() == "asc"
        series = df[sort_by]
        if pd.api.types.is_numeric_dtype(series):
            sort_key = numeric_series(series)
            return (
                df.assign(_sort_key=sort_key)
                .sort_values(by="_sort_key", ascending=ascending, na_position="last")
                .drop(columns=["_sort_key"])
            )
        if pd.api.types.is_datetime64_any_dtype(series):
            sort_key = _safe_parse_dates(series)
            return (
                df.assign(_sort_key=sort_key)
                .sort_values(by="_sort_key", ascending=ascending, na_position="last")
                .drop(columns=["_sort_key"])
            )
        return df.sort_values(by=sort_by, ascending=ascending, na_position="last")
    except Exception as exc:
        logger.warning("Sort failed for column '%s': %s", sort_by, exc)
        return df


def get_dataframe_preview(
    df: pd.DataFrame, page: int = 1, page_size: int = MAX_PREVIEW_ROWS
) -> Dict[str, Any]:
    total_rows = int(len(df))
    if total_rows == 0:
        return {"rows": [], "page": 1, "page_size": page_size, "total_rows": 0, "total_pages": 0}

    current_page = max(int(page), 1)
    current_size = max(int(page_size), 1)
    total_pages = int((total_rows + current_size - 1) / current_size)
    start = (current_page - 1) * current_size
    stop = min(start + current_size, total_rows)
    preview_df = df.iloc[start:stop].copy()

    records = _safe_records(preview_df)
    return {
        "rows": records,
        "page": current_page,
        "page_size": current_size,
        "total_rows": total_rows,
        "total_pages": total_pages,
    }


def dataframe_to_records(df: pd.DataFrame, max_rows: Optional[int] = None) -> List[Dict[str, Any]]:
    working = df.head(max_rows).copy() if max_rows else df.copy()
    return _safe_records(working)


def _safe_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    result = []
    for _, row in df.iterrows():
        clean_row: Dict[str, Any] = {}
        for k, v in row.items():
            clean_row[k] = _json_safe(v)
        result.append(clean_row)
    return result


def _json_safe(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return None
    if isinstance(v, (pd.Timestamp, datetime.datetime, datetime.date)):
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        return None if (np.isnan(f) or np.isinf(f)) else f
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if pd.isna(v):
        return None
    return v


def _safe_parse_dates(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series

    def _to_ts(v: Any) -> Any:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return pd.NaT
        if isinstance(v, (pd.Timestamp, datetime.datetime, datetime.date)):
            return pd.Timestamp(v)
        s = str(v).strip()
        if not s or s in _EXCEL_ERRORS:
            return pd.NaT
        return pd.to_datetime(s, errors="coerce", format="mixed")

    try:
        return series.apply(_to_ts)
    except Exception:
        return pd.to_datetime(series, errors="coerce", format="mixed")
