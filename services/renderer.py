import random
from pathlib import Path
from typing import Any

import numpy as np
from moviepy.editor import ColorClip, CompositeVideoClip, ImageClip, concatenate_videoclips, vfx
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1080, 1920  # 9:16
FPS = 30


# ----------------- utils -----------------
def _hex_to_rgb(h: str):
    h = h.strip().lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _ensure_rgb(frame: np.ndarray) -> np.ndarray:
    """입력 프레임을 항상 (H, W, 3) uint8로 맞춘다."""
    if frame.ndim == 2:  # grayscale
        frame = np.stack([frame, frame, frame], axis=-1)
    if frame.shape[-1] == 4:  # RGBA → RGB (알파 제거)
        frame = frame[..., :3]
    return frame.astype(np.uint8)


def _apply_cinematic_grade(frame: np.ndarray) -> np.ndarray:
    frame = _ensure_rgb(frame)
    arr = frame.astype(np.float32)

    # 픽셀 단위(2D) 루미넌스 마스크
    lum = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    sh_mask = lum < 96
    hi_mask = lum > 190

    # 채널까지 명시해서 브로드캐스팅 안정화
    arr[sh_mask, :] = arr[sh_mask, :] * np.array(
        [0.92, 1.00, 0.98], dtype=np.float32
    )  # 살짝 시원한 섀도우
    arr[hi_mask, :] = np.minimum(
        255.0,
        arr[hi_mask, :] * np.array([1.06, 1.02, 0.98], dtype=np.float32),  # 따뜻한 하이라이트
    )

    # 약간의 콘트라스트/채도
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.06)
    return np.array(img, dtype=np.uint8)


def _add_vignette(frame: np.ndarray, strength: float = 0.35) -> np.ndarray:
    frame = _ensure_rgb(frame)
    h, w = frame.shape[:2]
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    mask = dist / (dist.max() + 1e-6)
    vignette = 1.0 - strength * (mask**1.5)

    out = frame.astype(np.float32)
    out *= vignette[..., None]  # (H, W, 1)로 명시
    return np.clip(out, 0, 255).astype(np.uint8)


def _grain_clip(dur: float, opacity: float = 0.08, scale: int = 1):
    # 매 프레임 노이즈 생성 → 필름그레인 느낌
    def make_frame(t):
        noise = np.random.normal(0.0, 8.0, (H // scale, W // scale, 1)).astype(np.float32) + 128
        noise = np.clip(noise, 0, 255).astype(np.uint8)
        noise = np.repeat(np.repeat(noise, scale, axis=0), scale, axis=1)
        noise = np.repeat(noise, 3, axis=2)
        return noise

    return (
        ImageClip(make_frame(0))
        .set_make_frame(make_frame)
        .set_opacity(opacity)
        .set_duration(float(dur))
    )


def _light_leak_clip(dur: float, color=(255, 180, 80), move=True, opacity=0.12):
    # 라디얼 그라디언트 생성 후 천천히 이동
    base = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)
    for r in range(max(W, H), 0, -20):
        a = int(255 * (r / max(W, H)) ** 2)
        draw.ellipse([W - r, H - r, W + r, H + r], fill=(color[0], color[1], color[2], a // 10))
    base = base.filter(ImageFilter.GaussianBlur(radius=90))
    leak = ImageClip(np.array(base)).set_duration(float(dur)).set_opacity(opacity)
    if move:
        leak = leak.set_position(lambda t: (int(-W + t * 30), int(-H + t * 18)))
    else:
        leak = leak.set_position((-W, -H))
    return leak


def _fill_blur_bg(img: Image.Image) -> Image.Image:
    # 이미지를 캔버스에 맞춰 늘린 후 블러 처리
    img = img.resize((W, H), Image.Resampling.LANCZOS)
    return img.filter(ImageFilter.GaussianBlur(radius=15))


def _fit_to_canvas(img: Image.Image, size: tuple) -> Image.Image:
    # 비율 유지하면서 캔버스에 맞춤
    w, h = size
    img_w, img_h = img.size
    scale = min(w / img_w, h / img_h) * 1.1  # 살짝 크게
    new_w, new_h = int(img_w * scale), int(img_h * scale)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 중앙에 배치
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    x, y = (w - new_w) // 2, (h - new_h) // 2
    canvas.paste(img, (x, y))
    return canvas


def list_ref_images(ref_dir: Path) -> list[Path]:
    # 레퍼런스 이미지 목록 반환
    if not ref_dir.exists():
        return []
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    return [p for p in ref_dir.iterdir() if p.suffix.lower() in exts]


def _find_font_path(pref_family: str | None = None) -> str | None:
    # Windows / macOS / Linux 후보 경로 (한글 가독용 말굽/나눔/애플/Noto/Arial)
    candidates = []
    if pref_family:
        pref_family = pref_family.lower()
    candidates += [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgunsl.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return None


def _text_width(text: str, font: ImageFont.FreeTypeFont) -> int:
    dummy = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy)
    return int(draw.textlength(text, font=font))  # getsize 대신 textlength 사용


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    lines, cur = [], ""
    for ch in text:
        if _text_width(cur + ch, font) <= max_width:
            cur += ch
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def _make_caption_image(text: str, width: int, style: dict[str, Any], pos: str) -> Image.Image:
    # 스타일 파라미터
    font_family = style.get("font", {}).get("family")
    bg_hex = style.get("caption", {}).get("bg", style.get("cta_style", {}).get("bg", "#000000"))
    fg_hex = style.get("caption", {}).get("fg", style.get("cta_style", {}).get("fg", "#FFFFFF"))
    bg_op = float(style.get("caption", {}).get("bg_opacity", 0.15))
    shadow = bool(style.get("caption", {}).get("shadow", True))

    font_path = _find_font_path(font_family)
    fs = 64 if pos == "center" else 54
    try:
        font = ImageFont.truetype(font_path, int(fs)) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    width = int(width)
    pad_x, pad_y = 28, 18
    text_w = int(width - pad_x * 2)

    wrapped = _wrap_text(text or " ", font, text_w)

    # 텍스트 박스 크기 계산 (정수로!)
    dummy = Image.new("RGBA", (width, 1000), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=6, align="center")
    tw = int(bbox[2] - bbox[0])
    th = int(bbox[3] - bbox[1])

    box_w = int(tw + pad_x * 2)
    box_h = int(th + pad_y * 2)

    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 배경(라운드)도 정수 좌표 사용
    radius = 18
    bg = _hex_to_rgb(bg_hex)
    bg_rgba = (int(bg[0]), int(bg[1]), int(bg[2]), int(bg_op * 255))
    draw.rounded_rectangle([(0, 0), (box_w - 1, box_h - 1)], radius=radius, fill=bg_rgba)

    # 텍스트
    fg = _hex_to_rgb(fg_hex)
    draw.multiline_text(
        (int(pad_x), int(pad_y)),
        wrapped,
        font=font,
        fill=(int(fg[0]), int(fg[1]), int(fg[2]), 255),
        spacing=6,
        align="center",
    )

    return img


def _caption_clip(text: str, style: dict[str, Any], pos: str, dur: float) -> ImageClip:
    width = int(W * 0.86)
    pil = _make_caption_image(text or " ", width, style, pos)
    np_img = np.array(pil)
    clip = ImageClip(np_img).set_duration(float(dur))

    y = int(H * 0.78) if pos == "center" else int(H * 0.87)
    clip = clip.set_position(("center", y))
    return clip


def ken_burns_clip(
    img_path: Path, dur: float, mode: str = "in", pan: str = "auto"
) -> CompositeVideoClip:
    base = Image.open(img_path).convert("RGB")
    bg = _fill_blur_bg(base)
    fg_canvas = _fit_to_canvas(base, (W, H)).convert("RGB")

    fg_start = 1.04 if mode == "in" else 1.12
    fg_end = 1.12 if mode == "in" else 1.04

    if pan == "auto":
        pan = random.choice(["lr", "rl", "tb", "bt", "none"])

    def scaler(t):
        p = t / max(dur, 0.001)
        return fg_start + (fg_end - fg_start) * (1 - (1 - p) * (1 - p))  # ease-out

    def mover(t):
        px, py, shift = 0, 0, 28
        p = t / max(dur, 0.001)
        if pan == "lr":
            px = -shift + 2 * shift * p
        if pan == "rl":
            px = shift - 2 * shift * p
        if pan == "tb":
            py = shift - 2 * shift * p
        if pan == "bt":
            py = -shift + 2 * shift * p
        return ("center", int(H / 2 + py))

    bg_clip = ImageClip(np.array(bg)).set_duration(float(dur))
    fg_clip = (
        ImageClip(np.array(fg_canvas))
        .resize(lambda t: scaler(t))
        .set_position(mover)
        .set_duration(float(dur))
    )

    base_clip = CompositeVideoClip([bg_clip, fg_clip], size=(W, H))
    # 프레임별 색보정 + 비네트
    base_clip = base_clip.fl_image(_apply_cinematic_grade).fl_image(_add_vignette)
    return base_clip


def caption_animated(text: str, style: dict[str, Any], pos: str, dur: float) -> ImageClip:
    # 하단 미니멀 로워서드 스타일
    width = int(W * 0.9)
    pil = _make_caption_image(text or " ", width, style, pos)
    np_img = np.array(pil)
    clip = ImageClip(np_img).set_duration(float(dur))

    y = int(H * 0.9)  # 하단 고정
    clip = clip.set_position(("center", y))
    return clip


# ----------------- renderer -----------------
def render_preview(shots, style, overlays, out_path: Path, crossfade: float = 0.3) -> Path:
    palette = style.get("palette", ["#161616", "#222", "#333"])
    ref_imgs = list_ref_images(Path(__file__).resolve().parents[1] / "outputs" / "refs")
    clips = []

    for i, s in enumerate(shots):
        dur = max(1.2, float(s["dur"]))  # 시네마틱은 최소 1.2s
        if ref_imgs:
            img_path = ref_imgs[i % len(ref_imgs)]
            mode = "in" if s.get("type") in ["intro", "value", "middle", None] else "out"
            pan = "auto"
            base = ken_burns_clip(img_path, dur, mode=mode, pan=pan)
        else:
            base = ColorClip((W, H), color=_hex_to_rgb(palette[i % len(palette)])).set_duration(dur)

        # 라이트리크/그레인
        leak = _light_leak_clip(dur)
        grain = _grain_clip(dur)

        # 자막 (하단 미니멀 로워서드)
        ov = overlays[i] if i < len(overlays) else {"text": s.get("caption", ""), "pos": "center"}
        cap_style = {
            **style,
            "caption": {"bg": "#000000", "fg": "#FFFFFF", "bg_opacity": 0.22, "shadow": False},
            "font": {**style.get("font", {}), "weight": 500},
        }
        cap = caption_animated(ov.get("text", ""), cap_style, "bottom", dur)

        clip = (
            CompositeVideoClip([base, leak, grain, cap], size=(W, H))
            .set_duration(dur)
            .fx(vfx.fadein, crossfade / 2)
            .fx(vfx.fadeout, crossfade / 2)
        )
        if i != 0:
            clip = clip.crossfadein(crossfade)
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # 시네마틱은 24fps 권장 (로그 출력 억제)
    final.write_videofile(str(out_path), fps=24, codec="libx264", audio=False, logger=None)
    final.close()  # 파일 잠김 방지
    return out_path
