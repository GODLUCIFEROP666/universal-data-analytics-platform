from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.database import increment_counter, record_analytics_event

from app.analyzer.chart_recommender import recommend_charts_with_warnings
from app.analyzer.export_engine import generate_csv_export, generate_excel_export
from app.analyzer.file_parser import (
    MAX_UPLOAD_BYTES,
    apply_filters,
    get_dataframe_preview,
    inspect_file,
    parse_file_to_df,
    sort_dataframe,
)
from app.analyzer.stats_engine import analyze_dataset

router = APIRouter(prefix="/api", tags=["analytics"])


class FilterPayload(BaseModel):
    search_query: Optional[str] = None
    category_filters: Dict[str, List[str]] = Field(default_factory=dict)
    numeric_ranges: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    date_ranges: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    sort_by: Optional[str] = None
    sort_direction: str = "desc"
    page: int = 1
    page_size: int = 50


@router.post("/upload")
async def upload_inspect(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File size exceeds 50 MB limit.")

    try:
        inspection = inspect_file(contents, file.filename)
        increment_counter("total_uploads")
        record_analytics_event("upload", file.filename, {"format": inspection["format"], "size_bytes": len(contents)})
        return {
            "filename": file.filename,
            "format": inspection["format"],
            "sheets": inspection["sheets"],
            "selected_sheet": inspection["selected_sheet"],
            "size_bytes": len(contents),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(None),
    filters: Optional[str] = Form(None),
    page: int = Form(1),
    page_size: int = Form(50),
    sort_by: Optional[str] = Form(None),
    sort_direction: str = Form("desc"),
) -> Dict[str, Any]:
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File size exceeds 50 MB limit.")

    try:
        df = parse_file_to_df(contents, file.filename, sheet_name)
        payload = _parse_filters(filters)
        payload.page = page
        payload.page_size = page_size
        payload.sort_by = sort_by or payload.sort_by
        payload.sort_direction = sort_direction or payload.sort_direction

        filtered = apply_filters(
            df,
            search_query=payload.search_query,
            category_filters=payload.category_filters,
            numeric_ranges=payload.numeric_ranges,
            date_ranges=payload.date_ranges,
        )
        filtered = sort_dataframe(filtered, payload.sort_by, payload.sort_direction)

        stats = analyze_dataset(filtered)
        stats_warnings: list = stats.pop("warnings", [])

        charts, chart_warnings = recommend_charts_with_warnings(
            filtered, stats["columns"], stats["correlations"]
        )
        all_warnings = stats_warnings + chart_warnings

        preview = get_dataframe_preview(filtered, payload.page, payload.page_size)

        increment_counter("total_analyses")
        record_analytics_event(
            "analyze",
            file.filename or "unnamed",
            {"sheet_name": sheet_name, "total_rows": stats.get("summary", {}).get("total_rows", 0)}
        )

        return {
            "filename": file.filename,
            "sheet_name": sheet_name,
            "analysis": stats,
            "charts": charts,
            "table": preview,
            "available_columns": list(filtered.columns),
            "warnings": all_warnings,
        }
    except HTTPException:
        raise
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).error("Analysis route error: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Analysis failed: {exc}") from exc


@router.post("/export/excel")
async def export_excel(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(None),
    filters: Optional[str] = Form(None),
) -> Response:
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File size exceeds 50 MB limit.")

    try:
        df = parse_file_to_df(contents, file.filename, sheet_name)
        payload = _parse_filters(filters)
        filtered = apply_filters(
            df,
            search_query=payload.search_query,
            category_filters=payload.category_filters,
            numeric_ranges=payload.numeric_ranges,
            date_ranges=payload.date_ranges,
        )
        stats = analyze_dataset(filtered)
        excel_bytes = generate_excel_export(filtered, stats)
        safe_name = file.filename.rsplit(".", 1)[0]
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="Analyzed_{safe_name}.xlsx"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Export failed: {exc}") from exc


@router.post("/export/csv")
async def export_csv(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(None),
    filters: Optional[str] = Form(None),
) -> Response:
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File size exceeds 50 MB limit.")

    try:
        df = parse_file_to_df(contents, file.filename, sheet_name)
        payload = _parse_filters(filters)
        filtered = apply_filters(
            df,
            search_query=payload.search_query,
            category_filters=payload.category_filters,
            numeric_ranges=payload.numeric_ranges,
            date_ranges=payload.date_ranges,
        )
        csv_bytes = generate_csv_export(filtered)
        safe_name = file.filename.rsplit(".", 1)[0]
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="Filtered_{safe_name}.csv"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Export failed: {exc}") from exc


@router.post("/reset")
async def reset_state() -> Dict[str, Any]:
    return {"status": "reset"}


def _parse_filters(raw_filters: Optional[str]) -> FilterPayload:
    if not raw_filters:
        return FilterPayload()
    try:
        data = json.loads(raw_filters)
        if not isinstance(data, dict):
            raise ValueError("Filters payload must be an object.")
        return FilterPayload(**data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid filters payload: {exc}") from exc
