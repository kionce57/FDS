"""
FDS Web Dashboard Application

FastAPI 應用程式入口點。
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.web.routes.api import router as api_router
from src.web.routes.pages import router as pages_router


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """建立 FastAPI 應用程式

    Returns:
        FastAPI 應用程式實例
    """
    app = FastAPI(
        title="FDS Web Dashboard",
        description="Fall Detection System 網頁儀表板",
        version="0.1.0",
    )

    # 註冊路由
    app.include_router(api_router)
    app.include_router(pages_router)

    # 掛載靜態檔案
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    logger.info("FDS Web Dashboard 應用程式已建立")

    return app


def main() -> None:
    """啟動 Web Server"""
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = create_app()

    logger.info("啟動 Web Server: http://localhost:8000")
    print("\n" + "=" * 50)
    print("🌐 FDS Web Dashboard")
    print("=" * 50)
    print("  儀表板:     http://localhost:8000")
    print("  事件列表:   http://localhost:8000/events")
    print("  API 文檔:   http://localhost:8000/docs")
    print("=" * 50)
    print("按 Ctrl+C 停止服務\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
