# services/pipeline_oneclick.py
from __future__ import annotations
from pathlib import Path
import shutil, json
from typing import Callable, Any, Dict, Tuple
from datetime import datetime

# 프로젝트 루트/출력 폴더
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
ASSETS_DIR = OUT / "assets"
RECIPES_DIR = OUT / "recipes"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
RECIPES_DIR.mkdir(parents=True, exist_ok=True)

def _stage_product(product_file) -> Tuple[str, Path]:
    """
    product_file:  str | Path | Streamlit UploadedFile
    return: (key, saved_path)
    """
    # 확장자
    suffix = ".jpg"
    name = "product"
    if hasattr(product_file, "name"):
        # st.uploaded_file
        src_name = str(product_file.name)
        suffix = Path(src_name).suffix.lower() or ".jpg"
    elif isinstance(product_file, (str, Path)):
        suffix = Path(product_file).suffix.lower() or ".jpg"
    else:
        raise ValueError("Unsupported product_file type")

    dst = ASSETS_DIR / f"{name}{suffix}"

    if hasattr(product_file, "read"):  # Streamlit UploadedFile
        data = product_file.read()
        dst.write_bytes(data)
    else:
        shutil.copyfile(str(product_file), dst)

    return name, dst

def _minimal_recipe(product_key: str, product_path: Path) -> Dict[str, Any]:
    # 9샷 × 2초 = 18초, 가장 단순한 레시피 (D4가 읽어 영상 생성 가능)
    assets = {
        product_key: {"type": "image" if product_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"] else "video",
                      "path": str(product_path)}
    }
    timeline = []
    for i in range(9):
        t0, t1 = i*2, (i+1)*2
        timeline.append({
            "t": [t0, t1],
            "layers": [
                {"type": assets[product_key]["type"], "ref": product_key, "dur": 2}
            ]
        })
    return {"version": 1, "assets": assets, "timeline": timeline}

def one_click_make(product_file, ref_url: str | None, preset: str | None,
                   progress: Callable[[float, str], None] | None = None) -> Dict[str, Any]:
    """
    제품 1개만 받아 최소 레시피를 만들어 저장하고 경로를 반환.
    ref_url / preset 은 있으면 나중에 고급 분석으로 확장 (지금은 무시해도 동작)
    """
    if progress: progress(0.05, "제품 자산 저장")
    key, p_path = _stage_product(product_file)

    if progress: progress(0.15, "레시피 구성")
    recipe = _minimal_recipe(key, p_path)

    ts = int(datetime.now().timestamp())
    latest = RECIPES_DIR / "recipe_latest.json"
    ver = RECIPES_DIR / f"recipe_{ts}.json"
    for p in (latest, ver):
        p.write_text(json.dumps(recipe, ensure_ascii=False, indent=2), encoding="utf-8")

    if progress: progress(0.30, "레시피 저장 완료")
    return {
        "ok": True,
        "recipe_path": str(latest),
        "timeline_len": len(recipe["timeline"]),
        "assets": recipe["assets"],
    }

__all__ = ["one_click_make"]