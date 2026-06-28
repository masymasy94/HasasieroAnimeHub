import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import settings
from ..schemas.download import DownloadRequest, DownloadStatus, DownloadsResponse
from ..services.download_service import DownloadService
from ..services.nas_queue import NasIOQueue
from .deps import get_download_service, get_nas_queue

router = APIRouter()


def _to_host_path(container_path: str | None) -> str | None:
    if not container_path or not settings.host_download_path:
        return container_path
    container_dir = settings.download_dir.rstrip("/")
    if container_path.startswith(container_dir):
        relative = container_path[len(container_dir):]
        return settings.host_download_path.rstrip("/") + relative
    return container_path


async def _enrich(dl, nas_queue: NasIOQueue) -> DownloadStatus:
    status = DownloadStatus.model_validate(dl)
    status.host_file_path = _to_host_path(status.file_path)
    if status.file_path and status.status == "completed":
        status.file_exists = await nas_queue.check_file_exists(status.file_path)
    else:
        status.file_exists = False
    return status


class DiskUsageResponse(BaseModel):
    total_bytes: int
    used_bytes: int
    free_bytes: int
    path: str
    host_path: str


@router.get("/disk-usage", response_model=DiskUsageResponse)
async def disk_usage(nas_queue: NasIOQueue = Depends(get_nas_queue)):
    info = await nas_queue.get_disk_usage()
    return DiskUsageResponse(
        total_bytes=info["total_bytes"],
        used_bytes=info["used_bytes"],
        free_bytes=info["free_bytes"],
        path=info["path"],
        host_path=settings.host_download_path or info["path"],
    )


@router.post("/downloads", response_model=DownloadsResponse, status_code=201)
async def create_downloads(
    request: DownloadRequest,
    svc: DownloadService = Depends(get_download_service),
    nas_queue: NasIOQueue = Depends(get_nas_queue),
):
    disk = await nas_queue.get_disk_usage()
    estimated_bytes = len(request.episodes) * 500 * 1024 * 1024
    if disk["free_bytes"] < estimated_bytes:
        free_gb = disk["free_bytes"] / (1024**3)
        needed_gb = estimated_bytes / (1024**3)
        raise HTTPException(
            status_code=400,
            detail=f"Spazio insufficiente: {free_gb:.1f} GB liberi, stimati {needed_gb:.1f} GB necessari per {len(request.episodes)} episodi",
        )

    downloads = await svc.enqueue(request)
    enriched = await asyncio.gather(*[_enrich(d, nas_queue) for d in downloads])
    return DownloadsResponse(downloads=list(enriched))


@router.get("/downloads", response_model=DownloadsResponse)
async def list_downloads(
    status: list[str] | None = Query(None),
    svc: DownloadService = Depends(get_download_service),
    nas_queue: NasIOQueue = Depends(get_nas_queue),
):
    downloads = await svc.get_downloads(status)
    enriched = await asyncio.gather(*[_enrich(d, nas_queue) for d in downloads])
    return DownloadsResponse(downloads=list(enriched))


@router.post("/downloads/cancel-all")
async def cancel_all_downloads(svc: DownloadService = Depends(get_download_service)):
    count = await svc.cancel_all()
    return {"cancelled": count}


@router.post("/downloads/clear-completed")
async def clear_completed_downloads(svc: DownloadService = Depends(get_download_service)):
    count = await svc.clear_completed()
    return {"cleared": count}


@router.post("/downloads/pause-all")
async def pause_all_downloads(svc: DownloadService = Depends(get_download_service)):
    count = await svc.pause_all()
    return {"paused": count}


@router.post("/downloads/resume-all")
async def resume_all_downloads(svc: DownloadService = Depends(get_download_service)):
    count = await svc.resume_all()
    return {"resumed": count}


@router.post("/downloads/retry-all-failed")
async def retry_all_failed(svc: DownloadService = Depends(get_download_service)):
    count = await svc.retry_all_failed()
    return {"retried": count}


@router.delete("/downloads/{download_id}", status_code=204)
async def delete_download(
    download_id: int,
    svc: DownloadService = Depends(get_download_service),
):
    deleted = await svc.delete_download(download_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Download not found")


@router.post("/downloads/{download_id}/pause")
async def pause_download(
    download_id: int,
    svc: DownloadService = Depends(get_download_service),
):
    paused = await svc.pause_download(download_id)
    if not paused:
        raise HTTPException(
            status_code=400,
            detail="Download cannot be paused (not queued/downloading)",
        )
    return {"status": "paused"}


@router.post("/downloads/{download_id}/resume")
async def resume_download(
    download_id: int,
    svc: DownloadService = Depends(get_download_service),
):
    resumed = await svc.resume_download(download_id)
    if not resumed:
        raise HTTPException(
            status_code=400,
            detail="Download cannot be resumed (not paused)",
        )
    return {"status": "queued"}


@router.post("/downloads/{download_id}/retry")
async def retry_download(
    download_id: int,
    svc: DownloadService = Depends(get_download_service),
):
    retried = await svc.retry_download(download_id)
    if not retried:
        raise HTTPException(
            status_code=400,
            detail="Download cannot be retried (not in failed/cancelled state)",
        )
    return {"status": "queued"}


@router.get("/downloads/{download_id}/file")
async def serve_file(
    download_id: int,
    svc: DownloadService = Depends(get_download_service),
):
    downloads = await svc.get_downloads()
    download = next((d for d in downloads if d.id == download_id), None)
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")
    if download.status != "completed" or not download.file_path:
        raise HTTPException(status_code=400, detail="File not available")
    path = Path(download.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="video/mp4",
    )
