# services/guard.py
from __future__ import annotations
import functools, logging, traceback, uuid
from .errors import AdGenError, ErrorCode

def guarded(step: str, code: ErrorCode = ErrorCode.UNKNOWN):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except AdGenError:
                raise
            except Exception as e:
                cid = uuid.uuid4().hex[:12]
                logging.exception("Unhandled error at %s cid=%s", step, cid)
                raise AdGenError(
                    code=code, msg=f"{step} 실패",
                    hint="오류 상세는 로그/아래 상세보기에서 확인하세요.",
                    detail=traceback.format_exc(), correlation_id=cid
                )
        return wrapper
    return deco
