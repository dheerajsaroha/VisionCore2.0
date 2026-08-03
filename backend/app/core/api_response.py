"""
api_response.py — Enterprise Standardized API Response & Problem Details Framework
VisionCore 3.0 Platform Core

Provides:
- Standard JSON Success Response Envelope (data, meta, pagination)
- RFC 7807 Problem Details Error Envelope (type, title, status, detail, instance, correlation_id)
- Standardized Pagination and Filtering Builders
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi.responses import JSONResponse


def success_response(
    data: Any = None,
    meta: Optional[Dict[str, Any]] = None,
    pagination: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
    correlation_id: str = "",
) -> JSONResponse:
    """Returns a standardized JSON success response envelope."""
    payload = {
        "success": True,
        "data": data if data is not None else {},
        "meta": meta or {},
    }
    if pagination:
        payload["pagination"] = pagination
    if correlation_id:
        payload["meta"]["correlation_id"] = correlation_id

    headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


def problem_details_response(
    title: str,
    detail: str,
    status_code: int = 400,
    type_uri: str = "about:blank",
    instance: str = "",
    correlation_id: str = "",
    validation_errors: Optional[List[Dict[str, Any]]] = None,
) -> JSONResponse:
    """Returns an RFC 7807 Problem Details standardized JSON error envelope."""
    payload = {
        "success": False,
        "type": type_uri,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "correlation_id": correlation_id,
    }
    if validation_errors:
        payload["invalid_params"] = validation_errors

    headers = {
        "Content-Type": "application/problem+json",
    }
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id

    return JSONResponse(status_code=status_code, content=payload, headers=headers)


def build_pagination_meta(page: int, page_size: int, total_items: int) -> Dict[str, Any]:
    """Helper to generate standardized pagination metadata."""
    total_pages = (total_items + page_size - 1) // max(page_size, 1) if total_items > 0 else 0
    return {
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }
