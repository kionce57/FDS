import logging

from src.core.config import load_config
from src.core.pipeline import Pipeline


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = load_config()
    pipeline = Pipeline(config=config)
    pipeline.run()


if __name__ == "__main__":
    main()
