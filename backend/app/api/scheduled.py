from datetime import datetime

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException

from ..schemas.scheduled import (
    CronUpdateRequest,
    CronValidationResponse,
    RunAllNowResponse,
    RunNowResponse,
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
)
from ..services.scheduled_download_service import ScheduledDownloadService
from .deps import get_scheduled_download_service

router = APIRouter()


@router.get("/scheduled", response_model=ScheduleListResponse)
async def list_schedules(
    svc: ScheduledDownloadService = Depends(get_scheduled_download_service),
):
    rows = await svc.list_all()
    cron = await svc.get_cron()
    next_run = await svc.get_next_run()
    return ScheduleListResponse(
        scheduled=[_to_response(r) for r in rows],
        cron_expr=cron,
        next_run_at=next_run,
    )


@router.post("/scheduled", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    request: ScheduleCreate,
    svc: ScheduledDownloadService = Depends(get_scheduled_download_service),
):
    try:
        row = await svc.create(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(row)


@router.put("/scheduled/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    update: ScheduleUpdate,
    svc: ScheduledDownloadService = Depends(get_scheduled_download_service),
):
    try:
        row = await svc.update(schedule_id, update)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _to_response(row)


@router.delete("/scheduled/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: int,
    svc: ScheduledDownloadService = Depends(get_scheduled_download_service),
):
    deleted = await svc.delete(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")


@router.post("/scheduled/{schedule_id}/run", response_model=RunNowResponse)
async def run_now(
    schedule_id: int,
    svc: ScheduledDownloadService = Depends(get_scheduled_download_service),
):
    enqueued, reason = await svc.run_now(schedule_id)
    return RunNowResponse(enqueued_episodes=enqueued, skipped_reason=reason)


@router.post("/scheduled/run-all", response_model=RunAllNowResponse)
async def run_all_now(
    svc: ScheduledDownloadService = Depends(get_scheduled_download_service),
):
    total = await svc.run_all_now()
    return RunAllNowResponse(total_enqueued=total)


@router.get("/scheduled/cron")
async def get_cron(
    svc: ScheduledDownloadService = Depends(get_scheduled_download_service),
):
    cron = await svc.get_cron()
    next_run = await svc.get_next_run()
    return {"cron_expr": cron, "next_run_at": next_run}


@router.put("/scheduled/cron")
async def set_cron(
    request: CronUpdateRequest,
    svc: ScheduledDownloadService = Depends(get_scheduled_download_service),
):
    try:
        expr = await svc.set_cron(request.cron_expr)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    next_run = await svc.get_next_run()
    return {"cron_expr": expr, "next_run_at": next_run}


@router.get("/scheduled/validate-cron", response_model=CronValidationResponse)
async def validate_cron(expr: str):
    if not croniter.is_valid(expr):
        return CronValidationResponse(valid=False, error="Invalid cron expression")
    base = datetime.now()
    it = croniter(expr, base)
    nexts = [it.get_next(datetime) for _ in range(3)]
    return CronValidationResponse(valid=True, next_runs=nexts)


def _to_response(row) -> ScheduleResponse:
    return ScheduleResponse(
        id=row.id,
        anime_id=row.anime_id,
        anime_slug=row.anime_slug,
        anime_title=row.anime_title,
        cover_url=row.cover_url,
        source_site=row.source_site,
        dest_folder=row.dest_folder,
        filename_template=row.filename_template,
        filename_template_type=row.filename_template_type,
        enabled=bool(row.enabled),
        last_run_at=row.last_run_at,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
