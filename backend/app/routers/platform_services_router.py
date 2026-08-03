"""
platform_services_router.py — Enterprise Platform Services REST API Layer
VisionCore 3.0 Enterprise Platform Services Layer

Exposes unified REST API endpoints for:
- Enterprise Search Service
- Enterprise File Management Service
- Event Bus Status & Replay
- Background Job Engine (enqueue, status, cancel)
- Business Calendar Service
- Localization Service
- Import/Export Framework
- Business Rules Engine
- Extension Manager (Plugin Registry)
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.services.search_service import search_service, SearchDocument
from app.services.file_service import file_service
from app.services.event_bus import event_bus
from app.services.job_engine import job_engine, JobPriority
from app.services.business_calendar_service import business_calendar_service, WorkingDayConfig, HolidayEntry, DayType
from app.services.localization_service import localization_service
from app.services.import_export_engine import import_export_engine
from app.services.business_rules_engine import business_rules_engine
from app.services.extension_manager import extension_manager

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
#  Schema Models
# =============================================================================

class SearchRequest(BaseModel):
    query: str
    entity_types: Optional[List[str]] = None
    limit: int = 50
    offset: int = 0


class IndexDocumentRequest(BaseModel):
    id: str
    entity_type: str
    title: str
    content: str
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class EnqueueJobRequest(BaseModel):
    name: str
    handler_type: str
    payload: Dict[str, Any]
    priority: str = "NORMAL"


class AddHolidayRequest(BaseModel):
    date: str
    name: str
    country_code: Optional[str] = None
    is_optional: bool = False


class WorkingDayConfigRequest(BaseModel):
    working_days: List[int] = [0, 1, 2, 3, 4]
    timezone: str = "Asia/Kolkata"
    standard_hours_per_day: float = 8.0


class TranslateRequest(BaseModel):
    key: str
    locale: Optional[str] = None
    kwargs: Optional[Dict[str, str]] = None


class RuleEvaluateRequest(BaseModel):
    rule_set: str
    context: Dict[str, Any]
    simulation: bool = False


class ActivatePluginRequest(BaseModel):
    plugin_id: str


# =============================================================================
#  1. Enterprise Search
# =============================================================================

@router.post("/search", summary="Cross-module hybrid enterprise search")
def platform_search(
    request: SearchRequest,
    current_user=Depends(get_current_user),
):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    result = search_service.search(
        query=request.query,
        organization_id=org_id,
        user_id=current_user.id,
        entity_types=request.entity_types,
        limit=request.limit,
        offset=request.offset,
    )
    return {
        "success": True,
        "data": {
            "query": result.query,
            "total": result.total,
            "results": [
                {
                    "id": r.id,
                    "entity_type": r.entity_type,
                    "title": r.title,
                    "snippet": r.snippet,
                    "score": r.score,
                    "highlights": r.highlights,
                    "metadata": r.metadata,
                }
                for r in result.results
            ],
            "facets": result.facets,
            "search_type": result.search_type,
            "execution_time_ms": result.execution_time_ms,
        },
    }


@router.get("/search/autocomplete", summary="Get autocomplete suggestions")
def search_autocomplete(
    prefix: str = Query(..., min_length=1),
    current_user=Depends(get_current_user),
):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    suggestions = search_service.autocomplete(prefix, org_id)
    return {"success": True, "data": {"suggestions": suggestions}}


@router.post("/search/index", summary="Index a document for search")
def index_document(
    request: IndexDocumentRequest,
    current_user=Depends(get_current_user),
):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    doc = SearchDocument(
        id=request.id,
        entity_type=request.entity_type,
        organization_id=org_id,
        title=request.title,
        content=request.content,
        tags=request.tags or [],
        metadata=request.metadata or {},
    )
    indexed = search_service.index(doc)
    return {"success": True, "data": {"indexed": indexed}}


# =============================================================================
#  2. File Management
# =============================================================================

@router.post("/files/upload", summary="Upload a file to enterprise file store")
async def upload_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    content = await file.read()
    meta = file_service.upload_file(
        filename=file.filename,
        content=content,
        organization_id=org_id,
        content_type=file.content_type or "application/octet-stream",
        uploaded_by=current_user.id,
    )
    return {
        "success": True,
        "data": {
            "file_id": meta.id,
            "filename": meta.filename,
            "size_bytes": meta.size_bytes,
            "sha256_hash": meta.sha256_hash,
            "content_type": meta.content_type,
            "created_at": meta.created_at,
        },
    }


@router.get("/files/{file_id}/signed-url", summary="Get a signed download URL for a file")
def get_signed_url(
    file_id: str,
    expiration_seconds: int = Query(3600, ge=60, le=86400),
    current_user=Depends(get_current_user),
):
    try:
        signed_url = file_service.get_signed_url(file_id, expiration_seconds)
        return {"success": True, "data": {"signed_url": signed_url, "expires_in": expiration_seconds}}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found")


@router.delete("/files/{file_id}", summary="Delete a file from enterprise file store")
def delete_file(file_id: str, current_user=Depends(get_current_user)):
    try:
        deleted = file_service.delete_file(file_id, user_id=current_user.id)
        return {"success": True, "data": {"deleted": deleted}}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found")


# =============================================================================
#  3. Background Job Engine
# =============================================================================

@router.post("/jobs/enqueue", summary="Enqueue a background job")
def enqueue_job(
    request: EnqueueJobRequest,
    current_user=Depends(get_current_user),
):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    priority_map = {
        "LOW": JobPriority.LOW, "NORMAL": JobPriority.NORMAL,
        "HIGH": JobPriority.HIGH, "CRITICAL": JobPriority.CRITICAL,
    }
    priority = priority_map.get(request.priority.upper(), JobPriority.NORMAL)
    try:
        job = job_engine.enqueue_job(
            name=request.name,
            organization_id=org_id,
            handler_type=request.handler_type,
            payload=request.payload,
            priority=priority,
        )
        return {
            "success": True,
            "data": {
                "job_id": job.id,
                "name": job.name,
                "status": job.status.value,
                "priority": job.priority.name,
                "progress": job.progress_percentage,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}", summary="Get background job status")
def get_job_status(job_id: str, current_user=Depends(get_current_user)):
    try:
        job = job_engine.get_job(job_id)
        return {
            "success": True,
            "data": {
                "job_id": job.id,
                "name": job.name,
                "status": job.status.value,
                "progress": job.progress_percentage,
                "result": job.result,
                "error": job.error_message,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
            },
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")


@router.delete("/jobs/{job_id}", summary="Cancel a background job")
def cancel_job(job_id: str, current_user=Depends(get_current_user)):
    cancelled = job_engine.cancel_job(job_id, user_id=current_user.id)
    return {"success": True, "data": {"cancelled": cancelled}}


# =============================================================================
#  4. Business Calendar
# =============================================================================

@router.get("/calendar/working-days", summary="Count working days in a date range")
def count_working_days(
    start_date: str = Query(...),
    end_date: str = Query(...),
    current_user=Depends(get_current_user),
):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    count = business_calendar_service.count_working_days(start, end, org_id)
    return {"success": True, "data": {"working_days": count, "from": start_date, "to": end_date}}


@router.get("/calendar/holidays", summary="Get organization holiday calendar")
def get_holidays(
    year: Optional[int] = Query(None),
    current_user=Depends(get_current_user),
):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    holidays = business_calendar_service.get_holidays(org_id, year=year)
    return {
        "success": True,
        "data": {
            "holidays": [{"date": h.date, "name": h.name, "type": h.type.value} for h in holidays]
        },
    }


@router.post("/calendar/holidays", summary="Add a holiday to organization calendar")
def add_holiday(request: AddHolidayRequest, current_user=Depends(get_current_user)):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    entry = HolidayEntry(
        date=request.date,
        name=request.name,
        type=DayType.OPTIONAL_HOLIDAY if request.is_optional else DayType.HOLIDAY,
        country_code=request.country_code,
        is_optional=request.is_optional,
    )
    business_calendar_service.add_holiday(org_id, entry)
    return {"success": True, "data": {"added": True, "date": request.date, "name": request.name}}


@router.get("/calendar/fiscal-year", summary="Get fiscal year for today or a specific date")
def get_fiscal_year(
    for_date: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    d = date.fromisoformat(for_date) if for_date else date.today()
    fy = business_calendar_service.get_fiscal_year(d, org_id)
    quarter = business_calendar_service.get_fiscal_quarter(d, org_id)
    return {"success": True, "data": {**fy, **quarter}}


# =============================================================================
#  5. Localization
# =============================================================================

@router.post("/i18n/translate", summary="Translate a platform string key")
def translate_key(request: TranslateRequest, current_user=Depends(get_current_user)):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    result = localization_service.translate(
        key=request.key,
        locale=request.locale,
        organization_id=org_id,
        user_id=current_user.id,
        **(request.kwargs or {}),
    )
    return {"success": True, "data": {"key": request.key, "value": result}}


@router.get("/i18n/locales", summary="Get supported locales")
def get_locales(current_user=Depends(get_current_user)):
    return {"success": True, "data": {"locales": localization_service.get_supported_locales()}}


# =============================================================================
#  6. Import / Export
# =============================================================================

@router.post("/import/csv", summary="Bulk import data from CSV upload")
async def import_csv(
    schema_name: str = Query(...),
    preview_only: bool = Query(False),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    content = await file.read()
    result = import_export_engine.import_csv(
        content=content,
        schema_name=schema_name,
        organization_id=org_id,
        user_id=current_user.id,
        preview_only=preview_only,
    )
    return {
        "success": True,
        "data": {
            "job_id": result.job_id,
            "status": result.status.value,
            "total_rows": result.total_rows,
            "success_rows": result.success_rows,
            "failed_rows": result.failed_rows,
            "errors": [{"row": e.row, "field": e.field, "message": e.message} for e in result.errors],
            "preview": result.preview_data,
        },
    }


@router.get("/export/csv", summary="Export data as CSV")
def export_csv(
    schema_name: str = Query(...),
    current_user=Depends(get_current_user),
):
    # Placeholder: real endpoint would accept filter params & fetch data from DB
    sample_data = [{"employee_id": "EMP001", "full_name": "Demo User", "email": "demo@example.com", "status": "active"}]
    org_id = str(getattr(current_user, "organization_id", "") or "")
    result = import_export_engine.export_csv(sample_data, schema_name, org_id, current_user.id)
    return Response(
        content=result.content,
        media_type=result.mime_type,
        headers={"Content-Disposition": f"attachment; filename={result.filename}"},
    )


@router.get("/export/json", summary="Export data as JSON")
def export_json(
    schema_name: str = Query(...),
    current_user=Depends(get_current_user),
):
    sample_data = [{"employee_id": "EMP001", "full_name": "Demo User", "email": "demo@example.com"}]
    org_id = str(getattr(current_user, "organization_id", "") or "")
    result = import_export_engine.export_json(sample_data, schema_name, org_id, current_user.id)
    return Response(
        content=result.content,
        media_type=result.mime_type,
        headers={"Content-Disposition": f"attachment; filename={result.filename}"},
    )


# =============================================================================
#  7. Business Rules Engine
# =============================================================================

@router.post("/rules/evaluate", summary="Evaluate a rule set against a context")
def evaluate_rules(request: RuleEvaluateRequest, current_user=Depends(get_current_user)):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    report = business_rules_engine.evaluate(
        rule_set=request.rule_set,
        context=request.context,
        organization_id=org_id,
        user_id=current_user.id,
        simulation=request.simulation,
    )
    return {
        "success": True,
        "data": {
            "rule_set": report.rule_set,
            "total_rules": report.total_rules,
            "matched_rules": report.matched_rules,
            "simulation": report.simulation,
            "final_context": report.final_context,
            "results": [
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "matched": r.matched,
                    "actions_executed": r.actions_executed,
                }
                for r in report.results
            ],
        },
    }


@router.get("/rules", summary="List all rules for a rule set")
def list_rules(
    rule_set: str = Query(...),
    current_user=Depends(get_current_user),
):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    rules = business_rules_engine.get_rules_for_set(rule_set, org_id)
    return {
        "success": True,
        "data": {
            "rule_set": rule_set,
            "rules": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "priority": r.priority,
                    "is_active": r.is_active,
                    "version": r.version,
                }
                for r in rules
            ],
        },
    }


# =============================================================================
#  8. Extension Manager (Plugin Registry)
# =============================================================================

@router.get("/plugins", summary="List all registered platform plugins")
def list_plugins(current_user=Depends(get_current_user)):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    plugins = extension_manager.list_plugins()
    return {
        "success": True,
        "data": {
            "plugins": [
                {
                    "plugin_id": p.metadata.plugin_id,
                    "name": p.metadata.name,
                    "version": p.metadata.version,
                    "description": p.metadata.description,
                    "status": p.status.value,
                    "hooks": p.metadata.hooks,
                    "provides": p.metadata.provides,
                }
                for p in plugins
            ]
        },
    }


@router.get("/plugins/hooks", summary="List all supported platform lifecycle hooks")
def list_hooks(current_user=Depends(get_current_user)):
    return {"success": True, "data": {"hooks": extension_manager.get_available_hooks()}}


@router.post("/plugins/{plugin_id}/activate", summary="Activate a plugin for this organization")
def activate_plugin(plugin_id: str, current_user=Depends(get_current_user)):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    try:
        record = extension_manager.activate_plugin(plugin_id, organization_id=org_id, user_id=current_user.id)
        return {"success": True, "data": {"plugin_id": plugin_id, "status": record.status.value}}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/plugins/{plugin_id}/deactivate", summary="Deactivate a plugin for this organization")
def deactivate_plugin(plugin_id: str, current_user=Depends(get_current_user)):
    org_id = str(getattr(current_user, "organization_id", "") or "")
    result = extension_manager.deactivate_plugin(plugin_id, organization_id=org_id, user_id=current_user.id)
    return {"success": True, "data": {"deactivated": result}}
