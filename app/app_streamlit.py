# 🔐 민감정보는 .env에서만, 화면/로그 노출 금지
import os as _os

import streamlit as st

# repo 루트 경로를 모듈 경로에 추가 (루트에서 실행이 아닐 수도 있어서)
from pathlib import Path
import sys
ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 에러 타입 import
try:
    from services.errors import AdGenError, ErrorCode
except Exception:
    # 최후의 안전장치: import 실패해도 NameError는 안 나게 최소 스텁 제공
    from enum import Enum
    class ErrorCode(str, Enum):
        UNKNOWN = "A999"
    class AdGenError(Exception):
        def __init__(self, code: ErrorCode = ErrorCode.UNKNOWN, msg="", hint=None, detail=None, correlation_id=None):
            self.code, self.msg, self.hint, self.detail, self.correlation_id = code, msg, hint, detail, correlation_id
        def __str__(self):
            return f"{self.code}: {self.msg}"

# ✅ one_click_make 가져오기
try:
    from services.pipeline_oneclick import one_click_make
except Exception:
    # 안전 스텁: import 실패 시 명확한 메시지
    def one_click_make(*args, **kwargs):
        raise AdGenError(ErrorCode.UNKNOWN, "one_click_make() 미구현",
                         hint="services/pipeline_oneclick.py 를 생성하고 __all__ 에 one_click_make를 노출하세요.")

# 진단 시스템 초기화

try:
    from utils.diagnostics import start_watchdog
    start_watchdog(timeout=90)  # 90초 동안 heartbeat 없으면 덤프
except ImportError as e:
    print(f"Warning: 진단 시스템 로드 실패: {e}")

# Windows cp949 디코딩 에러 방지 + 로그 안정화
_os.environ["PYTHONIOENCODING"] = "utf-8"
import logging as _pylog

# Windows 인코딩 안정화
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 로깅 시스템 안정화
_pylog.basicConfig(
    level=_pylog.INFO, 
    encoding="utf-8", 
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ── 루트 경로 주입(반드시 최상단) ───────────────────────────
APP_DIR = Path(__file__).resolve().parent  # .../app
ROOT = APP_DIR.parent  # 프로젝트 루트
UTILS_DIR = ROOT / "utils"
assert UTILS_DIR.exists(), f"missing: {UTILS_DIR}"  # 파일 유무(친절 메시지)

if str(ROOT) not in sys.path:  # ★ import 경로 보정(핵심)
    sys.path.insert(0, str(ROOT))
    print(f"[DEBUG] Added to sys.path: {ROOT}")
    print(f"[DEBUG] Current sys.path[0]: {sys.path[0]}")
else:
    print(f"[DEBUG] ROOT already in sys.path: {ROOT}")

# PIL 기반 텍스트 렌더링 설정 (ImageMagick 의존성 제거)
try:
    from PIL import Image, ImageDraw, ImageFont

    print("[INFO] PIL-based text rendering enabled (no ImageMagick required)")
except ImportError:
    print("[WARNING] PIL not available. Text overlays may not work.")
    print("[INFO] Please install Pillow: pip install Pillow")

# 안전장치: utils.config가 없거나 환경변수만 사용하는 경우
try:
    from utils.config import OPENAI_API_KEY
except Exception:
    from dotenv import load_dotenv

    load_dotenv()
    OPENAI_API_KEY = _os.getenv("OPENAI_API_KEY", "")
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY가 없습니다. utils/config.py 또는 .env/환경변수에 키를 설정하세요."
        )

# 로깅 시스템
from utils.coerce import coerce_json_dict, coerce_json_list

LOG = _pylog.getLogger("adgen")
LOG.info("App booted")


# 타입 강제 변환 함수
def _coerce_json_dict(v):
    """문자열을 dict로 안전하게 변환"""
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            d = jsonlib.loads(v)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}
    return {}

def _coerce_json_list(v):
    """문자열을 list로 안전하게 변환"""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            d = jsonlib.loads(v)
            return d if isinstance(d, list) else []
        except Exception:
            return []
    return []


# 레시피 관리 함수들
def _ensure_dir(p: Path):
    """디렉토리 생성"""
    p.mkdir(parents=True, exist_ok=True)


def save_recipe(recipe: dict):
    """레시피를 세션과 디스크에 저장"""
    import time

    rdir = ROOT / "outputs" / "recipes"
    _ensure_dir(rdir)
    ts = int(time.time())
    latest = rdir / "recipe_latest.json"
    path = rdir / f"recipe_{ts}.json"
    txt = jsonlib.dumps(recipe, ensure_ascii=False, indent=2)
    latest.write_text(txt, encoding="utf-8")
    path.write_text(txt, encoding="utf-8")
    # 세션에도 보관
    st.session_state["recipe"] = recipe
    st.session_state["recipe_path"] = str(latest)  # 항상 최신 파일 경로
    LOG.info("[RECIPE] saved -> %s", latest)


def load_json(p: Path):
    """JSON 파일 로드"""
    return jsonlib.loads(p.read_text(encoding="utf-8"))


def find_latest_recipe() -> dict | None:
    """레시피를 찾는 함수 (세션 → 지정 경로 → 최신 파일 스캔)"""
    # 1) 세션
    r = st.session_state.get("recipe")
    if isinstance(r, dict) and r:
        LOG.info("[RECIPE] found in session")
        return r
    # 2) 세션 경로
    rp = st.session_state.get("recipe_path")
    if rp and Path(rp).exists():
        LOG.info("[RECIPE] found in session path: %s", rp)
        return load_json(Path(rp))
    # 3) 디스크 스캔
    rdir = ROOT / "outputs" / "recipes"
    if rdir.exists():
        if (rdir / "recipe_latest.json").exists():
            LOG.info("[RECIPE] found latest file")
            return load_json(rdir / "recipe_latest.json")
        files = sorted(rdir.glob("recipe_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            LOG.info("[RECIPE] found most recent: %s", files[0])
            return load_json(files[0])
    LOG.warning("[RECIPE] not found anywhere")
    return None


def normalize_recipe(recipe: dict, uploaded_assets: dict | None = None) -> dict:
    """Bring recipe to renderer schema:
    - convert {"in":.., "out":..} -> {"t":[..,..]} AND keep both formats for compatibility
    - ensure assets has keys: product, store, broll1, broll2 (fallback mapping)
    - clamp/repair durations
    """
    import copy

    r = copy.deepcopy(recipe)

    # 1) timeline: in/out -> t, 그리고 t -> in/out 동시 유지 (호환성)
    for s in r.get("timeline", []):
        # t가 없고 in/out이 있으면 t 생성
        if "t" not in s:
            if "in" in s and "out" in s:
                s["t"] = [float(s.pop("in")), float(s.pop("out"))]
            else:
                s["t"] = [0.0, 0.0]
        # 여기서 반드시 in/out도 같이 유지 (구 코드 호환)
        s["in"], s["out"] = float(s["t"][0]), float(s["t"][1])

    # 2) assets 키 보정: 업로더-state에서 적절히 끌어오거나, 가진 것들로 대체
    assets = r.setdefault("assets", {})

    # 업로더 상태를 전달받았다면(선택)
    def _first_id(key):
        v = (uploaded_assets or {}).get(key)
        if isinstance(v, list) and v:
            return v[0].get("file_id") or v[0].get("id")
        if isinstance(v, dict):
            return v.get("file_id") or v.get("id")
        return None

    # product 유지/보강
    assets.setdefault("product", _first_id("upload_product_shot"))

    # broll 후보 풀 만들기 (업로더에서 온 애들 + 이미 assets에 있던 해시 키들)
    broll_pool = []
    for k in ("upload_broll", "upload_broll_2", "upload_broll_3"):
        vv = (uploaded_assets or {}).get(k) or []
        if isinstance(vv, dict):
            vv = [vv]
        for it in vv:
            fid = it.get("file_id") or it.get("id")
            if fid:
                broll_pool.append(fid)
    # assets에 이미 있는 해시형 키도 예비풀로
    for k in list(assets.keys()):
        if len(k) > 20 and isinstance(assets[k], str):
            broll_pool.append(assets[k])

    # 사용 가능한 자산들을 수집 (실제 파일 경로)
    available_assets = []
    for k, v in assets.items():
        if isinstance(v, str) and Path(v).exists():
            available_assets.append(v)

    # product 자산 찾기 (1-소스 모드 지원)
    if "product" not in assets or not assets["product"] or not Path(assets["product"]).exists():
        # 1-소스 모드용 product 폴더에서 찾기
        product_dir = ASSET_DIR / "product"
        if product_dir.exists():
            product_files = list(product_dir.glob("*"))
            if product_files:
                assets["product"] = str(product_files[0])
        # 기존 방식으로 fallback
        elif available_assets:
            assets["product"] = available_assets[0]

    # store/broll1/broll2 할당 (사용 가능한 자산들을 순서대로)
    if len(available_assets) >= 1:
        assets.setdefault("store", available_assets[0])
    if len(available_assets) >= 2:
        assets.setdefault("broll1", available_assets[1])
    if len(available_assets) >= 3:
        assets.setdefault("broll2", available_assets[2])

    # 부족한 키들은 product로 대체
    assets.setdefault("store", assets.get("product"))
    assets.setdefault("broll1", assets.get("product"))
    assets.setdefault("broll2", assets.get("product"))

    # 3) shot/layer 길이 보정 (in/out 기준으로)
    for s in r.get("timeline", []):
        start, end = float(s["in"]), float(s["out"])
        if end - start <= 0:
            end = start + 2.0
            s["t"] = [start, end]
            s["in"] = start
            s["out"] = end
        # 레이어 dur 누락/0 보정
        for lyr in s.get("layers", []):
            if lyr.get("type") == "video":
                if not lyr.get("dur") or lyr["dur"] <= 0:
                    lyr["dur"] = end - start
    return r


def shot_bounds(s):
    """샷의 시간 범위를 안전하게 가져오기 (t 또는 in/out 호환)"""
    if "t" in s and isinstance(s["t"], (list, tuple)) and len(s["t"]) == 2:
        a, b = s["t"]
        return float(a), float(b)
    return float(s.get("in", 0)), float(s.get("out", 0))


def shot_duration(s):
    """샷의 지속시간을 안전하게 계산"""
    a, b = shot_bounds(s)
    return b - a


def validate_recipe(recipe: dict) -> list:
    """레시피 검증 및 오류 목록 반환"""
    errs = []
    tl = recipe.get("timeline", [])
    assets = recipe.get("assets", {})

    if not tl:
        errs.append("timeline이 비어있습니다.")
        return errs

    for i, shot in enumerate(tl):
        # 새로운 유틸리티 함수 사용
        dur = shot_duration(shot)
        if dur <= 0:
            errs.append(f"shot#{i} duration<=0")

        layers = shot.get("layers", [])
        for j, layer in enumerate(layers):
            if layer.get("type") in ("video", "image"):
                ref = layer.get("ref")
                if not ref:
                    errs.append(f"shot#{i} layer#{j} missing ref")
                elif ref not in assets:
                    errs.append(f"shot#{i} layer#{j} ref '{ref}' not in assets")
                elif not Path(assets[ref]).exists():
                    errs.append(f"shot#{i} layer#{j} asset file missing: {assets[ref]}")

    return errs


def build_recipe_from_session() -> dict | None:
    """세션 데이터로부터 레시피 즉석 생성"""
    brief = st.session_state.get("brief") or {}
    style = st.session_state.get("style_guide") or {}
    ov = st.session_state.get("overlays") or []
    shots = st.session_state.get("shotlist") or st.session_state.get("shotlist_json") or []

    # 타입 강제 (문자열로 저장된 케이스 방지)
    def as_dict(x):
        if isinstance(x, dict):
            return x
        if isinstance(x, str):
            try:
                v = jsonlib.loads(x)
                return v if isinstance(v, dict) else {}
            except:
                return {}
        return {}

    def as_list(x):
        if isinstance(x, list):
            return x
        if isinstance(x, str):
            try:
                v = jsonlib.loads(x)
                return v if isinstance(v, list) else []
            except:
                return []
        return []

    brief = as_dict(brief)
    style = as_dict(style)
    ov = as_list(ov)
    shots = as_list(shots)

    if not shots or not style:
        LOG.warning("[RECIPE] cannot build - missing shots or style")
        return None

    # 자산 매핑 생성 (refs 폴더에서 자동 매핑)
    assets = {}
    refs_dir = ROOT / "outputs" / "refs"
    if refs_dir.exists():
        for ref_file in refs_dir.glob("*"):
            if ref_file.is_file():
                # 파일명을 키로 사용 (확장자 제거)
                key = ref_file.stem
                assets[key] = str(ref_file)
                # product, store, broll1, broll2 등으로 매핑
                if "product" in key.lower() or not any(
                    x in key.lower() for x in ["store", "broll"]
                ):
                    assets["product"] = str(ref_file)
                elif "store" in key.lower():
                    assets["store"] = str(ref_file)
                elif "broll" in key.lower() or "1" in key:
                    assets["broll1"] = str(ref_file)
                elif "2" in key:
                    assets["broll2"] = str(ref_file)

    # --- 개선된 레시피 생성 ---
    recipe = {
        "canvas": {"w": 1080, "h": 1920, "fps": 30, "bitrate": "4M"},
        "assets": assets,  # 자동 매핑된 자산
        "timeline": [],
    }
    t = 0.0
    for i, s in enumerate(shots):
        dur = float(s.get("dur", 2.0))
        # 샷별로 다른 자산 참조 (순환)
        asset_refs = ["product", "store", "broll1", "broll2"]
        ref = asset_refs[i % len(asset_refs)] if asset_refs else "product"

        item = {
            "in": t,
            "out": t + dur,
            "layers": [
                {"type": "video", "ref": ref, "dur": dur},
                {
                    "type": "text",
                    "text": s.get("caption", f"샷 {i + 1}"),
                    "style": style.get("text", {}),
                },
            ],
        }
        recipe["timeline"].append(item)
        t += dur

    LOG.info("[RECIPE] built from session with %d shots, %d assets", len(shots), len(assets))
    return recipe


# 세션 상태 기본값 보장
DEFAULTS = {
    "brief": {},
    "shotlist_json": [],
    "shotlist": [],
    "shots": [],
    "refs_frames": [],
    "palette": [],
    "style_guide": {},
    "overlay_plan": [],
    "preview_video": None,
    "analysis_complete": False,
    "recipe": None,
    "recipe_with_checklist": None,
    "brief_md": "",
    "checklist": [],
    "d2_done": False,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

# 타입 강제 변환 (문자열로 잘못 저장된 경우 수정)
# 기존 세션 상태가 문자열로 저장된 경우를 대비해 강제 변환
brief_value = st.session_state.get("brief")
if isinstance(brief_value, str):
    LOG.warning("[INIT] brief was string, converting to dict")
st.session_state["brief"] = _coerce_json_dict(brief_value)

shotlist_value = st.session_state.get("shotlist") or st.session_state.get("shotlist_json")
if isinstance(shotlist_value, str):
    LOG.warning("[INIT] shotlist was string, converting to list")
shotlist_converted = _coerce_json_list(shotlist_value)
st.session_state["shotlist"] = shotlist_converted
st.session_state["shotlist_json"] = shotlist_converted

# 안전한 로그 출력
brief = st.session_state.get("brief", {})
if isinstance(brief, dict):
    LOG.debug("[INIT] brief keys=%s", list(brief.keys()))
else:
    LOG.debug("[INIT] brief is %s (not dict)", type(brief).__name__)

shotlist_data = st.session_state.get("shotlist_json", [])
LOG.debug("[INIT] shotlist len=%s", len(shotlist_data))

# ✅ 반드시 파일 맨 위 (다른 st. 호출보다 먼저)
st.set_page_config(
    page_title="AdGen MVP",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 이 아래부터 다른 모듈 import, 세션 초기화, 라우팅 등
import json as jsonlib  # 모듈 이름을 jsonlib로 고정
import subprocess as sp
import time
from datetime import datetime
from pathlib import Path  # 표준 Path

from openai import OpenAI

# 공통 유틸
OUT_DIR = Path(ROOT) / "outputs"
REF_DIR = OUT_DIR / "refs"
VID_DIR = OUT_DIR / "videos"
ASSET_DIR = OUT_DIR / "assets"
VID_DIR.mkdir(parents=True, exist_ok=True)
ASSET_DIR.mkdir(parents=True, exist_ok=True)


def stage_asset(file, key_hint):
    """업로드된 파일을 영구 경로로 복사"""
    ext = Path(file.name).suffix.lower()
    
    # 1-소스 모드를 위한 product 폴더 구조 생성
    if key_hint == "product":
        product_dir = ASSET_DIR / "product"
        product_dir.mkdir(parents=True, exist_ok=True)
        save_path = product_dir / f"{key_hint}{ext}"
    else:
        save_path = ASSET_DIR / f"{key_hint}{ext}"
    
    with open(save_path, "wb") as f:
        f.write(file.getbuffer())
    return str(save_path)


def resolve_assets(asset_state: dict) -> dict:
    """자산 경로 검증 및 매핑"""
    amap = {}
    for k, v in (asset_state or {}).items():
        if not v:
            continue
        p = Path(v)
        if p.exists():
            amap[k] = str(p)
        else:
            st.error(f"자산 누락: {k} -> {v}")
    return amap


def normalize_timeline(timeline):
    """타임라인 duration=0 버그 방지"""
    from utils.diagnostics import heartbeat, loop_guard
    
    fixed = []
    guard = loop_guard("normalize_timeline", max_iter=1000, warn_every=100)
    for i, sh in enumerate(timeline):
        heartbeat("normalize_timeline")
        guard.tick({"shot_index": i, "total_shots": len(timeline)})
        
        t = sh.get("t")
        if t and len(t) == 2:
            dur = max(0.05, float(t[1]) - float(t[0]))
            sh["in"], sh["out"], sh["dur"] = float(t[0]), float(t[1]), dur
        elif "in" in sh and "out" in sh:
            sh["dur"] = max(0.05, float(sh["out"]) - float(sh["in"]))
        else:
            sh["dur"] = max(0.05, float(sh.get("dur", 2.0)))
        fixed.append(sh)
    return fixed


# Serene Minimal Gold 스타일 팩
SERENE_MINIMAL_PALETTE = {
    "bg": "#E9E3D9",  # 베이지
    "gold": "#C7A86E",  # 포인트 골드
    "text": "#2A2A2A",  # 다크 텍스트
    "soft_bg": "#FAF8F4C8",  # 반투명 소프트 배경
}

SERENE_MINIMAL_FONTS = {"kr": "Pretendard", "en": "CormorantGaramond"}

SERENE_MINIMAL_OVERLAYS = [
    {"type": "vignette", "strength": 0.22},
    {"type": "grain", "amount": 0.035, "soft": True},
    {"type": "glow", "threshold": 0.82, "intensity": 0.18},
]


def create_serene_minimal_recipe(assets: dict) -> dict:
    """Serene Minimal Gold 스타일 레시피 생성"""
    timeline = [
        # 0) 로고 인트로 (미세 줌인 + 골드)
        {
            "t": [0, 1.2],
            "xfade": "in",
            "layers": [
                {"type": "solid", "color": SERENE_MINIMAL_PALETTE["bg"]},
                {
                    "type": "logo",
                    "ref": "logo",
                    "pos": "center",
                    "scale": 0.58,
                    "style": {
                        "tint": SERENE_MINIMAL_PALETTE["gold"],
                        "emboss": 0.35,
                        "shadow": 0.2,
                    },
                    "motion": {"zoom": 1.02, "ease": "cubic_in_out"},
                },
            ],
        },
        # 1) 제품 히어로
        {
            "t": [1.2, 4.2],
            "xfade": "cross",
            "layers": [
                {
                    "type": "video",
                    "ref": "product",
                    "fit": "cover",
                    "stabilize": False,
                    "motion": {"zoom": 1.03, "pan": "center", "ease": "sine_in_out"},
                },
            ],
        },
        # 2) 공간 전경 (느린 패닝)
        {
            "t": [4.2, 6.2],
            "xfade": "cross",
            "layers": [
                {
                    "type": "image",
                    "ref": "store",
                    "fit": "cover",
                    "motion": {"pan": "left_to_right", "zoom": 1.02, "ease": "sine_in_out"},
                },
            ],
        },
        # 3) 브롤 디테일 컷 A
        {
            "t": [6.2, 8.2],
            "xfade": "cross",
            "layers": [
                {
                    "type": "image",
                    "ref": "broll1",
                    "fit": "cover",
                    "motion": {"pan": "top_to_center", "zoom": 1.03},
                },
            ],
        },
        # 4) 브롤 디테일 컷 B
        {
            "t": [8.2, 10.2],
            "xfade": "cross",
            "layers": [
                {
                    "type": "image",
                    "ref": "broll2",
                    "fit": "cover",
                    "motion": {"pan": "center_to_bottom", "zoom": 1.02},
                },
            ],
        },
        # 5) 제품 리프레임 (살짝 클로즈업)
        {
            "t": [10.2, 13.2],
            "xfade": "cross",
            "layers": [
                {
                    "type": "video",
                    "ref": "product",
                    "fit": "cover",
                    "motion": {"zoom": 1.045, "ease": "cubic_in_out"},
                },
                {
                    "type": "text",
                    "text": "HAND-CRAFTED TASTE",
                    "style": {
                        "font": SERENE_MINIMAL_FONTS["en"],
                        "size": 54,
                        "color": SERENE_MINIMAL_PALETTE["gold"],
                        "track": 2,
                    },
                    "pos": "top",
                },
            ],
        },
        # 6) 소프트 CTA
        {
            "t": [13.2, 16.2],
            "xfade": "cross",
            "layers": [
                {
                    "type": "image",
                    "ref": "store",
                    "fit": "cover",
                    "blur": 0.5,
                    "motion": {"zoom": 1.01},
                },
                {
                    "type": "text",
                    "text": "지금 방문하세요",
                    "pos": "bottom",
                    "style": {
                        "font": SERENE_MINIMAL_FONTS["kr"],
                        "size": 64,
                        "color": SERENE_MINIMAL_PALETTE["text"],
                        "bg": SERENE_MINIMAL_PALETTE["soft_bg"],
                        "pad": 14,
                        "radius": 12,
                    },
                },
            ],
        },
        # 7) 로고 아웃트로
        {
            "t": [16.2, 18.0],
            "xfade": "out",
            "layers": [
                {"type": "solid", "color": SERENE_MINIMAL_PALETTE["bg"]},
                {
                    "type": "logo",
                    "ref": "logo",
                    "pos": "center",
                    "scale": 0.62,
                    "style": {"tint": SERENE_MINIMAL_PALETTE["gold"], "emboss": 0.35},
                    "motion": {"zoom": 1.01},
                },
            ],
        },
    ]

    # 정규화 적용
    normalized_timeline = normalize_timeline(timeline)

    return {
        "canvas": {"w": 1080, "h": 1920, "fps": 30, "bitrate": "4M"},
        "assets": assets,
        "timeline": normalized_timeline,
        "overlays": SERENE_MINIMAL_OVERLAYS,
        "style": "serene_minimal_gold",
    }


# 1-소스 자동 합성 시스템
def synthesize_assets(product_path, out_dir, palette):
    """제품 이미지 1장으로 store, broll1, broll2 자동 합성"""
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    from utils.diagnostics import heartbeat, loop_guard
    
    heartbeat("synthesize_start")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prod = Image.open(product_path).convert("RGBA")
    W, H = 1080, 1920

    def backdrop(color_top, color_bot, vignette=0.25):
        """그라데이션 + 비네트 배경 생성"""

        # 색상 문자열을 RGB 튜플로 변환
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip("#")
            return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

        if isinstance(color_top, str):
            color_top = hex_to_rgb(color_top)
        if isinstance(color_bot, str):
            color_bot = hex_to_rgb(color_bot)

        g = Image.new("RGB", (W, H), color_top)
        grad = Image.linear_gradient("L").resize((1, H)).resize((W, H))
        base = Image.blend(g, Image.new("RGB", (W, H), color_bot), 0.35)
        # 비네트
        vign = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(vign)
        d.ellipse(
            (-int(W * 0.2), -int(H * 0.2), int(W * 1.2), int(H * 1.2)), fill=int(255 * vignette)
        )
        vign = vign.filter(ImageFilter.GaussianBlur(220))
        base = Image.composite(
            base, Image.new("RGB", (W, H), (0, 0, 0)), vign.point(lambda x: 255 - x)
        )
        return base

    def place(center_y=0.55, scale=0.8, glow=0.15):
        """제품을 배경에 배치 (글로우 + 그림자)"""
        bg = backdrop(palette["bg"], palette["bg"])
        # 소프트 글로우
        blur = prod.resize((int(prod.width * scale), int(prod.height * scale)), Image.LANCZOS)
        blur = blur.filter(ImageFilter.GaussianBlur(40)).point(lambda p: int(p * glow))
        layer = bg.convert("RGBA")
        cy = int(H * center_y)
        x = (W - blur.width) // 2
        y = cy - blur.height // 2
        layer.alpha_composite(blur, (x, y))
        # 본체
        main = prod.resize((int(prod.width * scale), int(prod.height * scale)), Image.LANCZOS)
        shadow = Image.new("RGBA", main.size, (0, 0, 0, 0))
        shadow.putalpha(
            ImageOps.invert(ImageOps.grayscale(main.split()[-1])).filter(
                ImageFilter.GaussianBlur(8)
            )
        )
        layer.alpha_composite(shadow, (x, y + 8))
        layer.alpha_composite(main, (x, y))
        return layer.convert("RGB")

    # store / broll1 / broll2 3종 합성
    heartbeat("synthesize_store_start")
    store = place(center_y=0.55, scale=0.82)
    store.save(out / "store.jpg", quality=92)
    heartbeat("synthesize_store_complete")

    heartbeat("synthesize_broll1_start")
    broll1 = place(center_y=0.60, scale=0.95)
    broll1.save(out / "broll1.jpg", quality=92)
    heartbeat("synthesize_broll1_complete")

    heartbeat("synthesize_broll2_start")
    broll2 = place(center_y=0.52, scale=0.70)
    broll2.save(out / "broll2.jpg", quality=92)
    heartbeat("synthesize_broll2_complete")

    return str(out / "store.jpg"), str(out / "broll1.jpg"), str(out / "broll2.jpg")


def map_to_product_only(ref_shots, assets):
    """레퍼런스 타임라인을 제품 전용 패턴으로 매핑"""
    seq = []
    cyc = ["product", "store", "broll1", "broll2"]  # 누락 방지 순환
    idx = 0
    t = 0.0

    for s in ref_shots:
        ref = cyc[idx % len(cyc)]
        idx += 1

        # 제품/합성샷을 켄번스 패턴으로
        motion_patterns = [
            {"zoom": 1.02, "pan": "center"},
            {"zoom": 1.03, "pan": "left_to_right"},
            {"zoom": 1.02, "pan": "top_to_center"},
            {"zoom": 1.045, "pan": "center"},
        ]
        motion = motion_patterns[idx % 4]

        shot = {
            "t": [round(t, 3), round(t + s["dur"], 3)],
            "xfade": s.get("xfade", "cross"),
            "layers": [
                {
                    "type": "image" if ref != "product" else "video",
                    "ref": ref,
                    "fit": "cover",
                    "motion": motion,
                }
            ],
        }
        seq.append(shot)
        t += s["dur"]

    return seq


def normalize_and_fill(timeline):
    """타임라인 정규화 및 최소 길이 보장"""
    fixed = []
    for s in timeline:
        a, b = s["t"]
        if b - a < 0.25:  # 최소 0.25s
            b = a + 0.25
        s["t"] = [round(a, 3), round(b, 3)]
        s["xfade"] = s.get("xfade", "cross")
        fixed.append(s)
    return fixed


def save_json_util(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        jsonlib.dump(obj, f, ensure_ascii=False, indent=2)


def save_uploaded_assets(items: list, uploaded_map: dict, assets_root: Path) -> list:
    """
    items: [{'id': 'logo', 'type': 'image'}, ...]
    uploaded_map: {'logo': <UploadedFile>, ...}
    assets_root: Path('outputs/assets')
    """
    assets_root = Path(assets_root)
    assets_root.mkdir(parents=True, exist_ok=True)

    saved = []
    for item in items:
        item_id = item.get("id")
        item_type = item.get("type", "misc")

        uf = uploaded_map.get(item_id)
        if not uf:  # 업로드 안 된 항목은 건너뜀
            continue

        # 확장자 추출(없으면 .bin)
        ext = Path(uf.name).suffix
        if not ext:
            ext = ".bin"

        subdir = assets_root / f"{item_type}s"
        subdir.mkdir(parents=True, exist_ok=True)

        out_path = subdir / f"{item_id}{ext}"
        # Streamlit UploadedFile은 getbuffer()가 가장 안전
        try:
            data = uf.getbuffer()
            out_path.write_bytes(data)
        except Exception:
            uf.seek(0)
            out_path.write_bytes(uf.read())

        saved.append({"id": item_id, "type": item_type, "path": str(out_path)})

    return saved


def switch_tab(label: str):
    # 실험적: 탭 자동 전환 (DOM을 클릭). 실패해도 앱 동작에는 영향 없음.
    st.markdown(
        f"""
        <script>
        const labels = Array.from(parent.document.querySelectorAll('button[role="tab"], div[role="tab"]'));
        const el = labels.find(x => x.innerText.trim() === "{label}");
        if (el) el.click();
        </script>
        """,
        unsafe_allow_html=True,
    )


# 타입 정규화는 utils/coerce.py로 이동됨


# D4 진단 유틸리티
def ffprobe_json(path: Path) -> dict:
    """ffprobe로 메타데이터 수집 (터미널/파일 로그에 남김)"""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,codec_name",
        "-show_entries",
        "format=duration,bit_rate",
        "-of",
        "json",
        str(path),
    ]
    p = sp.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if p.returncode != 0:
        LOG.error(f"ffprobe rc={p.returncode} err={p.stderr.strip()}")
        return {}
    try:
        info = jsonlib.loads(p.stdout or "{}")
    except Exception:
        LOG.exception("ffprobe JSON parse failed")
        info = {}
    LOG.debug(f"ffprobe out: {jsonlib.dumps(info, ensure_ascii=False)}")
    return info


def wait_until_written(path: Path, min_size=100_000, timeout=10):
    """쓰기 완료 대기: 사이즈가 멈출 때까지 또는 최소 용량/타임아웃"""
    t0 = time.time()
    last = -1
    while time.time() - t0 < timeout:
        if path.exists():
            size = path.stat().st_size
            if size >= min_size and size == last:
                LOG.debug(f"file stable size={size}")
                return True
            last = size
        time.sleep(0.25)
    LOG.warning(
        f"wait_until_written timeout. exists={path.exists()} size={path.stat().st_size if path.exists() else 0}"
    )
    return path.exists()


# 세션키 초기화
def _init_state():
    for k, v in {
        "active_tab": "D1 · Healthcheck",
        "refs_frames": [],
        "brief": None,
        "shotlist": None,
        "palette": None,
        "style_guide": None,
        "overlay_plan": None,
        "preview_video": None,
        "style": None,
        "overlays": None,
        "shots": None,
    }.items():
        st.session_state.setdefault(k, v)

    # 타입 정규화 (중요!)
    st.session_state["brief"] = coerce_json_dict(st.session_state.get("brief"))
    st.session_state["shotlist"] = coerce_json_list(st.session_state.get("shotlist"))

    LOG.info(
        f"[INIT] brief keys={list(st.session_state['brief'].keys()) if isinstance(st.session_state['brief'], dict) else type(st.session_state['brief'])}"
    )
    LOG.info(
        f"[INIT] shotlist len={len(st.session_state['shotlist']) if isinstance(st.session_state['shotlist'], list) else type(st.session_state['shotlist'])}"
    )


_init_state()

# 디버그용: 현재 키 상태를 항상 좌측에 표시(문제 잡을 때 매우 유용)
st.sidebar.caption("Session keys")
debug_info = {}
for k in [
    "active_tab",
    "refs_frames",
    "brief",
    "shotlist",
    "palette",
    "style_guide",
    "overlay_plan",
    "preview_video",
]:
    value = st.session_state.get(k)
    if isinstance(value, str) and len(value) > 50:
        debug_info[k] = f"str({len(value)} chars)"
    else:
        debug_info[k] = bool(value)
st.sidebar.json(debug_info)

# 추가 디버그: 비디오 관련 키들
st.sidebar.caption("Video paths")
video_keys = ["downloaded_video", "preview_video", "rendered_video"]
for key in video_keys:
    if key in st.session_state:
        value = st.session_state[key]
        if isinstance(value, str):
            exists = "✅" if _os.path.exists(value) else "❌"
            st.sidebar.text(f"{key}: {exists} {value[:50]}...")
        else:
            st.sidebar.text(f"{key}: {type(value)} {str(value)[:50]}...")

# D2 서비스 임포트 시도(실패해도 탭은 보이게)
D2_IMPORT_ERR = None
try:
    from services.brief_and_shots import generate_brief, generate_shotlist, save_json

    HAS_D2 = True
except Exception as e:
    HAS_D2 = False
    D2_IMPORT_ERR = e

# D3 서비스 임포트 시도
D3_IMPORT_ERR = None
try:
    from services.style_guide import build_overlay_plan, extract_palette, summarize_style
    from services.style_guide import save_json as save_json_d3

    HAS_D3 = True
except Exception as e:
    HAS_D3 = False
    D3_IMPORT_ERR = e

# D4 서비스 임포트 시도
D4_IMPORT_ERR = None
try:
    from services.renderer import render_preview

    HAS_D4 = True
except Exception as e:
    HAS_D4 = False
    D4_IMPORT_ERR = e

st.caption("BUILD: D1+D2+D3+D4 tabs")  # ← 이 문구가 보이면 새 파일이 로드된 것!

# 탭 네비게이션: 버전 호환 래퍼
TABS = ["D1 · Healthcheck", "D2 · Brief & Shotlist", "D3 · Style & Refs", "D4 · Preview Render"]


def segmented_tabs(label: str, options: list[str], default_label: str) -> str:
    """Streamlit 버전에 따라 segmented_control 또는 radio로 동작."""
    default_label = default_label if default_label in options else options[0]
    if hasattr(st, "segmented_control"):
        # 최신 Streamlit: default 인자를 사용
        try:
            return st.segmented_control(
                label=label,
                options=options,
                selection_mode="single",
                default=default_label,  # ← index 대신 default!
                key="seg_tabs",
            )
        except TypeError:
            # 어떤 버전은 value로 받기도 함
            return st.segmented_control(
                label=label,
                options=options,
                selection_mode="single",
                value=default_label,
                key="seg_tabs",
            )
    else:
        # 구버전은 radio 대체
        idx = options.index(default_label)
        return st.radio(label, options, index=idx, horizontal=True, key="seg_tabs")


selected = segmented_tabs("BUILD: D1+D2+D3+D4 tabs", TABS, st.session_state["active_tab"])
st.session_state["active_tab"] = selected


# ============ 렌더링 함수들 정의 ============
def render_d1():
    st.title("AdGen MVP · D1 환경 점검 & 다운로더")

    # 환경 체크
    try:
        from utils.downloader import (
            download_youtube,
            extract_audio,
            healthcheck,
            save_health_report,
        )
    except ImportError as e:
        st.error(f"utils.downloader import 실패: {e}")
        st.error(f"현재 sys.path: {sys.path[:3]}")
        st.error(f"ROOT 경로: {ROOT}")
        st.error(f"UTILS_DIR 경로: {UTILS_DIR}")
        st.error(f"UTILS_DIR 존재 여부: {UTILS_DIR.exists()}")
        return

    st.subheader("🔧 환경 체크")
    health_data = healthcheck()

    # 환경 상태 표시
    col1, col2, col3 = st.columns(3)

    with col1:
        if health_data["ffmpeg"]:
            st.success("✅ ffmpeg")
            st.caption(health_data["version_info"].get("ffmpeg", "버전 확인 실패"))
        else:
            st.error("❌ ffmpeg")
            st.caption("PATH에 ffmpeg가 없습니다")

    with col2:
        if health_data["ffprobe"]:
            st.success("✅ ffprobe")
            st.caption(health_data["version_info"].get("ffprobe", "버전 확인 실패"))
        else:
            st.error("❌ ffprobe")
            st.caption("PATH에 ffprobe가 없습니다")

    with col3:
        if health_data["yt_dlp"]:
            st.success("✅ yt-dlp")
            st.caption(health_data["version_info"].get("yt_dlp", "버전 확인 실패"))
        else:
            st.error("❌ yt-dlp")
            st.caption("yt-dlp가 설치되지 않았습니다")

    # 전체 상태
    if health_data["ok"]:
        st.success("🎉 모든 도구가 정상적으로 설치되어 있습니다!")
    else:
        st.error("⚠️ 일부 도구가 누락되었습니다. 위의 오류를 확인해주세요.")

    # OpenAI API 체크
    st.subheader("🤖 OpenAI API 체크")
    masked = f"{len(OPENAI_API_KEY)} chars" if OPENAI_API_KEY else "MISSING"
    if OPENAI_API_KEY:
        st.success(f"🔑 OpenAI API Key: {masked}")
    else:
        st.error("❌ OpenAI API Key가 설정되지 않았습니다")
        
    # SVD (AI 영상 생성) 체크
    st.subheader("🎬 SVD (AI 영상 생성) 체크")
    try:
        from services.video_generation import is_svd_available
        svd_available = is_svd_available()
        
        if svd_available:
            st.success("✅ SVD 사용 가능 (Hugging Face 토큰 설정됨)")
            
            # GPU 정보 표시
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_name = torch.cuda.get_device_name(0)
                    gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                    current_memory = torch.cuda.memory_allocated(0) / 1024**3
                    st.info(f"🎮 GPU: {gpu_name} ({gpu_memory:.1f}GB VRAM, 사용 중: {current_memory:.1f}GB)")
                else:
                    st.warning("⚠️ CUDA 사용 불가 (CPU 모드)")
            except Exception as gpu_e:
                st.warning(f"⚠️ GPU 정보 확인 실패: {gpu_e}")
                
            # SVD 모델 접근 테스트
            if st.button("🧪 SVD 모델 접근 테스트"):
                try:
                    from huggingface_hub import hf_hub_download
                    model_path = hf_hub_download(
                        "stabilityai/stable-video-diffusion-img2vid-xt-1-1", 
                        "model_index.json"
                    )
                    st.success(f"✅ 모델 접근 성공: {model_path}")
                except Exception as access_e:
                    st.error(f"❌ 모델 접근 실패: {access_e}")
                    if "401" in str(access_e) or "GatedRepoError" in str(access_e):
                        st.info("💡 **해결 방법:**\n1. https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt-1-1 에서 Access 신청\n2. 승인 후 다시 시도")
        else:
            st.error("❌ SVD 사용 불가 (Hugging Face 토큰 필요)")
            st.info("💡 **설정 방법:**\n1. .env 파일에 HUGGINGFACE_HUB_TOKEN 추가\n2. https://huggingface.co/settings/tokens 에서 토큰 생성")
            
    except ImportError as e:
        st.error(f"❌ SVD 모듈 import 실패: {e}")
        st.info("💡 **해결 방법:**\n1. pip install diffusers transformers accelerate\n2. redraw310 환경에서 설치 확인")
    except Exception as e:
        st.error(f"❌ SVD 체크 실패: {str(e)}")
        with st.expander("🔎 상세보기"):
            st.exception(e)

    # API 테스트
    prompt = st.text_input("테스트 프롬프트", value="pong만 한 단어로 답해줘")
    if st.button("OpenAI API 테스트"):
        start = time.time()
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            st.success("✅ OpenAI 호출 성공")
            st.write("• 응답:", resp.choices[0].message.content.strip())
            st.write(f"• 왕복지연: {int((time.time() - start) * 1000)} ms")
        except Exception as e:
            st.error("❌ OpenAI 호출 실패")
            st.exception(e)

    st.divider()

    # 유튜브 다운로더
    st.subheader("🎬 유튜브 다운로더")
    st.info(
        "⚠️ **권한 안내**: 본인 소유이거나 사용 허용된 영상만 다운로드해 주세요. 저작권을 준수해야 합니다."
    )

    yt_url = st.text_input(
        "유튜브 URL", placeholder="https://www.youtube.com/watch?v=...", key="d1_yt_url"
    )

    if st.button("🎬 영상 다운로드", disabled=not yt_url.strip() or not health_data["ok"]):
        if not health_data["ok"]:
            st.error("환경 체크를 통과한 후 다운로드를 시도해주세요.")
        else:
            # 다운로드 진행
            progress_bar = st.progress(0)
            status_text = st.empty()

            def progress_callback(percent, message):
                progress_bar.progress(percent)
                status_text.text(message)

            try:
                # 임시 디렉토리 생성
                tmp_dir = OUT_DIR / "tmp" / "ref"
                tmp_dir.mkdir(parents=True, exist_ok=True)

                # 영상 다운로드
                video_path = download_youtube(yt_url.strip(), str(tmp_dir), progress_callback)

                # 오디오 추출
                audio_path = extract_audio(video_path, str(tmp_dir), progress_callback)

                # 결과 저장
                st.session_state["downloaded_video"] = video_path
                st.session_state["downloaded_audio"] = audio_path

                # health.json 저장
                health_report_path = OUT_DIR / "health.json"
                save_health_report(health_data, str(health_report_path))

                progress_bar.progress(100)
                status_text.text("✅ 다운로드 완료!")

                st.success("🎉 다운로드 성공!")
                st.write(f"• 비디오: {_os.path.basename(video_path)}")
                st.write(f"• 오디오: {_os.path.basename(audio_path)}")
                st.write(f"• 저장 위치: {tmp_dir}")

                # 파일 크기 표시
                video_size = _os.path.getsize(video_path) / (1024 * 1024)  # MB
                audio_size = _os.path.getsize(audio_path) / (1024 * 1024)  # MB
                st.metric("비디오 크기", f"{video_size:.1f} MB")
                st.metric("오디오 크기", f"{audio_size:.1f} MB")

            except Exception as e:
                st.error(f"❌ 다운로드 실패: {str(e)}")
                progress_bar.empty()
                status_text.empty()

    # 다운로드된 파일 표시
    if st.session_state.get("downloaded_video"):
        st.subheader("📁 다운로드된 파일")
        col1, col2 = st.columns(2)

        with col1:
            st.write("**비디오 파일**")
            st.write(f"경로: {st.session_state['downloaded_video']}")
            video_path = st.session_state["downloaded_video"]
            if video_path and _os.path.exists(video_path):
                try:
                    # 바이트로 읽어서 매번 새 ID 생성 (임시 ID 재사용 방지)
                    video_data = Path(video_path).read_bytes()
                    st.video(video_data, format="video/mp4")
                    st.download_button(
                        "mp4 다운로드",
                        video_data,
                        file_name=Path(video_path).name,
                        mime="video/mp4",
                    )
                except Exception as e:
                    st.error(f"비디오 미리보기 실패: {e}")
                    st.info(f"파일 경로: {video_path}")
            else:
                st.warning("파일을 찾을 수 없습니다")

        with col2:
            st.write("**오디오 파일**")
            st.write(f"경로: {st.session_state['downloaded_audio']}")
            if _os.path.exists(st.session_state["downloaded_audio"]):
                st.audio(st.session_state["downloaded_audio"])
            else:
                st.warning("파일을 찾을 수 없습니다")

    # 레퍼런스 분석 (다운로드된 영상이 있을 때만)
    if st.session_state.get("downloaded_video"):
        st.subheader("🔍 레퍼런스 자동 분석")

        from services.analyze_reference import analyze_reference, get_analysis_summary

        # 분석 설정
        col1, col2 = st.columns(2)
        with col1:
            num_keyframes = st.slider(
                "키프레임 개수",
                min_value=60,
                max_value=180,
                value=120,
                help="추출할 대표 프레임 수 (60~180장)",
            )
        with col2:
            analysis_threshold = st.slider(
                "장면 탐지 민감도",
                min_value=15.0,
                max_value=40.0,
                value=27.0,
                step=1.0,
                help="낮을수록 더 세밀하게 장면을 나눔",
            )

        if st.button("🔍 레퍼런스 분석 시작", type="primary"):
            video_path = st.session_state["downloaded_video"]

            with st.spinner("레퍼런스 분석 중..."):
                try:
                    # 분석 진행률 표시
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def analysis_progress(percent, message):
                        progress_bar.progress(percent / 100)
                        status_text.text(f"{message} ({percent}%)")

                    # 레퍼런스 분석 실행
                    recipe = analyze_reference(
                        video_path, "tmp/ref", num_keyframes, analysis_progress
                    )

                    # 분석 결과를 세션에 저장
                    st.session_state["recipe"] = recipe
                    st.session_state["analysis_complete"] = True

                    # 분석 요약 표시
                    summary = get_analysis_summary(recipe)

                    # 경고가 있으면 표시
                    warnings = recipe.get("warnings", [])
                    if warnings:
                        st.warning(f"⚠️ 분석 완료 (경고 {len(warnings)}건)")
                        with st.expander("경고 상세 보기", expanded=False):
                            for warning in warnings:
                                st.write(f"• {warning}")
                        st.info(
                            "💡 일부 구간에서 모션 포인트가 검출되지 않아 모션 기반 기법을 생략했습니다. 그래도 컷/색/오디오 분석은 정상 반영되었습니다."
                        )
                    else:
                        st.success("✅ 레퍼런스 분석 완료!")

                    # 분석 결과 요약
                    st.subheader("📊 분석 결과 요약")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("총 샷 수", summary["total_shots"])
                    with col2:
                        st.metric("평균 샷 길이", f"{summary['avg_shot_duration']}초")
                    with col3:
                        st.metric("BPM", f"{summary['bpm']:.1f}")
                    with col4:
                        st.metric("해상도", summary["resolution"])

                    # 샷 썸네일 미리보기
                    st.subheader("🎬 샷 썸네일 미리보기")
                    shots = recipe.get("shots", [])
                    if shots:
                        # 처음 12개 샷만 표시
                        preview_shots = shots[:12]
                        cols = st.columns(4)
                        for i, shot in enumerate(preview_shots):
                            with cols[i % 4]:
                                if _os.path.exists(shot["thumb"]):
                                    st.image(shot["thumb"], caption=f"샷 {shot['idx'] + 1}")
                                    st.caption(f"{shot['t0']:.1f}s - {shot['t1']:.1f}s")

                    # 팔레트 미리보기
                    if shots:
                        st.subheader("🎨 색상 팔레트")
                        sample_shot = shots[0]  # 첫 번째 샷의 팔레트 표시
                        palette = sample_shot.get("palette", [])
                        if palette:
                            cols = st.columns(len(palette))
                            for i, color in enumerate(palette):
                                with cols[i]:
                                    st.color_picker(
                                        f"색상 {i + 1}", color, disabled=True, key=f"palette_{i}"
                                    )

                    # D2로 이동 버튼
                    if st.button("➡️ D2로 이동하여 브리프 생성", type="primary"):
                        st.session_state["active_tab"] = "D2 · Brief & Shotlist"
                        st.rerun()

                except Exception as e:
                    st.error(f"분석 실패: {str(e)}")
                    st.exception(e)

    # 분석 완료 상태 표시
    if st.session_state.get("analysis_complete"):
        st.success("✅ 레퍼런스 분석이 완료되었습니다. D2 탭으로 이동하여 브리프를 생성하세요.")

    # 환경 체크 결과 저장
    if st.button("💾 환경 체크 결과 저장"):
        health_report_path = OUT_DIR / "health.json"
        save_health_report(health_data, str(health_report_path))
        st.success(f"환경 체크 결과가 저장되었습니다: {health_report_path}")


def render_d2():
    st.title("AdGen MVP · D2 Brief & Shotlist")

    # 1-소스 자동 생성 모드 스위치
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("🎬 생성 모드")
    with col2:
        one_src_mode = st.toggle(
            "🪄 1-소스 자동 생성",
            value=True,
            help="제품 이미지 1장만으로 누락 샷을 자동 합성합니다.",
        )

    if one_src_mode:
        st.info("🪄 **1-소스 모드**: 제품 이미지 1장으로 모든 샷을 자동 생성합니다")
        st.session_state["one_source_mode"] = True
    else:
        st.info("📁 **수동 모드**: 각 샷에 필요한 자산을 직접 업로드합니다")
        st.session_state["one_source_mode"] = False

    # 레퍼런스 분석 결과 확인
    if st.session_state.get("analysis_complete") and st.session_state.get("recipe"):
        st.success("✅ 레퍼런스 분석 완료 - 분석된 데이터를 활용합니다")

        recipe = st.session_state["recipe"]
        shots = recipe.get("shots", [])

        # 분석 결과 요약 표시
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("총 샷 수", len(shots))
        with col2:
            st.metric("BPM", f"{recipe.get('audio', {}).get('bpm', 0):.1f}")
        with col3:
            meta = recipe.get("meta", {})
            st.metric("해상도", f"{meta.get('size', [0, 0])[0]}x{meta.get('size', [0, 0])[1]}")

        # 샷 썸네일 그리드
        st.subheader("🎬 분석된 샷들")
        if shots:
            cols = st.columns(4)
            for i, shot in enumerate(shots[:16]):  # 처음 16개만 표시
                with cols[i % 4]:
                    if _os.path.exists(shot["thumb"]):
                        st.image(shot["thumb"], caption=f"샷 {shot['idx'] + 1}")
                        st.caption(f"{shot['t0']:.1f}s - {shot['t1']:.1f}s")

        # 브리프 생성
        st.subheader("📝 브리프 생성")
        prompt = st.text_area(
            "브리프 생성 프롬프트",
            value="분석된 레퍼런스 영상을 바탕으로 고품질 광고 영상을 위한 브리프를 생성해주세요.",
            height=100,
        )

        if st.button("🎯 레퍼런스 기반 브리프 생성", type="primary"):
            LOG.debug(
                "[D2] shotlist_json type=%s len=%s",
                type(st.session_state.get("shotlist_json")).__name__,
                len(st.session_state.get("shotlist_json") or []),
            )
            with st.spinner("브리프 생성 중..."):
                try:
                    from services.checklist import (
                        build_checklist,
                        generate_brief_md,
                        generate_shotlist_json,
                    )

                    # 체크리스트 생성
                    recipe_with_checklist = build_checklist(recipe.copy())
                    st.session_state["recipe_with_checklist"] = recipe_with_checklist

                    # 브리프 마크다운 생성
                    brief_md = generate_brief_md(recipe_with_checklist, prompt)
                    st.session_state["brief_md"] = brief_md

                    # 샷리스트 JSON 생성
                    shotlist_text = generate_shotlist_json(recipe_with_checklist)
                    st.session_state["shotlist_json"] = shotlist_text

                    # 체크리스트 생성
                    checklist = recipe_with_checklist.get("checklist", [])
                    st.session_state["checklist"] = checklist

                    # 세션 상태 저장 (키 이름 통일) - 파이썬 객체로 저장
                    st.session_state["brief"] = recipe_with_checklist  # dict 객체로 저장
                    st.session_state["shotlist"] = shotlist_text  # list 객체로 저장
                    st.session_state["shots"] = (
                        shotlist_text  # D3가 찾는 키 이름도 설정 (객체 그대로)
                    )
                    st.session_state["d2_done"] = True

                    # 파일 백업 (새 탭/새 세션 대비)

                    OUTPUTS = Path("outputs")
                    OUTPUTS.mkdir(exist_ok=True)

                    # 브리프 파일 저장
                    with open(OUTPUTS / "brief.json", "w", encoding="utf-8") as f:
                        jsonlib.dump(
                            {"content": brief_md, "type": "markdown"},
                            f,
                            ensure_ascii=False,
                            indent=2,
                        )

                    # 샷리스트 파일 저장
                    with open(OUTPUTS / "shots.json", "w", encoding="utf-8") as f:
                        jsonlib.dump(shotlist_text, f, ensure_ascii=False, indent=2)

                    st.success("✅ 브리프, 샷리스트, 체크리스트가 생성되었습니다!")
                    st.success("💾 파일 백업 완료: outputs/brief.json, outputs/shots.json")

                    # 생성된 브리프 표시
                    st.subheader("📄 생성된 브리프")
                    st.markdown(brief_md)

                except Exception as e:
                    st.error(f"브리프 생성 실패: {str(e)}")
                    st.exception(e)

        # 샷리스트 생성
        st.subheader("🎬 샷리스트 생성")
        if st.button("🎯 레퍼런스 기반 샷리스트 생성", type="primary"):
            with st.spinner("샷리스트 생성 중..."):
                try:
                    # 분석된 샷을 기반으로 샷리스트 생성
                    shotlist = []
                    for i, shot in enumerate(shots):
                        shot_item = {
                            "shot_number": i + 1,
                            "time_range": f"{shot['t0']:.1f}s - {shot['t1']:.1f}s",
                            "duration": f"{shot['duration']:.1f}s",
                            "description": f"샷 {i + 1} - {shot.get('motion', {}).get('type', 'static')} 모션",
                            "colors": shot.get("palette", []),
                            "texts": [t["text"] for t in shot.get("text", [])],
                            "thumbnail": shot["thumb"],
                        }
                        shotlist.append(shot_item)

                    st.session_state["shotlist"] = shotlist
                    st.success("✅ 샷리스트가 생성되었습니다!")

                    # 생성된 샷리스트 표시
                    for shot in shotlist[:5]:  # 처음 5개만 표시
                        with st.expander(f"샷 {shot['shot_number']}: {shot['time_range']}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                if _os.path.exists(shot["thumbnail"]):
                                    st.image(shot["thumbnail"], width=200)
                            with col2:
                                st.write(f"**설명**: {shot['description']}")
                                st.write(f"**색상**: {', '.join(shot['colors'][:3])}")
                                if shot["texts"]:
                                    st.write(f"**텍스트**: {', '.join(shot['texts'][:2])}")

                except Exception as e:
                    st.error(f"샷리스트 생성 실패: {str(e)}")
                    st.exception(e)

        # 체크리스트 및 자산 업로드
        if st.session_state.get("checklist"):
            st.subheader("📋 자산 체크리스트")

            checklist = st.session_state["checklist"]
            project_id = f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 필수 항목과 선택 항목 분리
            required_items = [item for item in checklist if item["required"]]
            optional_items = [item for item in checklist if not item["required"]]

            # 필수 항목 표시
            st.write("**필수 자산**")
            for item in required_items:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"🔴 **{item['desc']}** ({item['type']})")
                    if item.get("frequency", 0) > 0:
                        st.caption(f"사용 빈도: {item['frequency']}회")
                with col2:
                    if item["type"] == "text":
                        user_input = st.text_input(
                            "입력",
                            key=f"input_{item['id']}",
                            placeholder=item.get("placeholder", ""),
                        )
                        if user_input:
                            st.session_state[f"asset_{item['id']}"] = user_input
                    elif item["type"] == "color":
                        color = st.color_picker("색상", key=f"color_{item['id']}")
                        if color:
                            st.session_state[f"asset_{item['id']}"] = color
                    else:
                        # 제품 이미지/영상 전용 업로더 (안정화 버전)
                        if item["id"] == "product":
                            # 제품 이미지 업로더 (고유 키로 탭 간 충돌 방지)
                            up_img = st.file_uploader(
                                "제품 이미지(메인)", 
                                type=["png","jpg","jpeg","webp"],
                                key="d2_upload_product_image", 
                                accept_multiple_files=False
                            )
                            
                            # 제품 영상 업로더 (선택) (고유 키로 탭 간 충돌 방지)
                            up_vid = st.file_uploader(
                                "제품 영상(선택)", 
                                type=["mp4","mov","m4v"],
                                key="d2_upload_product_shot", 
                                accept_multiple_files=False
                            )
                            
                            # 업로드 처리 (즉시 저장, 절대 경로 사용)
                            from pathlib import Path
                            import os as _os
                            from PIL import Image
                            import numpy as np
                            from utils.frame_extractor import extract_frame_to_image
                            
                            # 앱 파일 기준 절대 경로 (CWD 의존성 제거)
                            ROOT = Path(__file__).resolve().parents[1]
                            ASSETS_DIR = ROOT / "outputs" / "assets"
                            ASSETS_DIR.mkdir(parents=True, exist_ok=True)
                            
                            def save_bytes_immediate(file, outpath: Path):
                                """업로드 즉시 파일 저장 (Submit 불필요)"""
                                data = file.getvalue()
                                outpath.parent.mkdir(parents=True, exist_ok=True)
                                with open(outpath, "wb") as f:
                                    f.write(data)
                                return str(outpath), len(data)
                            
                            # 1) 이미지 우선 저장 (즉시)
                            if up_img is not None:
                                ext = _os.path.splitext(up_img.name)[1].lower() or ".png"
                                if ext not in [".jpg",".jpeg",".png",".webp"]:
                                    ext = ".png"
                                img_path, size = save_bytes_immediate(up_img, ASSETS_DIR / f"product{ext}")
                                st.session_state["product_image_path"] = img_path
                                st.info(f"✅ 이미지 저장됨: {img_path} ({size:,} bytes)")
                            
                            # 2) 영상만 올린 경우: 썸네일 이미지 자동 생성 (즉시)
                            if up_vid is not None and st.session_state.get("product_image_path") is None:
                                tmp_video_path, vid_size = save_bytes_immediate(up_vid, ASSETS_DIR / "product_shot.mp4")
                                st.info(f"✅ 영상 저장됨: {tmp_video_path} ({vid_size:,} bytes)")
                                
                                # 한 프레임 썸네일 생성 (0.5초 지점)
                                try:
                                    thumb = extract_frame_to_image(tmp_video_path, t=0.5)
                                    thumb_out = ASSETS_DIR / "product.jpg"
                                    thumb.save(thumb_out, quality=95)
                                    st.session_state["product_image_path"] = str(thumb_out)
                                    st.success("🎬 영상에서 제품 썸네일을 생성했습니다.")
                                except Exception as e:
                                    st.error(f"❌ 썸네일 생성 실패: {e}")
                            
                            # 3) 최종 검증 및 세션 상태 업데이트 (즉시)
                            p_img = st.session_state.get("product_image_path")
                            if not p_img or not _os.path.exists(p_img):
                                st.error("❌ 제품 이미지를 찾을 수 없습니다.")
                            else:
                                st.success(f"✅ 제품 이미지 OK: {_os.path.basename(p_img)}")
                                # 기존 시스템과 호환
                                permanent_path = p_img
                                st.session_state[f"asset_{item['id']}"] = permanent_path
                                st.session_state.setdefault("assets", {})[item["id"]] = permanent_path
                                st.session_state["uploaded_product_path"] = permanent_path
                        else:
                            # 다른 자산들은 기존 방식 유지
                            uploaded_file = st.file_uploader(
                                "업로드",
                                type=["png", "jpg", "jpeg", "mp4", "mov"],
                                key=f"upload_{item['id']}",
                            )
                            if uploaded_file:
                                # 영구 경로로 복사하여 저장
                                permanent_path = stage_asset(uploaded_file, item["id"])
                                st.session_state[f"asset_{item['id']}"] = permanent_path
                                st.session_state.setdefault("assets", {})[item["id"]] = permanent_path
                with col3:
                    if st.session_state.get(f"asset_{item['id']}"):
                        st.success("✅")
                    else:
                        st.warning("❌")

            # 선택 항목 표시
            if optional_items:
                st.write("**선택 자산**")
                for item in optional_items:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"🟡 **{item['desc']}** ({item['type']})")
                        if item.get("frequency", 0) > 0:
                            st.caption(f"사용 빈도: {item['frequency']}회")
                    with col2:
                        if item["type"] == "text":
                            user_input = st.text_input(
                                "입력",
                                key=f"input_{item['id']}",
                                placeholder=item.get("placeholder", ""),
                            )
                            if user_input:
                                st.session_state[f"asset_{item['id']}"] = user_input
                        elif item["type"] == "color":
                            color = st.color_picker("색상", key=f"color_{item['id']}")
                            if color:
                                st.session_state[f"asset_{item['id']}"] = color
                        else:
                            # 다른 자산들은 기존 방식 유지
                            uploaded_file = st.file_uploader(
                                "업로드",
                                type=["png", "jpg", "jpeg", "mp4", "mov"],
                                key=f"upload_{item['id']}",
                            )
                            if uploaded_file:
                                # 영구 경로로 복사하여 저장
                                permanent_path = stage_asset(uploaded_file, item["id"])
                                st.session_state[f"asset_{item['id']}"] = permanent_path
                                st.session_state.setdefault("assets", {})[item["id"]] = (
                                    permanent_path
                                )
                    with col3:
                        if st.session_state.get(f"asset_{item['id']}"):
                            st.success("✅")
                        else:
                            st.info("선택")

            # 체크리스트 완료 상태 계산 (안전한 방식)
            def progress_of(items, prefix="asset_"):
                total = len(items)
                done = sum(bool(st.session_state.get(f"{prefix}{it['id']}")) for it in items)
                pct = int(done * 100 / total) if total else 0
                return done, total, pct

            # 필수 항목 진행률
            req_done, req_total, req_pct = progress_of(required_items)
            required_completed = req_done == req_total

            # 선택 항목 진행률
            opt_done, opt_total, opt_pct = progress_of(optional_items)

            # 전체 완료율
            total_done = req_done + opt_done
            total_items = len(checklist)
            completion_rate = int(total_done * 100 / total_items) if total_items else 0

            st.subheader("📊 진행 상황")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("필수 항목", f"{req_done}/{req_total}", f"{req_pct}%")
            with col2:
                st.metric("선택 항목", f"{opt_done}/{opt_total}", f"{opt_pct}%")
            with col3:
                st.metric("완료율", f"{total_done}/{total_items}", f"{completion_rate}%")

            # 파일 저장
            save_button_text = "🪄 1-소스 자동 생성 & 저장" if one_src_mode else "💾 자산 저장"
            if st.button(save_button_text, disabled=not required_completed):
                try:
                    from services.checklist import save_assets_structure
                    from utils.diagnostics import heartbeat

                    heartbeat("button_asset_save_start")

                    # 자산 저장 구조 생성
                    assets_dir = save_assets_structure(project_id, checklist)

                    # 1-소스 모드 처리
                    if one_src_mode:
                        st.info("🪄 1-소스 모드: 제품 이미지로 자동 합성 중...")
                        heartbeat("one_source_mode_start")

                        # 제품 이미지 찾기
                        product_asset = None
                        for item in checklist:
                            if "product" in item["id"].lower():
                                asset = st.session_state.get(f"asset_{item['id']}")
                                if asset and hasattr(asset, "read"):
                                    # 제품 이미지를 영구 경로로 저장
                                    product_path = stage_asset(asset, "product")
                                    product_asset = product_path
                                    heartbeat("product_asset_staged")
                                    break

                        if product_asset:
                            # 자동 합성 실행
                            heartbeat("synthesize_assets_start")
                            
                            # 진행 표시기
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            try:
                                status_text.text("🔄 제품 이미지 분석 중...")
                                progress_bar.progress(10)
                                heartbeat("synthesize_assets_analysis")
                                
                                status_text.text("🎨 Store 이미지 생성 중...")
                                progress_bar.progress(30)
                                
                                status_text.text("🎬 Broll1 이미지 생성 중...")
                                progress_bar.progress(60)
                                
                                status_text.text("🎭 Broll2 이미지 생성 중...")
                                progress_bar.progress(90)
                                
                                store_path, broll1_path, broll2_path = synthesize_assets(
                                    product_asset, str(ASSET_DIR / "autogen"), SERENE_MINIMAL_PALETTE
                                )
                                
                                progress_bar.progress(100)
                                status_text.text("✅ 자동 합성 완료!")
                                heartbeat("synthesize_assets_complete")
                                
                            except Exception as e:
                                st.error(f"자동 합성 중 오류 발생: {str(e)}")
                                st.error("제품 이미지를 다시 업로드하거나 다른 이미지로 시도해보세요.")
                                st.stop()

                            # 세션에 자동 생성된 자산 저장
                            st.session_state.setdefault("assets", {})
                            st.session_state["assets"]["product"] = product_asset
                            st.session_state["assets"]["store"] = store_path
                            st.session_state["assets"]["broll1"] = broll1_path
                            st.session_state["assets"]["broll2"] = broll2_path

                            st.success("✅ 자동 합성 완료!")
                            st.success(f"   - 제품: {Path(product_asset).name}")
                            st.success(f"   - 매장: {Path(store_path).name}")
                            st.success(f"   - 브롤1: {Path(broll1_path).name}")
                            st.success(f"   - 브롤2: {Path(broll2_path).name}")
                        else:
                            st.error(
                                "제품 이미지를 찾을 수 없습니다. 먼저 제품 이미지를 업로드해주세요."
                            )
                            st.stop()

                    # 업로드된 파일들을 안전하게 저장
                    uploaded_files_map = {}
                    for item in checklist:
                        asset = st.session_state.get(f"asset_{item['id']}")
                        if asset and hasattr(asset, "read"):  # 파일 업로드만
                            uploaded_files_map[item["id"]] = asset

                    # 안전한 자산 저장 함수 사용 (1-소스 모드가 아닌 경우만)
                    if not one_src_mode:
                        saved_assets = save_uploaded_assets(
                            checklist, uploaded_files_map, Path(assets_dir)
                        )

                    # 텍스트/색상 입력 저장
                    for item in checklist:
                        asset = st.session_state.get(f"asset_{item['id']}")
                        if asset and not hasattr(asset, "read"):  # 텍스트/색상 입력
                            text_path = Path(assets_dir) / "texts" / f"{item['id']}.txt"
                            text_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(text_path, "w", encoding="utf-8") as f:
                                f.write(str(asset))

                    # 브리프 마크다운 저장
                    brief_path = Path(assets_dir) / "brief.md"
                    with open(brief_path, "w", encoding="utf-8") as f:
                        f.write(st.session_state["brief_md"])

                    # 샷리스트 JSON 저장
                    shotlist_path = Path(assets_dir) / "shotlist.json"
                    with open(shotlist_path, "w", encoding="utf-8") as f:
                        jsonlib.dump(
                            st.session_state["shotlist_json"], f, ensure_ascii=False, indent=2
                        )

                    # 체크리스트 JSON 저장
                    checklist_path = Path(assets_dir) / "checklist.json"
                    with open(checklist_path, "w", encoding="utf-8") as f:
                        jsonlib.dump(checklist, f, ensure_ascii=False, indent=2)

                    st.success(f"✅ 자산이 저장되었습니다: {assets_dir}")
                    st.session_state["assets_saved"] = True

                except Exception as e:
                    st.error(f"자산 저장 실패: {str(e)}")
                    st.exception(e)

            # 원클릭 자동 생성 버튼
            st.divider()
            colA, colB = st.columns([1,1])
            with colA:
                product_file = st.session_state.get("uploaded_product_path")  # 당신이 저장한 경로
                ref_url      = st.session_state.get("ref_url") or ""
                preset       = st.session_state.get("style_preset") or "Serene Minimal Gold"
                
                if st.button("🪄 제품 1개로 자동 생성", use_container_width=True):
                    prog = st.progress(0, text="준비 중…")
                    def cb(pct, msg): prog.progress(int(pct), text=msg)

                    try:
                        result = one_click_make(product_file, ref_url, preset, progress=cb)
                        # 세션 상태 타입 강제 변환
                        st.session_state["brief"]      = _coerce_json_dict(result.get("recipe", {}).get("brief"))
                        st.session_state["shotlist"]   = _coerce_json_list(result.get("recipe", {}).get("shots"))
                        st.session_state["style_guide"]= _coerce_json_dict(result.get("style"))
                        st.session_state["assets_map"] = _coerce_json_dict(result.get("assets"))
                        st.session_state["last_video"] = result["output"]
                        st.success("자동 생성 완료! D4에서 미리보기/다운로드하세요.")
                        st.session_state["active_tab"] = "D4 · Preview Render"
                    except AdGenError as e:
                        st.error(f"❌ {e.code} — {e.msg}")
                        with st.expander("🔎 상세보기/개발용 로그"):
                            st.code((e.detail or "no detail") + f"\ncorrelation_id={e.correlation_id}")
                            if e.hint: st.info(e.hint)
                    except Exception as e:
                        st.error("❌ A999 — 알 수 없는 오류")
                        st.exception(e)
            with colB:
                st.write("Tip: 레퍼런스 링크(D1)와 제품 이미지/영상(D2)만 준비돼 있으면 됩니다.")
                
            # AI 영상 생성 버튼 추가
            st.divider()
            colC, colD = st.columns([1,1])
            with colC:
                try:
                    from services.video_generation import generate_ai_video, is_svd_available
                    svd_available = is_svd_available()
                except Exception as e:
                    svd_available = False
                    st.caption(f"⚠️ SVD 모듈 로드 실패: {str(e)}")
                
                if svd_available:
                    if st.button("🤖 AI 영상 생성 (SVD)", use_container_width=True):
                        product_img = st.session_state.get("product_image_path")
                        if not product_img or not _os.path.exists(product_img):
                            st.error("❌ 제품 이미지를 먼저 업로드하세요")
                        else:
                            prog = st.progress(0, text="AI 영상 생성 중...")
                            def ai_cb(pct, msg): 
                                prog.progress(int(pct), text=msg)
                            
                            try:
                                # AI 영상 생성 (1초, 중간 움직임)
                                output_path, metadata = generate_ai_video(
                                    image_path=product_img,
                                    duration_seconds=1.0,
                                    motion_level="medium", 
                                    quality="standard",
                                    progress_callback=ai_cb
                                )
                                
                                st.session_state["ai_generated_video"] = output_path
                                st.session_state["ai_video_metadata"] = metadata
                                st.success("✅ AI 영상 생성 완료!")
                                
                                # 결과 표시
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.metric("생성 시간", f"{metadata['duration']:.1f}초")
                                with col2:
                                    st.metric("프레임 수", metadata['num_frames'])
                                
                                # D4로 자동 이동
                                st.info("🎬 D4에서 AI 영상을 미리보기/다운로드하세요!")
                                st.session_state["active_tab"] = "D4 · Preview Render"
                                    
                            except AdGenError as e:
                                st.error(f"❌ {e.code} — {e.msg}")
                                with st.expander("🔎 상세보기"):
                                    st.code(f"코드: {e.code}\n메시지: {e.msg}\n힌트: {e.hint or '없음'}\n상세: {e.detail or '없음'}")
                                    if "GatedRepoError" in str(e.detail or ""):
                                        st.info("💡 **해결 방법:**\n1. https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt-1-1 에서 Access 신청\n2. HUGGINGFACE_HUB_TOKEN 환경변수 설정")
                                    elif "OOM" in str(e.detail or "") or "OutOfMemory" in str(e.detail or ""):
                                        st.info("💡 **해결 방법:**\n1. GPU 메모리 부족 - 다른 프로그램 종료\n2. 프레임 수 줄이기 (25 → 15)\n3. 품질 설정 낮추기 (high → standard)")
                            except Exception as e:
                                st.error(f"❌ AI 영상 생성 실패: {str(e)}")
                                with st.expander("🔎 상세보기"):
                                    st.exception(e)
                else:
                    st.button("🤖 AI 영상 생성 (SVD)", disabled=True, use_container_width=True)
                    st.caption("⚠️ SVD 설정 필요 (Hugging Face 토큰)")
                    
            with colD:
                ai_video = st.session_state.get("ai_generated_video")
                if ai_video and _os.path.exists(ai_video):
                    st.success("🎬 AI 영상 준비됨")
                    try:
                        with open(ai_video, "rb") as f:
                            st.video(f.read(), format="video/mp4")
                    except Exception as e:
                        st.error(f"영상 표시 실패: {e}")
                else:
                    st.info("💡 제품 이미지 업로드 후 AI 영상 생성하세요")

            # D3로 이동 버튼
            if st.session_state.get("assets_saved"):
                if st.button("➡️ D3로 이동하여 스타일 가이드 생성", type="primary"):
                    st.session_state["active_tab"] = "D3 · Style & Refs"
                    st.rerun()

        st.divider()
        st.info(
            "💡 위의 분석 결과를 바탕으로 브리프와 샷리스트를 생성했습니다. 필요시 D3 탭으로 이동하여 스타일 가이드를 생성하세요."
        )
        return

    if not HAS_D2:
        st.error("D2 모듈 임포트 실패: services/brief_and_shots.py 또는 prompts/*.md 확인")
        if D2_IMPORT_ERR:
            st.exception(D2_IMPORT_ERR)
        st.code(
            "필수 파일:\n  prompts/intent_prompt.md\n  prompts/shotlist_prompt.md\n  services/brief_and_shots.py"
        )
    else:
        user_text = st.text_area(
            "요구사항 입력",
            key="d2_prompt",
            height=140,
            value="카페 오픈 20% 할인. 따뜻하고 감성 톤. 9:16 릴스.",
        )

        # 유튜브 레퍼런스 섹션
        st.subheader("🎬 유튜브 레퍼런스 (선택)")
        st.caption(f"Python: {sys.executable}")
        st.info(
            "⚠️ **권한 안내**: 본인 소유이거나 사용 허용된 영상만 입력해 주세요. 저작권을 준수해야 합니다."
        )
        yt_url = st.text_input(
            "유튜브 URL:", placeholder="https://www.youtube.com/watch?v=...", key="yt_url"
        )

        # 프레임 수 설정
        st.session_state.setdefault("yt_target_frames", 60)
        col_slider1, col_slider2 = st.columns([2, 1])
        with col_slider1:
            st.session_state["yt_target_frames"] = st.slider(
                "추출 프레임 수",
                min_value=24,
                max_value=180,
                value=60,
                step=6,
                help="60장 이상 권장: 색상/톤/장면 다양성 확보",
            )
        with col_slider2:
            st.metric("예상 용량", f"~{st.session_state['yt_target_frames'] * 0.5:.1f}MB")

        col_yt1, col_yt2 = st.columns([1, 1])
        with col_yt1:
            if st.button(
                "🎬 스마트 키프레임 추출 (권장)",
                use_container_width=True,
                disabled=not yt_url.strip(),
            ):
                try:
                    # 캐시 클리어 (안전장치)
                    import importlib

                    import utils.youtube_refs as yrefs

                    importlib.reload(yrefs)
                    from utils.youtube_refs import download_youtube, extract_keyframes

                    YT_DIR = OUT_DIR / "yt_tmp"

                    with st.spinner("유튜브 영상 다운로드 중..."):
                        vid_path = download_youtube(yt_url.strip(), YT_DIR)
                    with st.spinner("스마트 키프레임 추출 중..."):
                        refs = extract_keyframes(
                            video_path=vid_path,
                            save_dir=REF_DIR,
                            target_frames=st.session_state["yt_target_frames"],
                            candidate_fps=3.0,
                            min_sharpness=60.0,
                            hash_thresh=8,
                            min_scene_diff=0.3,
                            resize_width=960,
                        )
                    # 세션에 프레임 경로 저장
                    st.session_state["refs_frames"] = [str(p) for p in refs]
                    LOG.info(f"[D1] smart keyframes extracted: {len(refs)} frames")
                    st.success(f"스마트 키프레임 {len(refs)}장 추출 완료! (outputs/refs)")
                    st.info("💡 중복 제거, 흐림 필터, 장면 다양성 확보로 고품질 레퍼런스 생성")
                except Exception as e:
                    st.error(f"키프레임 추출 실패: {e}")
                    st.code(
                        "필요 패키지: pip install yt-dlp opencv-python imagehash", language="bash"
                    )
                    st.warning("💡 **해결 방법**: 위 Python 경로로 패키지를 설치하세요.")
                    st.code(
                        f'"{sys.executable}" -m pip install yt-dlp opencv-python imagehash',
                        language="bash",
                    )

        with col_yt2:
            if st.button(
                "⚡ 빠른 6장 추출 (MVP)", use_container_width=True, disabled=not yt_url.strip()
            ):
                try:
                    # 캐시 클리어 (안전장치)
                    import importlib

                    import utils.youtube_refs as yrefs

                    importlib.reload(yrefs)
                    from utils.youtube_refs import download_youtube, sample_frames

                    YT_DIR = OUT_DIR / "yt_tmp"

                    with st.spinner("유튜브 영상 다운로드 중..."):
                        vid_path = download_youtube(yt_url.strip(), YT_DIR)
                    with st.spinner("프레임 추출 중..."):
                        refs = sample_frames(
                            vid_path, REF_DIR, num_frames=6, start_sec=3.0, end_sec=None
                        )
                    # 세션에 프레임 경로 저장
                    st.session_state["refs_frames"] = [str(p) for p in refs]
                    LOG.info(f"[D1] quick frames extracted: {len(refs)} frames")
                    st.success(
                        f"빠른 레퍼런스 {len(refs)}장 추출 완료. D3에서 자동으로 사용됩니다."
                    )
                except Exception as e:
                    st.error(f"레퍼런스 추출 실패: {e}")
                    st.code("필요 패키지: pip install yt-dlp opencv-python", language="bash")
                    st.warning("💡 **해결 방법**: 위 Python 경로로 패키지를 설치하세요.")
                    st.code(
                        f'"{sys.executable}" -m pip install yt-dlp opencv-python', language="bash"
                    )

        st.divider()
        ref_desc = st.text_input("레퍼런스(선택): 이미지/영상 키워드")

        # 원-클릭 버튼
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("⚡ 원-클릭: 브리프 + 샷리스트", use_container_width=True):
                if not user_text.strip():
                    st.warning("요구사항을 입력해 주세요.")
                    return

                with st.spinner("브리프 생성 중..."):
                    brief = generate_brief(user_text, ref_desc or None)
                    st.session_state["brief"] = brief  # dict 객체로 저장
                    st.session_state["shotlist"] = brief  # 호환성
                    save_json_util(brief, OUT_DIR / "brief.json")

                with st.spinner("샷리스트 생성 중..."):
                    shots = generate_shotlist(brief)
                    st.session_state["shots"] = shots
                    st.session_state["shotlist"] = shots  # 호환성
                    save_json_util(shots, OUT_DIR / "shots.json")

                st.success("D2 완료! D3로 이동합니다.")
                # D3로 자동 전환
                st.session_state["active_tab"] = "D3 · Style & Refs"
                st.rerun()

        with col2:
            st.write("← 이 버튼 하나면 D2는 끝!")

        st.divider()
        st.write("**개별 실행** (원-클릭 사용 시 생략 가능)")
        c1, c2 = st.columns(2)
        if c1.button("1) 브리프 생성"):
            with st.spinner("브리프 생성 중..."):
                brief = generate_brief(user_text, ref_desc or None)
                st.session_state["brief"] = brief  # dict 객체로 저장
                save_json(brief, Path(ROOT) / "outputs/briefs/brief_latest.json")
                st.success("브리프 생성 완료")
                st.code(jsonlib.dumps(brief, ensure_ascii=False, indent=2), "json")
        if c2.button("2) 샷리스트 생성"):
            if "brief" not in st.session_state:
                st.warning("먼저 브리프를 생성하세요.")
            else:
                with st.spinner("샷리스트 생성 중..."):
                    shots = generate_shotlist(st.session_state["brief"])
                    st.session_state["shots"] = shots
                    save_json(shots, Path(ROOT) / "outputs/briefs/shotlist_latest.json")
                    total = sum(s["dur"] for s in shots)
                    st.success(f"샷리스트 생성 완료 · 총 {total:.1f}s")
                    st.code(jsonlib.dumps(shots, ensure_ascii=False, indent=2), "json")


def render_d3():
    st.title("AdGen MVP · D3 Style & Refs")
    st.write(
        "레퍼런스 이미지로 팔레트를 뽑고, 브리프 기반 스타일 가이드와 오버레이 플랜을 생성합니다."
    )

    # 세션 복구 기능 (새 탭/새 세션 대비)
    import re

    OUTPUTS = Path("outputs")

    def _to_number(v):
        """'1.2', '00:05.3' 같은 문자열도 float(초)로 바꿔줍니다."""
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            s = v.strip()
            m = re.match(r"^(\d+):(\d+)(?:\.(\d+))?$", s)  # mm:ss(.ms) 포맷 허용
            if m:
                mm, ss, ms = m.groups()
                sec = int(mm) * 60 + int(ss)
                if ms:
                    sec += int(ms) / (10 ** len(ms))
                return float(sec)
            try:
                return float(s)
            except:
                return 0.0
        return 0.0

    def normalize_shots(raw):
        """
        raw 가 다음 중 어떤 형태여도 -> List[Dict] 로 변환
          - str (JSON 문자열)
          - Dict ({"shots": [...]})
          - List[str] (각 요소가 JSON 문자열)
          - List[Dict]
        """
        if raw is None:
            return []

        # 최상위가 문자열이면 JSON 파싱 시도
        if isinstance(raw, str):
            try:
                raw = jsonlib.loads(raw)
            except:
                # 문자열 하나만 온 경우: 캡션만 있는 기본 샷으로
                return [{"t": 0.0, "dur": 1.5, "type": "cut", "caption": raw}]

        # {"shots": [...]} 형태면 꺼내기
        if isinstance(raw, dict) and "shots" in raw:
            raw = raw["shots"]

        out = []
        for s in raw or []:
            if isinstance(s, str):
                # 요소가 문자열이면 JSON 파싱 시도
                try:
                    s = jsonlib.loads(s)
                except:
                    s = {"caption": s}

            if not isinstance(s, dict):
                s = {}

            out.append(
                {
                    "t": _to_number(s.get("t", 0)),
                    "dur": _to_number(s.get("dur", 1.5)),
                    "type": s.get("type", "cut"),
                    "caption": s.get("caption", ""),
                }
            )
        return out

    # 세션에 없으면 파일에서 복구
    if "brief" not in st.session_state or not st.session_state.get("brief"):
        try:
            brief_file = OUTPUTS / "brief.json"
            if brief_file.exists():
                with open(brief_file, encoding="utf-8") as f:
                    brief_data = jsonlib.load(f)
                    if isinstance(brief_data, dict) and "content" in brief_data:
                        st.session_state["brief"] = _coerce_json_dict(brief_data["content"])
                    else:
                        st.session_state["brief"] = _coerce_json_dict(brief_data)
                st.info("📁 파일에서 브리프를 복구했습니다.")
        except Exception as e:
            st.warning(f"브리프 파일 복구 실패: {e}")

    # shotlist / shots 키 정리
    if "shots" not in st.session_state or not st.session_state.get("shots"):
        # 1) 세션에 shotlist 있으면 그대로 shots로 복사
        if "shotlist" in st.session_state and st.session_state["shotlist"]:
            st.session_state["shots"] = st.session_state["shotlist"]
            st.info("📁 세션에서 샷리스트를 복구했습니다.")
        else:
            # 2) 디스크에 shots.json 이 있으면 로드
            try:
                shots_file = OUTPUTS / "shots.json"
                if shots_file.exists():
                    with open(shots_file, encoding="utf-8") as f:
                        st.session_state["shots"] = jsonlib.load(f)
                    st.info("📁 파일에서 샷리스트를 복구했습니다.")
            except Exception as e:
                st.warning(f"샷리스트 파일 복구 실패: {e}")

    # shots 정규화 실행 (문자열 → List[Dict] 변환)
    shots_raw = st.session_state.get("shots") or st.session_state.get("shotlist")
    shots = normalize_shots(shots_raw)
    st.session_state["shots"] = shots  # 이후부터는 항상 List[Dict] 로 보장

    LOG.info(
        f"[D2] brief keys={list(st.session_state['brief'].keys()) if isinstance(st.session_state['brief'], dict) else type(st.session_state['brief'])}"
    )
    LOG.info(
        f"[D2] shotlist len={len(st.session_state['shots']) if isinstance(st.session_state['shots'], list) else type(st.session_state['shots'])}"
    )

    # 디버그 정보 (개발 중에만)
    st.sidebar.caption("Shots Debug")
    st.sidebar.write(f"shots type: {type(shots)}")
    st.sidebar.write(f"shots count: {len(shots)}")
    if shots:
        st.sidebar.write(f"first shot: {shots[0]}")

    # D3가 빈화면으로 보이지 않도록, 조건 미충족 시 안내 메시지 출력
    s = st.session_state
    if not s.get("brief") or not s.get("shots"):
        st.warning("D2에서 브리프/샷리스트를 먼저 생성하세요.")
        st.info("💡 D2에서 '레퍼런스 기반 브리프 생성' 버튼을 눌러주세요.")
        return

    if not HAS_D3:
        st.error("D3 모듈 임포트 실패: services/style_guide.py 또는 prompts/style_prompt.md 확인")
        if D3_IMPORT_ERR:
            st.exception(D3_IMPORT_ERR)
        st.code("필수 파일:\n  prompts/style_prompt.md\n  services/style_guide.py")
    else:
        up = st.file_uploader(
            "레퍼런스 이미지(최대 6장)",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
        )
        extra_kw = st.text_input(
            "추가 키워드(선택)", placeholder="우드톤, 따뜻한 조명, 필름그레인…"
        )

        def _save_refs(files):
            REF_DIR.mkdir(parents=True, exist_ok=True)
            saved = []
            for f in files:
                p = REF_DIR / f.name
                p.write_bytes(f.read())
                saved.append(p)
            return saved

        # 원-클릭 버튼 (항상 보이되, 조건 체크는 내부에서)
        do_all = st.button(
            "🚀 원-클릭: 팔레트→스타일→오버레이→프리뷰 렌더", use_container_width=True
        )
        if do_all:
            ref_paths = []
            if up:
                ref_paths = _save_refs(up)
            elif s.get("refs_frames"):
                # 유튜브에서 추출한 프레임 사용
                ref_paths = [Path(p) for p in s["refs_frames"]]

            # 1) 팔레트
            with st.spinner("팔레트 추출 중..."):
                if ref_paths:
                    palette = extract_palette(ref_paths, k=5)
                else:
                    palette = st.session_state.get("brief", {}).get("colors", []) or [
                        "#F5EDE0",
                        "#2C2C2C",
                    ]
                st.session_state["palette"] = palette
                save_json_util(palette, OUT_DIR / "palette.json")

            # 2) 스타일 가이드
            with st.spinner("스타일 가이드 생성 중..."):
                style = summarize_style(st.session_state["brief"], palette, extra_kw or None)
                st.session_state["style"] = style
                st.session_state["style_guide"] = style  # 호환성
                save_json_util(style, OUT_DIR / "style.json")

            # 3) 오버레이 플랜
            with st.spinner("오버레이 플랜 생성 중..."):
                overlays = build_overlay_plan(st.session_state["shots"], style)
                st.session_state["overlays"] = overlays
                st.session_state["overlay_plan"] = overlays  # 호환성
                save_json_util(overlays, OUT_DIR / "overlays.json")

            # 4) 레시피 생성 및 저장
            with st.spinner("레시피 생성 중..."):
                recipe = build_recipe_from_session()
                if recipe:
                    save_recipe(recipe)
                    st.session_state["recipe"] = recipe
                    LOG.info("[D3] recipe created and saved")
                else:
                    LOG.warning("[D3] failed to create recipe")

            # 5) D4 프리뷰 렌더
            with st.spinner("프리뷰 렌더 중... (mp4)"):
                # 캐시 버스터로 매번 새 파일명 생성
                import time

                out_path = VID_DIR / f"preview_d4_{int(time.time())}.mp4"
                render_preview(
                    shots=st.session_state["shots"],
                    style=style,
                    overlays=overlays,
                    out_path=out_path,
                )
                st.session_state["preview_video"] = str(out_path)

            st.success("렌더 완료! D4로 이동합니다.")
            # D3에서도 바로 미리보기
            preview_path = st.session_state["preview_video"]
            if preview_path and _os.path.exists(preview_path):
                try:
                    # 바이트로 읽어서 매번 새 ID 생성 (임시 ID 재사용 방지)
                    video_data = Path(preview_path).read_bytes()
                    st.video(video_data, format="video/mp4")
                    st.download_button(
                        "mp4 다운로드",
                        video_data,
                        file_name=Path(preview_path).name,
                        mime="video/mp4",
                    )
                except Exception as e:
                    st.error(f"미리보기 표시 실패: {e}")
                    st.info(f"파일 경로: {preview_path}")
            else:
                st.warning("미리보기 파일을 찾을 수 없습니다")

            # D4로 자동 전환
            st.session_state["active_tab"] = "D4 · Preview Render"
            st.rerun()

        # 현재 세션 상태 디버그
        with st.expander("세션 상태 확인(디버그)"):
            st.json(
                {
                    "has_brief": st.session_state.get("brief") is not None,
                    "has_shots": st.session_state.get("shots") is not None,
                    "has_palette": st.session_state.get("palette") is not None,
                    "has_style": st.session_state.get("style") is not None,
                    "has_overlays": st.session_state.get("overlays") is not None,
                    "preview_video": st.session_state.get("preview_video"),
                }
            )

        st.divider()
        st.write("**개별 실행** (원-클릭 사용 시 생략 가능)")
        c1, c2 = st.columns(2)

        if c1.button("1) 팔레트 추출"):
            LOG.info(f"[D3] palette extraction started. has_upload={bool(up)}")
            if not up:
                # 브리프 colors가 있으면 그걸 사용(백업 경로)
                brief_obj = coerce_json_dict(st.session_state.get("brief"))
                pal = brief_obj.get("colors", []) or ["#F5EDE0", "#2C2C2C"]
                st.session_state["palette"] = pal
                save_json_d3(pal, Path(ROOT) / "outputs/briefs/palette_latest.json")
                LOG.info(f"[D3] palette from brief: {pal}")
                st.warning("이미지 없음 → 브리프 colors/기본 팔레트 사용")
            else:
                tmp_dir = Path(ROOT) / "outputs/refs"
                tmp_dir.mkdir(parents=True, exist_ok=True)
                paths = []
                for f in up[:6]:
                    p = tmp_dir / f.name
                    with open(p, "wb") as w:
                        w.write(f.read())
                    paths.append(p)
                pal = extract_palette(paths, k=5)
                st.session_state["palette"] = pal
                save_json_d3(pal, Path(ROOT) / "outputs/briefs/palette_latest.json")
                LOG.info(f"[D3] palette from upload: {pal}")
            st.success(f"팔레트: {st.session_state['palette']}")

        if c2.button("2) 스타일 가이드 생성"):
            if "brief" not in st.session_state:
                st.warning("먼저 D2에서 브리프를 생성하세요.")
            else:
                pal = st.session_state.get(
                    "palette", st.session_state["brief"].get("colors", []) or ["#F5EDE0", "#2C2C2C"]
                )
                style = summarize_style(st.session_state["brief"], pal, extra_kw or None)
                st.session_state["style"] = style
                save_json_d3(style, Path(ROOT) / "outputs/briefs/style_guide.json")
                st.success("스타일 가이드 생성 완료")
                st.code(jsonlib.dumps(style, ensure_ascii=False, indent=2), "json")

        if st.button("3) 오버레이 플랜 생성"):
            if "shots" not in st.session_state:
                st.warning("D2에서 샷리스트를 먼저 생성하세요.")
            elif "style" not in st.session_state:
                st.warning("스타일 가이드를 먼저 생성하세요.")
            else:
                overlays = build_overlay_plan(st.session_state["shots"], st.session_state["style"])
                st.session_state["overlays"] = overlays
                save_json_d3(overlays, Path(ROOT) / "outputs/briefs/overlay_plan.json")
                st.success("오버레이 플랜 생성 완료")
                st.code(jsonlib.dumps(overlays, ensure_ascii=False, indent=2), "json")


def render_d4():
    st.title("AdGen MVP · D4 Preview Render")
    st.write("레퍼런스 분석 + 자산을 매핑해서 9:16 모바일 비디오를 생성합니다.")

    # AI 영상 생성 결과 표시
    ai_video = st.session_state.get("ai_generated_video")
    ai_metadata = st.session_state.get("ai_video_metadata")
    
    if ai_video and Path(ai_video).exists():
        st.subheader("🤖 AI 영상 생성 결과 (SVD)")
        try:
            with open(ai_video, "rb") as f:
                st.video(f.read(), format="video/mp4")
            
            # 메타데이터 표시
            if ai_metadata:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("생성 시간", f"{ai_metadata.get('duration', 0):.1f}초")
                with col2:
                    st.metric("프레임 수", ai_metadata.get('num_frames', 0))
                with col3:
                    st.metric("해상도", ai_metadata.get('resolution', 'N/A'))
            
            st.download_button(
                "📥 AI 영상 다운로드",
                Path(ai_video).read_bytes(),
                file_name=Path(ai_video).name,
                mime="video/mp4",
            )
            st.success("✅ AI 영상 생성이 완료되었습니다!")
        except Exception as e:
            st.error(f"AI 영상 표시 실패: {e}")
    
    # 원클릭 자동 생성 결과 표시
    out_path = st.session_state.get("last_video")
    if out_path and Path(out_path).exists():
        st.subheader("🎥 원클릭 자동 생성 결과")
        try:
            with open(out_path, "rb") as f:
                st.video(f.read(), format="video/mp4")  # 파일ID 대신 바이트 직접 전달
            st.download_button(
                "📥 비디오 다운로드",
                Path(out_path).read_bytes(),
                file_name=Path(out_path).name,
                mime="video/mp4",
            )
            st.success("✅ 원클릭 자동 생성이 완료되었습니다!")
        except Exception as e:
            st.error(f"비디오 표시 실패: {e}")
    elif out_path:
        st.warning(f"렌더 결과 파일을 찾을 수 없습니다: {out_path}")
    elif not ai_video:
        st.info("💡 D2에서 '제품 1개로 자동 생성' 또는 '🤖 AI 영상 생성 (SVD)' 버튼을 실행하세요.")

    # 디버그 패널 추가
    with st.expander("🔎 디버그(레시피 탐색 상태)"):
        rdir = ROOT / "outputs" / "recipes"
        st.write("session recipe:", isinstance(st.session_state.get("recipe"), dict))
        st.write("session recipe_path:", st.session_state.get("recipe_path"))
        st.write("latest exists:", (rdir / "recipe_latest.json").exists())
        st.write("dir:", str(rdir))
        st.write("files:", [p.name for p in rdir.glob("*.json")] if rdir.exists() else "없음")

        # 레시피 내용 진단
        recipe = find_latest_recipe()
        if recipe:
            # 정규화된 레시피로 진단
            uploaded_assets = st.session_state.get("assets_meta") or {}
            normalized_recipe = normalize_recipe(recipe, uploaded_assets)

            tl = normalized_recipe.get("timeline", [])
            assets = normalized_recipe.get("assets", {})
            st.write("timeline len:", len(tl))
            st.write("assets keys:", list(assets.keys()))
            st.write("first 3 shots:", tl[:3] if tl else "없음")

            # 자산 파일 존재 확인
            missing_assets = []
            for key, path in assets.items():
                if not Path(path).exists():
                    missing_assets.append(f"{key}: {path}")
            if missing_assets:
                st.error("Missing assets:")
                for ma in missing_assets:
                    st.write(f"- {ma}")
            else:
                st.success("All assets found")

            # 레시피 검증 미리보기
            errs = validate_recipe(normalized_recipe)
            if errs:
                st.error("Recipe validation errors:")
                for err in errs:
                    st.write(f"- {err}")
            else:
                st.success("Recipe validation passed")

    # 세션 복구 기능 (새 탭/새 세션 대비)

    OUTPUTS = Path("outputs")

    # 세션에 없으면 파일에서 복구
    if "brief" not in st.session_state or not st.session_state.get("brief"):
        try:
            brief_file = OUTPUTS / "brief.json"
            if brief_file.exists():
                with open(brief_file, encoding="utf-8") as f:
                    brief_data = jsonlib.load(f)
                    if isinstance(brief_data, dict) and "content" in brief_data:
                        st.session_state["brief"] = _coerce_json_dict(brief_data["content"])
                    else:
                        st.session_state["brief"] = _coerce_json_dict(brief_data)
                st.info("📁 파일에서 브리프를 복구했습니다.")
        except Exception as e:
            st.warning(f"브리프 파일 복구 실패: {e}")

    # shotlist / shots 키 정리
    if "shots" not in st.session_state or not st.session_state.get("shots"):
        # 1) 세션에 shotlist 있으면 그대로 shots로 복사
        if "shotlist" in st.session_state and st.session_state["shotlist"]:
            st.session_state["shots"] = st.session_state["shotlist"]
            st.info("📁 세션에서 샷리스트를 복구했습니다.")
        else:
            # 2) 디스크에 shots.json 이 있으면 로드
            try:
                shots_file = OUTPUTS / "shots.json"
                if shots_file.exists():
                    with open(shots_file, encoding="utf-8") as f:
                        st.session_state["shots"] = jsonlib.load(f)
                    st.info("📁 파일에서 샷리스트를 복구했습니다.")
            except Exception as e:
                st.warning(f"샷리스트 파일 복구 실패: {e}")

    # 렌더링 조건 확인
    s = st.session_state
    if not s.get("recipe_with_checklist"):
        st.info("D2에서 레퍼런스 분석과 자산 업로드를 먼저 완료해 주세요.")
        return

    if not s.get("assets_saved"):
        st.info("D2에서 자산 저장을 먼저 완료해 주세요.")
        return

    # 자산 및 타임라인 실시간 검증 패널
    def debug_assets_panel(assets: dict):
        """자산 상태 디버그 패널"""
        if not assets:
            st.warning("자산이 설정되지 않았습니다.")
            return

        st.subheader("📋 자산 상태")
        rows = []
        for key, path in assets.items():
            exists = path and _os.path.exists(str(path))
            file_size = ""
            if exists:
                try:
                    size_bytes = _os.path.getsize(str(path))
                    if size_bytes > 1024 * 1024:
                        file_size = f"{size_bytes / (1024 * 1024):.1f}MB"
                    else:
                        file_size = f"{size_bytes / 1024:.1f}KB"
                except:
                    file_size = "크기 불명"
            rows.append(
                {
                    "자산": key,
                    "경로": str(path)[:50] + "..." if len(str(path)) > 50 else str(path),
                    "존재": "✅" if exists else "❌",
                    "크기": file_size,
                }
            )

        st.dataframe(rows, use_container_width=True)

        # 썸네일 미리보기 (이미지만)
        st.subheader("🖼️ 자산 썸네일")
        cols = st.columns(min(4, len(assets)))
        for i, (key, path) in enumerate(assets.items()):
            if i >= 4:  # 최대 4개만 표시
                break
            with cols[i]:
                if path and _os.path.exists(str(path)):
                    file_ext = Path(path).suffix.lower()
                    if file_ext in [".jpg", ".jpeg", ".png", ".webp"]:
                        try:
                            st.image(str(path), caption=key, width=140)
                        except Exception:
                            st.caption(f"{key}: 이미지 로드 실패")
                    elif file_ext in [".mp4", ".mov", ".avi"]:
                        st.caption(f"{key}: 비디오 파일")
                    else:
                        st.caption(f"{key}: {file_ext} 파일")
                else:
                    st.caption(f"{key}: 파일 없음")

    def validate_timeline(timeline: list) -> list:
        """타임라인 검증 및 오류 목록 반환"""
        errors = []
        last_end = 0.0

        from utils.diagnostics import heartbeat, loop_guard
        
        guard = loop_guard("timeline_validation", max_iter=1000, warn_every=100)
        for i, shot in enumerate(timeline):
            heartbeat("timeline_validation")
            guard.tick({"shot_index": i, "total_shots": len(timeline)})
            
            # 시간 범위 추출
            start_time, end_time = shot_bounds(shot)
            duration = end_time - start_time

            # 지속시간 검증
            if duration <= 0:
                errors.append(f"샷#{i}: 지속시간<=0 ({duration:.2f}s)")

            # 겹침 검증
            if start_time < last_end:
                errors.append(
                    f"샷#{i}: 이전 샷과 겹침 (시작={start_time:.2f}s < 이전종료={last_end:.2f}s)"
                )

            last_end = max(last_end, end_time)

            # 레이어 검증
            layers = shot.get("layers", [])
            if not layers:
                errors.append(f"샷#{i}: 레이어가 없음")

        return errors

    # 자산 상태 표시
    current_assets = st.session_state.get("assets", {})
    if current_assets:
        with st.expander("🔍 자산 및 타임라인 검증", expanded=False):
            debug_assets_panel(current_assets)

            # 타임라인 검증
            recipe = find_latest_recipe()
            if recipe:
                timeline = recipe.get("timeline", [])
                if timeline:
                    st.subheader("⏱️ 타임라인 검증")
                    errors = validate_timeline(timeline)

                    if errors:
                        st.error("타임라인 오류:")
                        for error in errors:
                            st.write(f"- {error}")
                    else:
                        st.success(f"✅ 타임라인 검증 통과 ({len(timeline)}개 샷)")

                        # 타임라인 요약
                        total_duration = sum(shot_duration(shot) for shot in timeline)
                        st.metric("총 길이", f"{total_duration:.1f}초")
                else:
                    st.warning("타임라인이 비어있습니다.")
            else:
                st.warning("레시피를 찾을 수 없습니다.")

    # Safe Render 토글 (디버그용)
    safe_mode = st.toggle(
        "🧪 Safe Render (베이스만)",
        value=False,
        help="오버레이(텍스트/비네트/그레인/글로우/solid) 전부 비활성화하고 베이스(제품/스토어/broll)만 합성",
    )

    if safe_mode:
        st.info("🧪 Safe Mode: 오버레이 없이 베이스 레이어만 렌더링합니다")

    # 렌더링 설정
    st.subheader("🎬 렌더링 설정")

    col1, col2, col3 = st.columns(3)
    with col1:
        style_option = st.selectbox(
            "스타일 팩",
            ["기본 스타일", "Serene Minimal Gold"],
            index=1,
            help="영상 스타일을 선택하세요",
        )
    with col2:
        max_shots = st.slider(
            "최대 샷 수", min_value=6, max_value=24, value=9, help="렌더링할 최대 샷 수"
        )
    with col3:
        quality = st.selectbox(
            "화질 설정", ["고화질 (6Mbps)", "중화질 (4Mbps)", "저화질 (2Mbps)"], index=1
        )

    # 화질별 비트레이트 설정
    bitrate_map = {"고화질 (6Mbps)": "6M", "중화질 (4Mbps)": "4M", "저화질 (2Mbps)": "2M"}
    selected_bitrate = bitrate_map[quality]

    # 샷0 미리보기 버튼 (디버그용)
    col_debug1, col_debug2 = st.columns(2)
    with col_debug1:
        if st.button("🔬 샷0 미리보기 (디버그)", use_container_width=True):
            # 레시피 로드
            recipe = find_latest_recipe()
            if recipe is None:
                recipe = build_recipe_from_session()
                if recipe:
                    save_recipe(recipe)

            if recipe:
                timeline = recipe.get("timeline", [])
                if timeline:
                    # 자산 검증
                    asset_map = resolve_assets(st.session_state.get("assets"))
                    if not asset_map:
                        st.error("자산을 먼저 설정해주세요.")
                        st.stop()

                    with st.spinner("샷0 미리보기 생성 중..."):
                        from services.render_engine import render_single_shot_preview

                        # 첫 번째 샷으로 미리보기
                        first_shot = timeline[0]
                        result = render_single_shot_preview(
                            first_shot, asset_map, "outputs", safe_mode
                        )

                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.success("✅ 샷0 미리보기 완료!")

                            # 프레임 분산 정보
                            variance = result.get("variance", 0)
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("프레임 분산", f"{variance:.2f}")
                            with col2:
                                if variance < 10:
                                    st.error("⚠️ 분산 낮음 (흑/회색 화면 의심)")
                                else:
                                    st.success("✅ 정상 분산")

                            # 프레임 이미지 표시
                            frame_path = result.get("frame_path")
                            if frame_path and _os.path.exists(frame_path):
                                st.image(frame_path, caption="0.1초 시점 프레임")

                            # 미리보기 비디오 표시
                            video_path = result.get("video_path")
                            if video_path and _os.path.exists(video_path):
                                try:
                                    video_data = Path(video_path).read_bytes()
                                    st.video(video_data, format="video/mp4")
                                except Exception as e:
                                    st.error(f"비디오 표시 실패: {e}")

                            # 경고 메시지
                            warning = result.get("warning")
                            if warning:
                                st.error(f"⚠️ {warning}")
                                st.info("💡 오버레이 마스크/순서를 확인하세요!")
                else:
                    st.error("타임라인이 비어있습니다.")
            else:
                st.error("레시피를 찾을 수 없습니다.")

    with col_debug2:
        st.caption("빠른 진단으로 첫 샷의 상태를 확인")

    # 렌더링 시작
    if st.button("🚀 렌더링 시작", type="primary", use_container_width=True):
        from utils.diagnostics import heartbeat
        
        heartbeat("render_start")
        
        # 자산 검증 (영구 경로 확인)
        asset_map = resolve_assets(st.session_state.get("assets"))
        if not asset_map.get("product"):
            st.error("필수 자산 'product'가 없습니다. D2에서 제품 영상을 업로드해주세요.")
            st.stop()

        heartbeat("asset_validation_complete")
        st.success(f"✅ 자산 검증 완료: {list(asset_map.keys())}")

        # 스타일에 따른 레시피 생성
        if style_option == "Serene Minimal Gold":
            # 1-소스 모드 확인
            one_src_mode = st.session_state.get("one_source_mode", False)

            if one_src_mode:
                # 레퍼런스 분석 결과를 사용하여 타임라인 매핑
                ref_recipe = st.session_state.get("recipe", {})
                ref_shots = ref_recipe.get("shots", [])

                if ref_shots:
                    # 레퍼런스의 길이/전환 패턴을 추출
                    ref_timeline = []
                    for shot in ref_shots:
                        ref_timeline.append(
                            {
                                "dur": shot.get("t1", 2.0) - shot.get("t0", 0.0),
                                "xfade": "cross",  # 기본 전환
                            }
                        )

                    # 제품 전용 타임라인으로 매핑
                    mapped_timeline = map_to_product_only(ref_timeline, asset_map)
                    normalized_timeline = normalize_and_fill(mapped_timeline)

                    # 커스텀 레시피 생성
                    recipe = {
                        "canvas": {"w": 1080, "h": 1920, "fps": 30, "bitrate": "6M"},
                        "assets": asset_map,
                        "timeline": normalized_timeline,
                        "overlays": SERENE_MINIMAL_OVERLAYS,
                        "style": "serene_minimal_gold_auto",
                    }

                    st.info(f"🪄 1-소스 자동 생성: {len(normalized_timeline)}개 샷 매핑 완료")
                    st.info(
                        f"📊 레퍼런스 패턴: {len(ref_shots)}개 샷 → {len(normalized_timeline)}개 샷"
                    )
                else:
                    # 레퍼런스가 없으면 기본 Serene Minimal Gold 스타일
                    recipe = create_serene_minimal_recipe(asset_map)
                    st.info("🎨 Serene Minimal Gold 기본 스타일 적용")
            else:
                # 일반 Serene Minimal Gold 스타일 레시피 생성
                recipe = create_serene_minimal_recipe(asset_map)
                st.info("🎨 Serene Minimal Gold 스타일 적용")
        else:
            # 기본 스타일 (기존 레시피 시스템)
            recipe = find_latest_recipe()
            if recipe is None:
                # 즉석 생성 시도
                recipe = build_recipe_from_session()
                if recipe:
                    save_recipe(recipe)  # 생성되면 저장
                    st.info("✅ 레시피를 즉석 생성했습니다.")
                else:
                    st.error(
                        "레시피 파일을 찾을 수 없고, 즉석 생성도 실패했습니다.\n"
                        "→ D3에서 스타일 가이드/오버레이를 먼저 생성해 주세요."
                    )
                    # 디버그에 경로들도 보여주면 원인 파악이 쉬움
                    rdir = ROOT / "outputs" / "recipes"
                    st.info(f"확인 경로: {rdir}\\recipe_latest.json / recipe_*.json")
                    st.stop()

            # 핫픽스: 레시피 정규화 (스키마 변환 + 자산 키 매핑)
            # 검증된 자산 맵을 사용
            recipe["assets"] = asset_map
            recipe = normalize_recipe(recipe, st.session_state.get("assets_meta") or {})

            # 타임라인 정규화 적용
            if "timeline" in recipe:
                recipe["timeline"] = normalize_timeline(recipe["timeline"])

        LOG.info(
            f"[RECIPE] normalized - timeline: {len(recipe.get('timeline', []))}, assets: {list(recipe.get('assets', {}).keys())}"
        )

        # 레시피 검증
        errs = validate_recipe(recipe)
        if errs:
            st.error("레시피 오류:\n- " + "\n- ".join(errs))
            st.stop()

        # 여기서부터 실제 렌더 호출
        try:
            from services.render_engine import create_subtitle_srt, get_video_info, render_video

            # 출력 경로 설정 (캐시 버스터)
            output_dir = Path("outputs/videos")
            output_dir.mkdir(parents=True, exist_ok=True)
            import time

            output_path = output_dir / f"out_{int(time.time())}.mp4"
            LOG.debug("[D4] writing preview -> %s", output_path)

            LOG.info(f"[D4] render start → {output_path}")

            # 자산 디렉토리 찾기
            assets_dir = None
            for item in Path("assets").glob("project_*"):
                if item.is_dir():
                    assets_dir = str(item)
                    break

            if not assets_dir:
                st.error("자산 디렉토리를 찾을 수 없습니다. D2에서 자산을 저장해주세요.")
                return

            # 레시피를 임시 파일로 저장 (렌더 엔진이 파일을 요구하는 경우)
            recipe_path = Path(assets_dir) / "recipe.json"
            with open(recipe_path, "w", encoding="utf-8") as f:
                jsonlib.dump(recipe, f, ensure_ascii=False, indent=2)

            # 진행률 표시
            progress_bar = st.progress(0)
            status_text = st.empty()

            def progress_callback(percent, message):
                progress_bar.progress(percent / 100)
                status_text.text(f"{message} ({percent}%)")

            # 렌더링 실행
            with st.spinner("렌더링 중..."):
                used_assets = render_video(
                    str(recipe_path), assets_dir, str(output_path), progress_callback, safe_mode
                )

            LOG.info(
                f"[D4] write done. exists={output_path.exists()} size={output_path.stat().st_size if output_path.exists() else 0}"
            )
            wait_until_written(output_path)
            LOG.debug(
                "[D4] write done -> exists=%s size=%s",
                output_path.exists(),
                output_path.stat().st_size if output_path.exists() else -1,
            )

            # 자막 생성
            try:
                with open(recipe_path, encoding="utf-8") as f:
                    recipe = jsonlib.load(f)
                srt_path = create_subtitle_srt(recipe, str(output_path))
                if srt_path:
                    st.success(f"자막 파일 생성: {srt_path}")
            except Exception as e:
                st.warning(f"자막 생성 실패: {e}")

            # 결과 표시
            st.success("렌더 요청 완료. 아래 미리보기를 확인해 주세요.")

            # ffprobe 진단
            info = ffprobe_json(output_path)
            LOG.info(f"[D4] video meta: {info}")

            # 비디오 정보 표시
            video_info = get_video_info(str(output_path))
            if video_info:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("파일 크기", f"{video_info['file_size_mb']} MB")
                with col2:
                    st.metric("길이", f"{video_info['duration_seconds']}초")
                with col3:
                    st.metric("해상도", video_info["resolution"])
                with col4:
                    st.metric("FPS", f"{video_info['fps']:.1f}")

            # 비디오 미리보기 (바이트 방식)
            st.subheader("🎥 렌더링 결과")
            try:
                video_data = Path(output_path).read_bytes()
                LOG.info(f"[D4] video bytes len={len(video_data)}")
                st.video(video_data, format="video/mp4")
                st.download_button(
                    "mp4 다운로드",
                    video_data,
                    file_name=Path(output_path).name,
                    mime="video/mp4",
                )
            except Exception as e:
                LOG.error(f"[D4] video preview failed: {e}")
                st.error(f"비디오 미리보기 실패: {e}")
                st.info(f"파일 경로: {output_path}")

            # 다운로드 버튼
            with open(output_path, "rb") as file:
                st.download_button(
                    label="📥 비디오 다운로드",
                    data=file.read(),
                    file_name=Path(output_path).name,
                    mime="video/mp4",
                )

            # 사용된 자산 정보
            st.subheader("📋 사용된 자산")
            st.json(used_assets)

            # 세션에 결과 저장 (파일 경로만 저장)
            st.session_state["rendered_video"] = str(output_path)
            st.session_state["render_complete"] = True

            # 파일 존재 확인
            if _os.path.exists(output_path):
                st.session_state["video_file_exists"] = True
            else:
                st.session_state["video_file_exists"] = False

        except Exception as e:
            st.error(f"렌더링 실패: {str(e)}")
            st.exception(e)

            # 재시도 버튼
            if st.button("🔄 재시도"):
                st.rerun()

    # 렌더링 완료 상태 표시
    if st.session_state.get("render_complete") and st.session_state.get("rendered_video"):
        # 렌더링된 비디오 경로
        rendered_video = st.session_state["rendered_video"]

        # 파일 존재 확인
        if not _os.path.exists(rendered_video):
            st.error(f"렌더링된 비디오 파일을 찾을 수 없습니다: {rendered_video}")
            st.info("다시 렌더링해 주세요.")
            return

        st.success("✅ 렌더링이 완료되었습니다! 아래에서 결과를 확인하고 다운로드하세요.")

        # 자산 디렉토리에서 레시피 파일 찾기
        recipe_path = None
        srt_path = None

        for item in Path("assets").glob("project_*"):
            if item.is_dir():
                recipe_path = item / "recipe.json"
                srt_path = Path(rendered_video).parent / "subtitle.srt"
                break

        if recipe_path and recipe_path.exists():
            # 비디오 미리보기 (파일 경로 사용)
            st.subheader("🎥 렌더링 결과")

            # 파일 경로가 유효한지 다시 한번 확인
            if rendered_video and _os.path.exists(rendered_video):
                try:
                    # 바이트로 읽어서 매번 새 ID 생성 (임시 ID 재사용 방지)
                    video_data = Path(rendered_video).read_bytes()
                    st.video(video_data, format="video/mp4")
                    st.download_button(
                        "mp4 다운로드",
                        video_data,
                        file_name=Path(rendered_video).name,
                        mime="video/mp4",
                    )
                except Exception as e:
                    st.error(f"비디오 미리보기 실패: {e}")
                    st.info(f"파일 경로: {rendered_video}")
            else:
                st.error(f"비디오 파일을 찾을 수 없습니다: {rendered_video}")

            # 다운로드 버튼
            if rendered_video and _os.path.exists(rendered_video):
                try:
                    with open(rendered_video, "rb") as file:
                        st.download_button(
                            label="📥 비디오 다운로드",
                            data=file.read(),
                            file_name=Path(rendered_video).name,
                            mime="video/mp4",
                        )
                except Exception as e:
                    st.error(f"다운로드 버튼 생성 실패: {e}")
            else:
                st.warning("비디오 파일이 없어서 다운로드할 수 없습니다.")

            # 레시피 다운로드
            with open(recipe_path, "rb") as file:
                st.download_button(
                    label="📋 레시피 다운로드",
                    data=file.read(),
                    file_name=Path(recipe_path).name,
                    mime="application/json",
                )

            # 자막 다운로드 (있는 경우)
            if srt_path and srt_path.exists():
                with open(srt_path, "rb") as file:
                    st.download_button(
                        label="📝 자막 다운로드",
                        data=file.read(),
                        file_name=Path(srt_path).name,
                        mime="text/plain",
                    )
        else:
            st.warning("레시피 파일을 찾을 수 없습니다.")

        # 추가 옵션
        st.subheader("🔧 추가 옵션")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📊 렌더링 로그 보기"):
                log_info = {
                    "렌더링 시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "사용된 샷 수": st.session_state.get("recipe_with_checklist", {})
                    .get("meta", {})
                    .get("total_shots", 0),
                    "출력 해상도": "1080x1920",
                    "프레임레이트": "30 FPS",
                    "비트레이트": selected_bitrate,
                }
                st.json(log_info)

        with col2:
            if st.button("🔄 새로 렌더링"):
                st.session_state["render_complete"] = False
                st.rerun()


# ============ 탭별 렌더링 ============
if st.session_state["active_tab"] == "D1 · Healthcheck":
    render_d1()
elif st.session_state["active_tab"] == "D2 · Brief & Shotlist":
    render_d2()
elif st.session_state["active_tab"] == "D3 · Style & Refs":
    # D2 산출물이 없으면 경고
    if not (st.session_state["brief"] and st.session_state["shotlist"]):
        st.warning("먼저 D2에서 브리프/샷리스트를 생성하세요.")
    else:
        render_d3()
elif st.session_state["active_tab"] == "D4 · Preview Render":
    # 원클릭 자동 생성 결과가 있거나 D3 산출물이 있으면 D4 표시
    has_oneclick_result = st.session_state.get("last_video") and Path(st.session_state.get("last_video", "")).exists()
    has_d3_outputs = (
        st.session_state.get("palette")
        and st.session_state.get("style_guide")
        and st.session_state.get("overlay_plan")
    )
    
    if has_oneclick_result:
        render_d4()
    elif has_d3_outputs:
        render_d4()
    else:
        st.warning("먼저 D3에서 팔레트·스타일가이드·오버레이 플랜을 생성하거나, D2에서 원클릭 자동 생성을 실행하세요.")
