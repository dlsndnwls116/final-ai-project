from __future__ import annotations
import os, math, json, time
from pathlib import Path
from typing import Callable, Optional, List
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageDraw, ImageFont
import imageio.v2 as iio
import torch

# --- ?�택?? Stable Video Diffusion(SVD) ?�용 ---
_SVD_OK = False
try:
    from diffusers import StableVideoDiffusionPipeline
    _SVD_OK = True
except Exception:
    _SVD_OK = False

Progress = Callable[[int, str], None]  # percent, message

def _progress(cb: Optional[Progress], p: int, msg: str):
    if cb: cb(min(max(p,0),100), msg)

def _load_template(template_path: str) -> dict:
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _wh_from_ratio(ratio: str, height: int = 1920) -> tuple[int,int]:
    w, h = map(int, ratio.split(":"))
    W = int(height * w / h)
    # macro_block_size=1???�용?��?�?16??배수 강제 조정 불필??
    # ?�하???�상??그�?�??��? (1080×1920)
    return (W, height)

def _make_mograph_bg(size: tuple[int,int], palette: List[str], seed: int = 0) -> np.ndarray:
    # ?�전모드(모션그래?? 배경 ?�성 ??가벼�?/?�패??0
    rng = np.random.default_rng(seed)
    W, H = size
    base = np.zeros((H, W, 3), dtype=np.uint8)
    # 그라?�이??
    c1 = tuple(int(palette[0].lstrip("#")[i:i+2], 16) for i in (0,2,4))
    c2 = tuple(int(palette[-1].lstrip("#")[i:i+2], 16) for i in (0,2,4))
    for y in range(H):
        t = y / max(H-1, 1)
        base[y,:,0] = int((1-t)*c1[0] + t*c2[0])
        base[y,:,1] = int((1-t)*c1[1] + t*c2[1])
        base[y,:,2] = int((1-t)*c1[2] + t*c2[2])
    # ?�이???�레???�이�?
    noise = rng.normal(0, 6, (H, W, 3)).astype(np.int16)
    base = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return base

def rgba_over(background_rgb: Image.Image, product_rgba: Image.Image, xy=(0,0)) -> np.ndarray:
    """RGBA ?�품??RGB 배경???�파 ?�성?�여 RGB 8비트 numpy 배열 반환"""
    # PIL?� RGBA ?�성?� PIL ?��?지?�리�?
    bg = background_rgb.convert("RGBA")
    prod = product_rgba.convert("RGBA")
    tmp = Image.new("RGBA", bg.size, (0,0,0,0))
    tmp.paste(prod, xy, prod)  # ?�품???�치???�려?�기
    out = Image.alpha_composite(bg, tmp)  # ?�파 ?��?�??�성
    out = out.convert("RGB")              # writer??RGB 8bit�?
    return np.array(out, dtype=np.uint8)  # uint8 보장

def _compose_product(product_img: Image.Image, bg: Image.Image, cam: Optional[str]) -> np.ndarray:
    # ?�품??중심 배치 + 가�??�이??그림??
    W, H = bg.size
    prod = product_img.convert("RGBA")
    # 가?�자�??�듬�?(Lanczos ?�용)
    prod = prod.resize((int(W*0.55), int(W*0.55*prod.height/prod.width)), Image.LANCZOS)
    
    # 바닥 그림??
    shadow = Image.new("RGBA", prod.size, (0,0,0,0))
    sh = Image.new("L", (prod.size[0], int(prod.size[1]*0.25)), 0)
    draw = ImageDraw.Draw(sh)
    draw.ellipse([0,0,sh.size[0],sh.size[1]*2], fill=160)
    shadow.alpha_composite(Image.merge("RGBA", [sh, sh, sh, sh]))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    
    # 배경??RGB�?변??
    bg_rgb = bg.convert("RGB")
    cx, cy = W//2, int(H*0.6)
    
    # 그림?��? ?�품??각각 ?�성
    # 1. 그림???�성
    shadow_xy = (cx - shadow.size[0]//2, cy)
    result = rgba_over(bg_rgb, shadow, shadow_xy)
    
    # 2. ?�품 ?�성 (그림?��? ?�는 배경??
    prod_xy = (cx - prod.size[0]//2, cy - prod.size[1])
    result_pil = Image.fromarray(result, 'RGB')
    result = rgba_over(result_pil, prod, prod_xy)
    
    return result

def _frames_mograph(shots: list, size: tuple[int,int], fps: int, palette: List[str], seed: int, cb: Progress) -> List[np.ndarray]:
    out = []
    t_acc = 30
    total_frames = sum(int(round(float(s.get("seconds", 1.5)) * fps)) for s in shots)
    frame_count = 0
    
    for i, s in enumerate(shots):
        sec = float(s.get("seconds", 1.5))
        n = int(round(sec*fps))
        bg = _make_mograph_bg(size, palette, seed + i)
        
        for f in range(n):
            # 미세 카메???�블
            dx = int(2*math.sin((t_acc+f)/17))
            dy = int(2*math.cos((t_acc+f)/23))
            frame = Image.fromarray(bg).transform(size, Image.AFFINE, (1,0,dx,0,1,dy), Image.BICUBIC)
            # ?�레???�식 보정: (H,W,3) / uint8 / RGB
            frame = np.asarray(frame.convert("RGB"), dtype=np.uint8)
            out.append(frame)
            frame_count += 1
            
            # 진행�??�데?�트 (???�주)
            if frame_count % 10 == 0:
                progress_pct = 30 + int(25 * frame_count / total_frames)
                _progress(cb, progress_pct, f"배경 ?�성 {frame_count}/{total_frames}")
        
        _progress(cb, 30 + int(25*(i+1)/len(shots)), f"배경 ?�성 {i+1}/{len(shots)}")
        t_acc += n
    return out

def _apply_product_blocks(frames: List[np.ndarray], shots: list, product_path: str, fps: int, cb: Progress) -> List[np.ndarray]:
    img = Image.open(product_path).convert("RGBA")
    out = []
    idx = 0
    for i, s in enumerate(shots):
        sec = float(s.get("seconds", 1.5))
        n = int(round(sec*fps))
        role = s.get("role","")
        for f in range(n):
            base = Image.fromarray(frames[idx]).copy()
            if role in ("product", "cta"):
                cam = s.get("cam")
                composed = _compose_product(img, base, cam)
                # _compose_product가 ?��? (H,W,3) / uint8 / RGB 반환
                out.append(composed)
            else:
                # 배경�??�는 경우???�식 보정
                frame = np.asarray(base.convert("RGB"), dtype=np.uint8)
                out.append(frame)
            idx += 1
        _progress(cb, 55 + int(30*(i+1)/len(shots)), f"?�품 ?�성 {i+1}/{len(shots)}")
    return out

def _write_video(frames: List[np.ndarray], out_path: str, fps: int, cb: Progress):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    
    # imageio.get_writer ?�용?�로 macro_block_size=1 ?�정 가??
    writer = iio.get_writer(
        out_path,
        fps=fps,                   # ?�하??FPS 명시
        codec="libx264",
        quality=None,
        macro_block_size=1,       # 1080 ???��? (16배수 강제 방�?)
        ffmpeg_params=[
            "-pix_fmt", "yuv420p",
            "-crf", "18",
            "-preset", "medium",
            "-movflags", "+faststart",
        ],
    )
    
    # ?�레?�을 ?�나??추�?
    for i, frame in enumerate(frames):
        # ?�레???�식 최종 보장
        frame = np.asarray(frame, dtype=np.uint8)
        assert frame.ndim == 3 and frame.shape[2] == 3 and frame.dtype == np.uint8
        writer.append_data(frame)
        
        if i % 10 == 0:  # 진행�??�데?�트
            progress_pct = 90 + int(10 * i / len(frames))
            _progress(cb, progress_pct, f"비디???�코??{i+1}/{len(frames)}")
    
    writer.close()
    _progress(cb, 100, f"?�료: {out_path}")

def generate_reels(
    product_path: str,
    template_path: str,
    out_path: str,
    use_svd: bool = True,
    progress: Optional[Progress] = None
):
    tpl = _load_template(template_path)
    fps = int(tpl.get("fps", 30))
    pal = tpl.get("palette", ["#222222","#FFFFFF"])
    ratio = tpl.get("ratio", "9:16")
    W,H = _wh_from_ratio(ratio)
    shots = tpl["shots"]

    _progress(progress, 5, "?�플�?로드")
    # 1) 배경(?�전모드: 모션그래?? ??SVD???�션/?�장 모듈
    frames = _frames_mograph(shots, (W,H), fps, pal, seed=42, cb=progress)

    # 2) ?�품 ?�성
    frames2 = _apply_product_blocks(frames, shots, product_path, fps, progress)

    # 3) (?�택) SVD�?미세 카메?�무�?강화 ???�일 ?��?지??짧�? ?�퀀??치환 로직?� ?�장부�??�고, 기본?� ?�전모드 ?��?
    # if use_svd and _SVD_OK:
    #   ... (?�요 ???�장)

    # 4) 출력
    _write_video(frames2, out_path, fps, progress)
