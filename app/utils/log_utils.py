import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name="adgen"):
    """파일+콘솔 로거 생성 (UTF-8, 로테이션)"""
    logdir = Path("logs")
    logdir.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # 중복 방지

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # 파일 핸들러 (로테이션)
    fh = RotatingFileHandler(
        logdir / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)

    # 콘솔 핸들러
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
