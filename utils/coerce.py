# utils/coerce.py
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _maybe_bytes_to_str(v: Any) -> Any:
    if isinstance(v, (bytes, bytearray)):
        for enc in ("utf-8", "cp949", "latin1"):
            try:
                return v.decode(enc, errors="ignore")
            except Exception:
                pass
    return v


def coerce_json_dict(obj: Any) -> dict:
    """dict가 필요할 때 다양한 입력을 느슨하게 dict로 바꿔줍니다."""
    obj = _maybe_bytes_to_str(obj)

    if obj is None or obj == "":
        return {}
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, Path) and obj.exists():
        return json.loads(obj.read_text(encoding="utf-8"))

    # Streamlit UploadedFile 등 file-like
    if hasattr(obj, "read"):
        try:
            data = obj.read()
            if hasattr(obj, "seek"):
                obj.seek(0)
            return coerce_json_dict(data)
        except Exception:
            pass

    # ("k","v") 쌍 모음 -> dict
    if isinstance(obj, (list, tuple)):
        try:
            return dict(obj)
        except Exception:
            pass

    if isinstance(obj, str):
        s = obj.strip()
        # ```json ... ``` 코드펜스 제거
        s = re.sub(r"^\s*```(?:json)?|```\s*$", "", s, flags=re.MULTILINE)
        for candidate in (s, s.replace("'", '"')):
            try:
                v = json.loads(candidate)
                if isinstance(v, dict):
                    return v
            except Exception:
                pass
    return {}


def coerce_json_list(obj: Any) -> list:
    """list가 필요할 때 다양한 입력을 느슨하게 list로 바꿔줍니다."""
    obj = _maybe_bytes_to_str(obj)

    if obj is None or obj == "":
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, tuple):
        return list(obj)
    if isinstance(obj, Path) and obj.exists():
        return json.loads(obj.read_text(encoding="utf-8"))

    if hasattr(obj, "read"):
        try:
            data = obj.read()
            if hasattr(obj, "seek"):
                obj.seek(0)
            return coerce_json_list(data)
        except Exception:
            pass

    if isinstance(obj, str):
        s = obj.strip()
        s = re.sub(r"^\s*```(?:json)?|```\s*$", "", s, flags=re.MULTILINE)
        for candidate in (s, s.replace("'", '"')):
            try:
                v = json.loads(candidate)
                if isinstance(v, list):
                    return v
                if isinstance(v, dict):
                    return [v]
                return [v]
            except Exception:
                pass
        # 콤마로 구분된 단일 값들에 대한 폴백
        try:
            return json.loads(f"[{s}]")
        except Exception:
            return []
    return []
