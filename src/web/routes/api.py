"""
RESTful API 路由

提供事件查詢、系統狀態等 API。
"""

import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from src.web.services.event_service import EventService


router = APIRouter(prefix="/api", tags=["API"])

# 應用程式啟動時間
_start_time = time.time()


def get_event_service() -> EventService:
    """取得事件服務實例"""
    return EventService("data/fds.db")


@router.get("/status")
async def get_status() -> dict:
    """取得系統狀態

    Returns:
        系統狀態資訊
    """
    uptime = time.time() - _start_time

    # 檢查資料庫是否存在
    db_exists = Path("data/fds.db").exists()

    return {
        "status": "running",
        "uptime_seconds": round(uptime, 2),
        "version": "0.1.0",
        "database_connected": db_exists,
    }


@router.get("/stats")
async def get_stats() -> dict:
    """取得事件統計資訊

    Returns:
        統計資訊
    """
    try:
        service = get_event_service()
        stats = service.get_stats()
        return stats.to_dict()
    except FileNotFoundError:
        return {
            "total_events": 0,
            "today_events": 0,
            "this_week_events": 0,
            "total_clips_size_mb": 0.0,
        }


@router.get("/events")
async def get_events(
    page: Annotated[int, Query(ge=1, description="頁碼")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="每頁數量")] = 10,
) -> dict:
    """取得事件列表

    Args:
        page: 頁碼（從 1 開始）
        per_page: 每頁數量（1-100）

    Returns:
        分頁事件列表
    """
    try:
        service = get_event_service()
        events, total = service.get_events(page=page, per_page=per_page)

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "events": [e.to_dict() for e in events],
        }
    except FileNotFoundError:
        return {
            "total": 0,
            "page": page,
            "per_page": per_page,
            "total_pages": 0,
            "events": [],
        }


@router.get("/events/{event_id}")
async def get_event(event_id: str) -> dict:
    """取得單一事件詳情

    Args:
        event_id: 事件 ID

    Returns:
        事件詳情
    """
    try:
        service = get_event_service()
        event = service.get_event(event_id)

        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")

        return event.to_dict()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Database not found")


@router.get("/events/{event_id}/clip")
async def get_event_clip(event_id: str) -> FileResponse:
    """取得事件影片

    Args:
        event_id: 事件 ID

    Returns:
        影片檔案串流
    """
    try:
        service = get_event_service()
        event = service.get_event(event_id)

        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")

        if not event.clip_path:
            raise HTTPException(status_code=404, detail="No clip available")

        clip_path = Path(event.clip_path)
        if not clip_path.exists():
            raise HTTPException(status_code=404, detail="Clip file not found")

        return FileResponse(
            path=clip_path,
            media_type="video/mp4",
            filename=f"{event_id}.mp4",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Database not found")


@router.delete("/events/{event_id}")
async def delete_event(event_id: str) -> dict:
    """刪除事件

    Args:
        event_id: 事件 ID

    Returns:
        刪除結果
    """
    try:
        service = get_event_service()
        success = service.delete_event(event_id)

        if not success:
            raise HTTPException(status_code=404, detail="Event not found")

        return {"success": True, "message": f"Event {event_id} deleted"}
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Database not found")


__all__ = ["router"]
