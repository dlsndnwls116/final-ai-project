import json
from pathlib import Path


def coerce_json_dict(v):
    """문자열/파일경로 → dict 변환"""
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        # 1) JSON 문자열일 수 있음
        try:
            return json.loads(v)
        except Exception:
            # 2) 파일 경로일 수 있음
            p = Path(v)
            if p.exists():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    pass
    return {}  # 못 만들면 빈 dict


def coerce_json_list(v):
    """문자열/파일경로 → list 변환"""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            obj = json.loads(v)
            return obj if isinstance(obj, list) else []
        except Exception:
            p = Path(v)
            if p.exists():
                try:
                    obj = json.loads(p.read_text(encoding="utf-8"))
                    return obj if isinstance(obj, list) else []
                except Exception:
                    pass
    return []
