# 🔐 키는 .env로만 관리하세요.
import json
import os
import sys
from pathlib import Path
from typing import Any

# 모듈 경로 보강
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from utils.config import OPENAI_API_KEY

ROOT = Path(__file__).resolve().parents[1]


# ====== Schemas ======
class AdBrief(BaseModel):
    brand: str | None = None
    target: str = Field(..., min_length=1)
    tone: str = Field(..., min_length=1)
    colors: list[str] = Field(default_factory=list)
    format: str = Field(default="9:16")
    offer: str | None = None
    cta: str = Field(..., min_length=1)
    motifs: list[str] = Field(default_factory=list)


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


# ====== Brief ======
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
        brief = AdBrief(**data)
        return brief.model_dump()
    except (json.JSONDecodeError, ValidationError):
        # 안전 폴백
        return AdBrief(
            brand=None,
            target="일반 성인 고객",
            tone="모던",
            colors=["#000000"],
            format="9:16",
            offer=None,
            cta="지금 확인하기",
            motifs=[],
        ).model_dump()


# ====== Shotlist ======
def generate_shotlist(brief: dict[str, Any]) -> list[dict[str, Any]]:
    sys_prompt = _load(ROOT / "prompts" / "shotlist_prompt.md")
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": json.dumps(brief, ensure_ascii=False)},
    ]
    resp = _client().chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=messages,
        temperature=0.3,
    )
    try:
        data = json.loads(resp.choices[0].message.content)
        shots = [Shot(**s).model_dump() for s in data.get("shots", [])]
        # 길이 보정(총합 8~10s로 스케일)
        total = sum(s["dur"] for s in shots)
        if total < 8.0 or total > 10.5:
            scale = 9.0 / max(total, 1e-6)
            t = 0.0
            for s in shots:
                s["dur"] = round(s["dur"] * scale, 2)
                s["t"] = round(t, 2)
                t += s["dur"]
        return shots
    except Exception:
        # 폴백 9.0s
        return [
            {
                "t": 0.0,
                "dur": 2.2,
                "type": "intro",
                "scene": "브랜드 로고 + 대표 컷",
                "caption": "방금 열린 우리 카페",
            },
            {
                "t": 2.2,
                "dur": 4.0,
                "type": "value",
                "scene": "제품 클로즈업",
                "caption": "오픈 기념 20% 할인",
            },
            {
                "t": 6.2,
                "dur": 2.8,
                "type": "cta",
                "scene": "매장 전경/메뉴",
                "caption": "지금 방문하기",
            },
        ]


# ====== Save ======
def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    demo = "카페 오픈 20% 할인. 따뜻하고 감성적인 느낌. 9:16 릴스용."
    brief = generate_brief(demo)
    shots = generate_shotlist(brief)
    save_json(brief, ROOT / "outputs" / "briefs" / "brief_demo.json")
    save_json(shots, ROOT / "outputs" / "briefs" / "shotlist_demo.json")
    print("OK:", brief["tone"], len(shots), "shots")
