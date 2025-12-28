"""
頁面路由

提供 HTML 頁面渲染。
"""

from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.web.services.event_service import EventService


router = APIRouter(tags=["Pages"])

# 設定模板目錄
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def get_event_service() -> EventService:
    """取得事件服務實例"""
    return EventService("data/fds.db")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """儀表板首頁

    顯示系統狀態、統計資訊和最近事件。
    """
    try:
        service = get_event_service()
        stats = service.get_stats()
        recent_events = service.get_recent_events(limit=5)
        db_connected = True
    except FileNotFoundError:
        stats = None
        recent_events = []
        db_connected = False

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "stats": stats,
            "recent_events": recent_events,
            "db_connected": db_connected,
        },
    )


@router.get("/events", response_class=HTMLResponse)
async def events_list(
    request: Request,
    page: int = 1,
    per_page: int = 10,
) -> HTMLResponse:
    """事件列表頁面

    Args:
        request: FastAPI 請求物件
        page: 頁碼
        per_page: 每頁數量
    """
    try:
        service = get_event_service()
        events, total = service.get_events(page=page, per_page=per_page)
        total_pages = (total + per_page - 1) // per_page
        db_connected = True
    except FileNotFoundError:
        events = []
        total = 0
        total_pages = 0
        db_connected = False

    return templates.TemplateResponse(
        request=request,
        name="events.html",
        context={
            "events": events,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "db_connected": db_connected,
        },
    )


@router.get("/events/{event_id}", response_class=HTMLResponse)
async def event_detail(request: Request, event_id: str) -> HTMLResponse:
    """事件詳情頁面

    Args:
        request: FastAPI 請求物件
        event_id: 事件 ID
    """
    try:
        service = get_event_service()
        event = service.get_event(event_id)

        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")

    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Database not found")

    return templates.TemplateResponse(
        request=request,
        name="event_detail.html",
        context={
            "event": event,
        },
    )


__all__ = ["router"]
