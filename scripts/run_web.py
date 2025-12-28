#!/usr/bin/env python3
"""
啟動 FDS Web Dashboard

Usage:
    uv run python scripts/run_web.py
    uv run python scripts/run_web.py --port 8080
    uv run python scripts/run_web.py --host 0.0.0.0 --port 8000
"""

import argparse

from src.web.app import create_app


def main():
    parser = argparse.ArgumentParser(description="啟動 FDS Web Dashboard")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="綁定的主機位址（預設: 0.0.0.0）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="監聽的埠號（預設: 8000）",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="開啟自動重載（開發模式）",
    )

    args = parser.parse_args()

    import logging
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = create_app()

    print("\n" + "=" * 50)
    print("🌐 FDS Web Dashboard")
    print("=" * 50)
    print(f"  儀表板:     http://localhost:{args.port}")
    print(f"  事件列表:   http://localhost:{args.port}/events")
    print(f"  API 文檔:   http://localhost:{args.port}/docs")
    print("=" * 50)
    print("按 Ctrl+C 停止服務\n")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
