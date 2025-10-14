import json
from pathlib import Path
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from utils.config import OPENAI_API_KEY

ROOT = Path(__file__).resolve().parents[1]


# ===== Schemas =====
class AdBrief(BaseModel):
    brand: str | None = None
    target: str
    tone: str
    colors: list[str] = []
    format: str = "9:16"
    offer: str | None = None
    cta: str
    motifs: list[str] = []


class Shot(BaseModel):
    t: float
    dur: float
    type: str
    scene: str
    caption: str


def _load(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY)


# ===== Brief =====
def generate_brief(user_text: str, ref_desc: str | None = None) -> dict[str, Any]:
    sys_prompt = _load(ROOT / "prompts" / "intent_prompt.md")
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"요구사항:\n{user_text}"},
    ]
    if ref_desc:
        messages.append({"role": "user", "content": f"레퍼런스 설명:\n{ref_desc}"})
    resp = _client().chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=messages,
        temperature=0.2,
    )
    raw = resp.choices[0].message.content
    try:
        data = json.loads(raw)
        return AdBrief(**data).model_dump()
    except (json.JSONDecodeError, ValidationError):
        # 폴백
        return AdBrief(target="일반 고객", tone="모던", cta="지금 확인하기").model_dump()


# ===== Shotlist =====
def generate_shotlist(brief: dict[str, Any]) -> list[dict[str, Any]]:
    sys_prompt = _load(ROOT / "prompts" / "shotlist_prompt.md")
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": json.dumps(brief, ensure_ascii=False)},
    ]
    resp = _client().chat.completions.create(
        model="gpt-4o-mini",
        # json_array -> json_object 로 변경
        response_format={"type": "json_object"},
        messages=messages,
        temperature=0.3,
    )
    raw = resp.choices[0].message.content

    try:
        obj = json.loads(raw) if isinstance(raw, str) else raw
        shots_raw = obj.get("shots", [])
        shots = [Shot(**s).model_dump() for s in shots_raw]

        # 길이 보정(총 8~10초)
        total = sum(s["dur"] for s in shots)
        if not 8.0 <= total <= 10.5 and total > 0:
            scale = 9.0 / total
            t = 0.0
            for s in shots:
                s["dur"] = round(s["dur"] * scale, 2)
                s["t"] = round(t, 2)
                t += s["dur"]
        return shots

    except Exception:
        # 폴백
        return [
            {
                "t": 0.0,
                "dur": 2.2,
                "type": "intro",
                "scene": "로고+대표컷",
                "caption": "방금 열린 우리 카페",
            },
            {
                "t": 2.2,
                "dur": 4.0,
                "type": "value",
                "scene": "제품 클로즈업",
                "caption": "오픈 20% 할인",
            },
            {"t": 6.2, "dur": 2.8, "type": "cta", "scene": "매장 전경", "caption": "지금 방문하기"},
        ]


# ===== Save =====
def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
