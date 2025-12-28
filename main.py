import logging
import signal
import sys

from src.core.config import load_config
from src.core.pipeline import Pipeline
from src.lifecycle.cleanup_scheduler import CleanupScheduler


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = load_config()

    # 啟動清理排程器
    cleanup_scheduler = CleanupScheduler(config)
    cleanup_scheduler.start()

    # 設定訊號處理器，確保優雅關閉
    def signal_handler(_signum: int, _frame: object) -> None:
        logging.info("收到終止訊號，正在關閉...")
        cleanup_scheduler.stop()
        sys.exit(0)

    _ = signal.signal(signal.SIGINT, signal_handler)
    _ = signal.signal(signal.SIGTERM, signal_handler)

    try:
        pipeline = Pipeline(config=config)
        pipeline.run()
    finally:
        cleanup_scheduler.stop()


if __name__ == "__main__":
    main()
