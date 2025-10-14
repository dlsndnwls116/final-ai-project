"""
S4. 타임라인 합성 & 렌더 엔진
recipe.json + 사용자 자산을 매핑해서 같은 기법(전환/줌/팔레트/타이포/오버레이)으로 9:16 mp4 생성
"""

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from moviepy.editor import *
from moviepy.video.fx import resize
from PIL import Image, ImageDraw, ImageFont


def pil_rgba_to_clip(im_rgba: Image.Image, duration: float) -> VideoClip:
    """PIL RGBA 이미지를 moviepy VideoClip으로 변환 (RGB+mask 분리)"""
    # RGBA로 변환
    rgba_array = np.array(im_rgba.convert("RGBA"))

    # RGB와 Alpha 분리
    rgb_array = rgba_array[:, :, :3]
    alpha_array = (rgba_array[:, :, 3] / 255.0).astype("float32")

    # RGB 클립 생성
    rgb_clip = ImageClip(rgb_array).set_duration(duration)

    # Alpha 마스크 생성
    alpha_mask = ImageClip(alpha_array, ismask=True).set_duration(duration)

    # 마스크 적용
    return rgb_clip.set_mask(alpha_mask)


# 9:16 모바일 비디오 설정
MOBILE_WIDTH = 1080
MOBILE_HEIGHT = 1920
MOBILE_FPS = 30


def fit_cover(clip: VideoClip, size: tuple) -> VideoClip:
    """fit:cover 효과 적용 (화면을 완전히 채우도록 크롭)"""
    W, H = size
    w, h = clip.size

    # 화면을 완전히 채우는 최소 스케일 계산
    scale = max(W / w, H / h)

    # 리사이즈 후 중앙 크롭
    return clip.resize(scale).crop(
        x_center=(w * scale) / 2, y_center=(h * scale) / 2, width=W, height=H
    )


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


def text_clip_pil(
    text,
    size=(1080, 1920),
    fontsize=64,
    color="white",
    font_path=None,
    bg=(0, 0, 0, 0),
    duration=2,
    pos="center",
):
    """PIL을 사용한 텍스트 클립 생성 (ImageMagick 의존성 제거)"""
    img = Image.new("RGBA", size, bg)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_path or "arial.ttf", fontsize)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    if pos == "center":
        x, y = (size[0] - w) // 2, (size[1] - h) // 2
    elif pos == "top":
        x, y = (size[0] - w) // 2, 50
    elif pos == "bottom":
        x, y = (size[0] - w) // 2, size[1] - h - 50
    else:
        x, y = pos

    draw.text((x, y), text, font=font, fill=color)
    # 기존 방식 대신 새로운 RGBA 변환 유틸 사용
    return pil_rgba_to_clip(img, duration)


def load_assets_from_directory(assets_dir: str) -> dict[str, str]:
    """자산 디렉토리에서 파일들을 로드"""
    assets = {}
    assets_path = Path(assets_dir)

    if not assets_path.exists():
        return assets

    # 이미지 파일들
    for img_file in assets_path.glob("images/*"):
        if img_file.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            assets[img_file.stem] = str(img_file)

    # 비디오 파일들
    for vid_file in assets_path.glob("videos/*"):
        if vid_file.suffix.lower() in [".mp4", ".mov", ".avi"]:
            assets[vid_file.stem] = str(vid_file)

    # 텍스트 파일들
    for txt_file in assets_path.glob("texts/*"):
        if txt_file.suffix.lower() in [".txt"]:
            with open(txt_file, encoding="utf-8") as f:
                assets[txt_file.stem] = f.read().strip()

    return assets


def create_text_clip(
    text_data: dict[str, Any], width: int = MOBILE_WIDTH, height: int = MOBILE_HEIGHT
) -> TextClip:
    """텍스트 클립 생성 (볼드+외곽선+슬라이드)"""

    content = text_data.get("content", "")
    start_time = text_data.get("t", 0)
    duration = text_data.get("t_end", 0) - start_time
    position = text_data.get("position", "center")

    # 폰트 설정
    font_size = text_data.get("font_size", 72)
    font_color = text_data.get("color", "white")
    stroke_color = text_data.get("stroke_color", "black")
    stroke_width = text_data.get("stroke_width", 3)

    # 텍스트 클립 생성
    text_clip = (
        TextClip(
            content,
            font="Arial-Bold",  # Pretendard-Bold 대신 Arial-Bold 사용
            fontsize=font_size,
            color=font_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            method="caption",
            size=(width * 0.9, None),  # 화면 너비의 90% 사용
        )
        .set_start(start_time)
        .set_duration(duration)
    )

    # 위치 설정
    if position == "center":
        text_clip = text_clip.set_position(("center", "center"))
    elif position == "top":
        text_clip = text_clip.set_position(("center", height * 0.1))
    elif position == "bottom":
        text_clip = text_clip.set_position(("center", height * 0.8))

    return text_clip


def create_placeholder_clip(duration: float, color: str = "#141414", text: str = "") -> VideoClip:
    """플레이스홀더 클립 생성 (단색+텍스트, PIL 기반)"""

    if text:
        # PIL 기반으로 텍스트가 포함된 클립 생성
        try:
            # PIL 기반으로 RGBA 이미지 생성 후 pil_rgba_to_clip 사용
            img = Image.new("RGBA", (MOBILE_WIDTH, MOBILE_HEIGHT), color)
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 48)
            except:
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x, y = (MOBILE_WIDTH - w) // 2, (MOBILE_HEIGHT - h) // 2
            draw.text((x, y), text, font=font, fill="white")

            return pil_rgba_to_clip(img, duration)
        except Exception as e:
            print(f"PIL 텍스트 실패, 단색으로 대체: {e}")
            # PIL 실패 시 단색 클립만 반환
            pass

    # 텍스트가 없거나 PIL 실패 시 단색 클립
    return ColorClip(size=(MOBILE_WIDTH, MOBILE_HEIGHT), color=color, duration=duration)


def apply_motion_effects(clip: VideoClip, motion: dict[str, Any]) -> VideoClip:
    """모션 효과 적용 (줌/팬/틸트)"""

    motion_type = motion.get("type", "static")
    intensity = motion.get("intensity", 0.0)

    if motion_type == "zoom-in-slow":
        # 천천히 줌인
        def zoom_func(t):
            return 1 + 0.05 * t

        clip = clip.fx(resize, zoom_func)

    elif motion_type == "zoom-out-slow":
        # 천천히 줌아웃
        def zoom_func(t):
            return 1.2 - 0.05 * t

        clip = clip.fx(resize, zoom_func)

    elif motion_type == "pan":
        # 팬 효과
        pan_intensity = intensity * 0.1

        def pan_func(t):
            return (pan_intensity * t, 0)

        clip = clip.set_position(pan_func)

    return clip


def _clip_from_layer(
    layer: dict[str, Any],
    assets: dict[str, str],
    W: int = 1080,
    H: int = 1920,
    default_dur: float = 2.0,
    diag: dict | None = None,
) -> VideoClip:
    """레이어에서 클립 생성 (진단 정보 수집)"""
    from moviepy.editor import ColorClip, CompositeVideoClip

    kind = layer.get("type")
    ref = layer.get("ref")
    dur = float(layer.get("dur", default_dur))
    dur = max(0.2, dur)  # 최소 0.2초

    if kind in ("video", "image"):
        path = assets.get(ref)
        if not path or not Path(path).exists():
            if diag is not None:
                diag["missing"].add(ref or "<empty-ref>")
                diag["reasons"].append(f"missing asset for ref={ref}")
            # 플레이스홀더 생성하여 진행 (PIL 기반)
            bg = ColorClip((W, H), color=(245, 245, 245), duration=dur)
            txt = text_clip_pil(
                f"Missing: {ref}", size=(W, H), fontsize=50, color="red", duration=dur
            )
            return CompositeVideoClip([bg, txt])

        # 실제 파일을 여는 로직
        try:
            if path.lower().endswith((".mp4", ".mov", ".avi")):
                clip = VideoFileClip(path).subclip(0, min(dur, 10))
                clip = fit_cover(clip, (W, H))  # fit:cover 강제 적용
            else:
                clip = ImageClip(path).set_duration(dur)
                clip = fit_cover(clip, (W, H))  # fit:cover 강제 적용
            return clip
        except Exception as e:
            if diag is not None:
                diag["reasons"].append(f"failed to load {ref}: {str(e)}")
            # 실패 시 플레이스홀더 (PIL 기반)
            bg = ColorClip((W, H), color=(245, 245, 245), duration=dur)
            txt = text_clip_pil(
                f"Error: {ref}", size=(W, H), fontsize=50, color="red", duration=dur
            )
            return CompositeVideoClip([bg, txt])

    elif kind == "text":
        txt = layer.get("text", "").strip()
        if not txt:
            if diag is not None:
                diag["reasons"].append("empty text layer")
            return None

        # PIL 기반 텍스트 클립 생성 (ImageMagick 의존성 완전 제거)
        try:
            # 텍스트 스타일 정보 추출
            style = layer.get("style", {})
            fontsize = style.get("fontsize", 64)
            color = style.get("color", "white")
            position = style.get("position", "center")

            text_clip = text_clip_pil(
                txt, size=(W, H), fontsize=fontsize, color=color, duration=dur, pos=position
            )
            return text_clip
        except Exception as e:
            if diag is not None:
                diag["reasons"].append(f"text clip error: {str(e)}")
            # 텍스트 실패 시에도 기본 텍스트로 대체
            try:
                fallback_clip = text_clip_pil(
                    f"TEXT ERROR: {txt[:20]}...",
                    size=(W, H),
                    fontsize=40,
                    color="red",
                    duration=dur,
                )
                return fallback_clip
            except:
                return None

    else:
        if diag is not None:
            diag["reasons"].append(f"unknown layer type: {kind}")
        return None


def build_shot_clip(
    shot: dict[str, Any],
    assets: dict[str, str],
    progress_cb: Callable | None = None,
    safe_mode: bool = False,
) -> VideoClip:
    """샷 클립 빌드 (디버그 워터마크 + 안전한 합성 순서)"""

    # 새로운 유틸리티 함수 사용 (t 또는 in/out 호환)
    start_time, end_time = shot_bounds(shot)
    duration = shot_duration(shot)

    # 최소 길이 보장
    if duration <= 0:
        duration = 2.0

    shot_idx = shot.get("idx", 0)
    size = (MOBILE_WIDTH, MOBILE_HEIGHT)

    # 레이어 처리
    layers = shot.get("layers", [])
    if not layers:
        # 기존 형식 지원 - 단순한 자산 로드
        video_asset = None
        for asset_key in [
            "product_shot",
            "store_exterior",
            "brand_logo",
            "product",
            "store",
            "broll1",
            "broll2",
        ]:
            if asset_key in assets:
                video_asset = assets[asset_key]
                break

        if video_asset and os.path.exists(video_asset):
            try:
                if video_asset.lower().endswith((".mp4", ".mov", ".avi")):
                    base = VideoFileClip(video_asset).subclip(0, min(duration, 10))
                else:
                    base = ImageClip(video_asset).set_duration(duration)
                base = fit_cover(base, size).set_opacity(1)  # fit:cover 강제 적용
            except Exception as e:
                print(f"자산 로드 실패: {e}")
                base = create_placeholder_clip(
                    duration, "#1a1a1a", f"자산 로드 실패: {video_asset}"
                )
        else:
            base = create_placeholder_clip(duration, "#141414", f"샷 {shot_idx + 1}")

        # 강화된 디버그 워터마크 추가
        debug_text = f"SHOT {shot_idx}\n{start_time:.1f}s-{end_time:.1f}s\n{duration:.1f}s"
        debug_overlay = text_clip_pil(
            debug_text,
            size=size,
            fontsize=60,
            color="yellow",
            bg=(0, 0, 0, 128),  # 반투명 검은 배경
            duration=duration,
            pos=(40, 40),
        )

        # 추가 디버그 정보 (우측 하단)
        info_text = f"Legacy Mode\nAssets: {len(assets)}"
        info_overlay = text_clip_pil(
            info_text,
            size=size,
            fontsize=40,
            color="cyan",
            bg=(0, 0, 0, 128),
            duration=duration,
            pos=(size[0] - 200, size[1] - 100),
        )

        return CompositeVideoClip([base, debug_overlay, info_overlay], size=size).set_duration(
            duration
        )

    # 새로운 레시피 형식 처리
    diagnostics = {"missing": set(), "reasons": []}
    base_clip = None
    overlays = []

    # 1. 베이스 비디오/이미지 레이어 찾기 (반드시 첫 번째)
    for layer in layers:
        if layer.get("type") in ("video", "image"):
            layer_clip = _clip_from_layer(
                layer, assets, MOBILE_WIDTH, MOBILE_HEIGHT, duration, diagnostics
            )
            if layer_clip is not None:
                base_clip = layer_clip.set_opacity(1)  # 알파 처리 안전장치
                break

    # 베이스 클립이 없으면 플레이스홀더 생성
    if base_clip is None:
        base_clip = create_placeholder_clip(duration, "#141414", f"샷 {shot_idx + 1}")

    # 2. 오버레이 레이어들 처리 (Safe Mode에서는 건너뛰기)
    if not safe_mode:
        for layer in layers:
            layer_type = layer.get("type")
            if layer_type == "text":
                try:
                    text_clip = text_clip_pil(
                        layer.get("text", ""),
                        size=size,
                        fontsize=64,
                        color="white",
                        duration=duration,
                        pos="center",
                    )
                    overlays.append(text_clip)
                except Exception as e:
                    print(f"shot#{shot_idx} text layer skipped: {e}")

    # 3. 강화된 디버그 워터마크 추가 (무조건)
    mode_indicator = "SAFE MODE" if safe_mode else "NORMAL"
    debug_text = (
        f"SHOT {shot_idx} [{mode_indicator}]\n{start_time:.1f}s-{end_time:.1f}s\n{duration:.1f}s"
    )
    debug_overlay = text_clip_pil(
        debug_text,
        size=size,
        fontsize=60,
        color="yellow" if not safe_mode else "green",
        bg=(0, 0, 0, 128),  # 반투명 검은 배경
        duration=duration,
        pos=(40, 40),
    )
    overlays.append(debug_overlay)

    # 4. 추가 디버그 정보 (우측 하단)
    overlay_count = (
        len([l for l in layers if l.get("type") in ("text", "solid", "vignette", "grain", "glow")])
        if not safe_mode
        else 0
    )
    info_text = f"Layers: {len(layers)}\nOverlays: {overlay_count}\nAssets: {len(assets)}"
    info_overlay = text_clip_pil(
        info_text,
        size=size,
        fontsize=40,
        color="cyan" if not safe_mode else "lime",
        bg=(0, 0, 0, 128),
        duration=duration,
        pos=(size[0] - 200, size[1] - 100),
    )
    overlays.append(info_overlay)

    # 4. 안전한 합성 순서: [베이스, *오버레이들] - base가 반드시 첫 번째
    all_layers = [base_clip] + overlays
    if len(all_layers) == 1:
        return all_layers[0]
    else:
        # base가 첫 번째임을 보장하고 size 강제 설정
        return CompositeVideoClip(all_layers, size=size).set_duration(duration)


def create_transition_effect(
    clip1: VideoClip, clip2: VideoClip, transition_type: str = "fade"
) -> VideoClip:
    """전환 효과 생성"""

    if transition_type == "fade":
        # 페이드 전환
        clip1 = clip1.fadeout(0.5)
        clip2 = clip2.fadein(0.5)
    elif transition_type == "slide":
        # 슬라이드 전환
        clip2 = clip2.set_position(lambda t: (MOBILE_WIDTH * (1 - t), 0))

    return concatenate_videoclips([clip1, clip2], method="compose")


def render_video(
    recipe_path: str,
    assets_dir: str,
    output_path: str,
    progress_cb: Callable | None = None,
    safe_mode: bool = False,
) -> dict[str, Any]:
    """메인 렌더링 함수"""

    # 진행률 콜백 기본값
    if progress_cb is None:
        progress_cb = lambda p, m: print(f"{p}%: {m}")

    try:
        # 레시피 로드
        progress_cb(5, "레시피 로드 중...")
        with open(recipe_path, encoding="utf-8") as f:
            recipe = json.load(f)

        # 자산 로드
        progress_cb(10, "자산 로드 중...")
        assets = load_assets_from_directory(assets_dir)

        # 샷 클립들 생성
        progress_cb(15, "샷 클립 생성 중...")
        shots = recipe.get("shots", [])
        timeline = recipe.get("timeline", [])

        # timeline이 있으면 timeline 사용, 없으면 shots 사용
        source_shots = timeline if timeline else shots
        max_shots = min(12, len(source_shots))  # MVP: 최대 12샷
        shot_clips = []
        diagnostics = {"missing": set(), "resolved": 0, "built": 0, "reasons": []}

        # 진단 시스템 초기화
        from utils.diagnostics import heartbeat, loop_guard
        
        guard = loop_guard("render_shots", max_iter=max_shots * 2, warn_every=5)
        for i, shot in enumerate(source_shots[:max_shots]):
            heartbeat("render_shots")
            guard.tick({"shot_index": i, "max_shots": max_shots, "built_count": len(shot_clips)})
            
            progress_cb(15 + int(60 * i / max_shots), f"샷 {i + 1}/{max_shots} 생성 중...")
            try:
                shot_clip = build_shot_clip(shot, assets, progress_cb, safe_mode)
                if shot_clip is not None:
                    shot_clips.append(shot_clip)
                    diagnostics["built"] += 1
                    print(
                        f"✅ Shot {i + 1} created successfully (duration: {shot_clip.duration:.2f}s)"
                    )
                else:
                    diagnostics["reasons"].append(f"shot#{i} returned None")
                    print(f"❌ Shot {i + 1} failed: returned None")
            except Exception as e:
                diagnostics["reasons"].append(f"shot#{i} error: {str(e)}")
                print(f"❌ Shot {i + 1} error: {str(e)}")

        # 진단 정보 출력
        print("\n🔍 렌더링 진단:")
        print(f"   - 총 샷: {len(source_shots)}")
        print(f"   - 처리된 샷: {max_shots}")
        print(f"   - 성공한 샷: {diagnostics['built']}")
        print(f"   - 실패한 샷: {len(diagnostics['reasons'])}")
        if diagnostics["reasons"]:
            print(f"   - 실패 원인: {diagnostics['reasons'][:3]}...")  # 처음 3개만 표시

        # 빈 샷 방어
        if not shot_clips:
            msg = (
                "No usable shots were produced. "
                f"timeline={len(timeline)}, shots={len(shots)}, "
                f"resolved={diagnostics['resolved']}, built={diagnostics['built']}, "
                f"reasons={diagnostics['reasons']}"
            )
            raise ValueError(msg)

        # 클립들 합성
        progress_cb(80, "클립 합성 중...")
        if len(shot_clips) == 1:
            final_clip = shot_clips[0]
        else:
            # 전환 효과 적용
            final_clip = shot_clips[0]
            transition_guard = loop_guard("render_transitions", max_iter=len(shot_clips) * 2, warn_every=3)
            for i in range(1, len(shot_clips)):
                heartbeat("render_transitions")
                transition_guard.tick({"transition_index": i, "total_clips": len(shot_clips)})
                
                transition_type = "fade"  # 기본 전환
                final_clip = create_transition_effect(final_clip, shot_clips[i], transition_type)

        # 출력 디렉토리 생성
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # 고급 비디오 인코딩 (모바일 최적화)
        progress_cb(90, "비디오 인코딩 중...")

        # Serene Minimal Gold 스타일이면 고품질 설정
        recipe_style = recipe.get("style", "")
        if recipe_style == "serene_minimal_gold":
            # 고품질 모바일 최적화 설정
            final_clip.write_videofile(
                output_path,
                fps=MOBILE_FPS,
                codec="libx264",
                audio=False,
                preset="slow",  # 고품질 프리셋
                bitrate="6M",  # 높은 비트레이트
                ffmpeg_params=[
                    "-profile:v",
                    "high",
                    "-pix_fmt",
                    "yuv420p",
                    "-crf",
                    "18",  # 고품질 CRF
                    "-movflags",
                    "+faststart",
                    "-vf",
                    f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color={recipe.get('canvas', {}).get('bg_color', 'E9E3D9').replace('#', '')},format=yuv420p",
                ],
                threads=4,
                logger=None,
            )
        else:
            # 기본 설정
            final_clip.write_videofile(
                output_path,
                fps=MOBILE_FPS,
                codec="libx264",
                audio=False,
                bitrate="4M",
                preset="medium",
                threads=4,
                logger=None,
            )
        final_clip.close()  # 파일 잠김 방지

        # 메타데이터 수집
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        duration = final_clip.duration

        # 사용된 자산 정보 저장
        used_assets = {
            "video_file": output_path,
            "file_size_mb": round(file_size, 2),
            "duration_seconds": round(duration, 2),
            "resolution": f"{MOBILE_WIDTH}x{MOBILE_HEIGHT}",
            "fps": MOBILE_FPS,
            "used_assets": list(assets.keys()),
            "total_shots": len(shot_clips),
        }

        # used_assets.json 저장
        assets_info_path = output_dir / "used_assets.json"
        with open(assets_info_path, "w", encoding="utf-8") as f:
            json.dump(used_assets, f, ensure_ascii=False, indent=2)

        progress_cb(100, "렌더링 완료!")

        return used_assets

    except Exception as e:
        progress_cb(0, f"렌더링 실패: {str(e)}")
        raise e


def create_subtitle_srt(recipe: dict[str, Any], output_path: str) -> str:
    """자막 SRT 파일 생성"""

    srt_path = output_path.replace(".mp4", ".srt")
    srt_content = []

    shots = recipe.get("shots", [])
    for i, shot in enumerate(shots):
        start_time = shot.get("t0", 0)
        end_time = shot.get("t1", 0)

        # 시간 포맷 변환 (초 -> SRT 포맷)
        def seconds_to_srt_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millisecs = int((seconds % 1) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

        start_srt = seconds_to_srt_time(start_time)
        end_srt = seconds_to_srt_time(end_time)

        # 텍스트 수집
        text_elements = shot.get("text", [])
        if text_elements:
            content = " ".join([elem.get("content", "") for elem in text_elements])
            if content.strip():
                srt_content.append(f"{i + 1}")
                srt_content.append(f"{start_srt} --> {end_srt}")
                srt_content.append(content.strip())
                srt_content.append("")

    # SRT 파일 저장
    if srt_content:
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_content))
        return srt_path

    return ""


def frame_variance(clip: VideoClip, t: float = 0.1) -> float:
    """특정 시점의 프레임 분산 계산 (흑/회색 화면 감지용)"""
    try:
        frame = clip.get_frame(t)
        return float(np.var(frame))
    except Exception as e:
        print(f"프레임 분산 계산 실패: {e}")
        return 0.0


def render_single_shot_preview(
    shot: dict[str, Any], assets: dict[str, str], output_dir: str, safe_mode: bool = False
) -> dict[str, Any]:
    """단일 샷 미리보기 렌더 (디버그용)"""
    try:
        # 디버그 출력 디렉토리 생성
        debug_dir = Path(output_dir) / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)

        # 샷 클립 생성 (2초 고정)
        shot_copy = shot.copy()
        if "t" in shot_copy:
            shot_copy["t"] = [0.0, 2.0]
        shot_copy["in"] = 0.0
        shot_copy["out"] = 2.0

        shot_clip = build_shot_clip(shot_copy, assets, safe_mode=safe_mode)

        if shot_clip is None:
            return {"error": "샷 클립 생성 실패"}

        # 프레임 분산 계산
        variance = frame_variance(shot_clip, t=0.1)

        # 프레임 이미지 저장
        frame_path = debug_dir / "shot0_0100ms.png"
        shot_clip.save_frame(str(frame_path), t=0.1)

        # 미니 비디오 저장 (2초)
        video_path = debug_dir / "shot0_preview.mp4"
        shot_clip.write_videofile(
            str(video_path),
            fps=30,
            codec="libx264",
            audio=False,
            bitrate="2M",
            preset="fast",
            logger=None,
        )
        shot_clip.close()

        return {
            "variance": variance,
            "frame_path": str(frame_path),
            "video_path": str(video_path),
            "duration": shot_clip.duration,
            "warning": "프레임 분산이 너무 낮습니다(흑/회색 화면 의심)" if variance < 10 else None,
        }

    except Exception as e:
        return {"error": f"미리보기 생성 실패: {str(e)}"}


def get_video_info(video_path: str) -> dict[str, Any]:
    """비디오 파일 정보 가져오기"""

    if not os.path.exists(video_path):
        return {}

    try:
        clip = VideoFileClip(video_path)
        info = {
            "file_size_mb": round(os.path.getsize(video_path) / (1024 * 1024), 2),
            "duration_seconds": round(clip.duration, 2),
            "fps": clip.fps,
            "size": clip.size,
            "resolution": f"{clip.w}x{clip.h}",
        }
        clip.close()
        return info
    except Exception as e:
        print(f"비디오 정보 가져오기 실패: {e}")
        return {}
