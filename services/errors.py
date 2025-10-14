# services/errors.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class ErrorCode(str, Enum):
    MISSING_PRODUCT      = "A100"
    PRODUCT_IO_ERROR     = "A110"
    REF_ANALYSIS_FAILED  = "A200"
    CUT_DETECT_FAILED    = "A210"
    MOTION_EST_FAILED    = "A220"
    ASSET_RESOLVE_FAILED = "A300"
    RENDER_FAILED        = "A400"
    EXTERNAL_API_FAIL    = "A500"
    CONFIG_MISSING_KEY   = "A700"
    UNKNOWN              = "A999"

@dataclass
class AdGenError(Exception):
    code: ErrorCode
    msg: str
    hint: str | None = None
    detail: str | None = None
    correlation_id: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.msg}"
