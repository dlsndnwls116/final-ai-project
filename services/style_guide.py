import json
from collections import Counter
from pathlib import Path
from typing import Any

from openai import OpenAI
from PIL import Image

from utils.config import OPENAI_API_KEY

ROOT = Path(__file__).resolve().parents[1]


# ── Palette 추출(로컬 이미지 → HEX) ──
def _dominant_colors(path: Path, k: int = 5) -> list[str]:
    img = Image.open(path).convert("RGB").resize((256, 256))
    pal = img.quantize(colors=k, method=Image.MEDIANCUT)
    raw = pal.getpalette()[: k * 3]
    hexes = []
    for i in range(0, len(raw), 3):
        r, g, b = raw[i : i + 3]
        hexes.append(f"#{r:02X}{g:02X}{b:02X}")
    # 중복 제거, 순서 유지
    seen = []
    for h in hexes:
        if h not in seen:
            seen.append(h)
    return seen[:k]


def extract_palette(image_paths: list[Path], k: int = 5) -> list[str]:
    """
    여러 이미지에서 팔레트 추출 (KMeans)
    많은 프레임 처리 시 샘플링으로 최적화
    """
    if not image_paths:
        return ["#F5EDE0", "#2C2C2C"]  # 기본 팔레트

    # 프레임이 많으면 샘플링으로 처리 속도 향상
    max_samples = 40  # 최대 40장만 처리
    if len(image_paths) > max_samples:
        # 시간 순서로 균등 샘플링
        step = len(image_paths) // max_samples
        image_paths = image_paths[::step][:max_samples]

    all_hex = []
    from utils.diagnostics import heartbeat, loop_guard
    
    guard = loop_guard("extract_palette", max_iter=len(image_paths) * 2, warn_every=5)
    for i, p in enumerate(image_paths):
        heartbeat("extract_palette")
        guard.tick({"image_index": i, "total_images": len(image_paths), "hex_count": len(all_hex)})
        
        try:
            all_hex += _dominant_colors(p, k=min(k, 5))
        except Exception:
            continue
    if not all_hex:
        return ["#F5EDE0", "#2C2C2C"]  # 기본 팔레트
    cnt = Counter(all_hex)
    return [h for h, _ in cnt.most_common(6)]


# ── LLM 호출 ──
def _client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY)


def summarize_style(
    brief: dict[str, Any], palette: list[str], keywords: str | None = None
) -> dict[str, Any]:
    sys_prompt = (ROOT / "prompts" / "style_prompt.md").read_text(encoding="utf-8")
    user = {"brief": brief, "palette": palette, "keywords": keywords or ""}
    resp = _client().chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        temperature=0.2,
    )
    raw = resp.choices[0].message.content
    try:
        return json.loads(raw)
    except Exception:
        # 안전 폴백
        return {
            "palette": palette[:4],
            "font": {
                "family": "Pretendard",
                "weight": "600",
                "fallback": ["Arial", "Noto Sans KR"],
            },
            "caption": {"align": "center", "max_chars": 16, "shadow": True, "bg_opacity": 0.15},
            "motion": {"transition": "crossfade", "speed": "natural", "cut_rhythm": "3-beat"},
            "mood": ["따뜻함", "감성"],
            "music": {"bpm": "80-100", "mood": "warm lo-fi"},
            "cta_style": {"shape": "rounded", "bg": "#000000", "fg": "#FFFFFF"},
        }


# ── 오버레이 플랜(자막 배치/스타일) ──
def build_overlay_plan(shots: list[dict[str, Any]], style: dict[str, Any]) -> list[dict[str, Any]]:
    from utils.diagnostics import heartbeat, loop_guard
    
    align = style.get("caption", {}).get("align", "center")
    bg_op = float(style.get("caption", {}).get("bg_opacity", 0.15))
    plan = []
    
    guard = loop_guard("build_overlay_plan", max_iter=len(shots) * 2, warn_every=10)
    for i, s in enumerate(shots):
        heartbeat("build_overlay_plan")
        guard.tick({"shot_index": i, "total_shots": len(shots), "plan_count": len(plan)})
        
        # 안전장치: s가 dict가 아닌 경우 처리
        if not isinstance(s, dict):
            continue

        plan.append(
            {
                "t": round(float(s.get("t", 0.0)), 2),
                "dur": round(float(s.get("dur", 1.5)), 2),
                "text": s.get("caption", ""),
                "pos": "center" if align == "center" else "bottom",
                "font": style.get("font", {}),
                "fg": "#FFFFFF" if align == "center" else "#111111",
                "bg": style.get("cta_style", {}).get("bg", "#000000"),
                "bg_opacity": bg_op,
            }
        )
    return plan


def save_json(obj: Any, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
