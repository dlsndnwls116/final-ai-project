# tools/svd_make.py
import os
import math
from pathlib import Path
from typing import Optional, List

import torch
from diffusers import StableVideoDiffusionPipeline
from PIL import Image, ImageFilter
import imageio.v3 as iio
import numpy as np
from tqdm import tqdm
import os

# --- Hugging Face 자동 로그인 ---
from huggingface_hub import login
from huggingface_hub.errors import GatedRepoError

# -------- GPU 메모리 제한 함수 --------
# GPU 메모리 제한 함수 제거됨 - 전체 VRAM 사용 허용

# -------- Config --------
MODEL_ID = "stabilityai/stable-video-diffusion-img2vid-xt-1-1"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32

def load_product_image(path: str, target_wh=(1024, 576)) -> Image.Image:
    """
    SVD 기본 해상도에 맞춰 리사이즈. (W,H)=(1024,576) 권장
    """
    img = Image.open(path).convert("RGB")
    # fit:cover
    w, h = img.size
    tw, th = target_wh
    scale = max(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    x0 = (nw - tw) // 2
    y0 = (nh - th) // 2
    img = img.crop((x0, y0, x0 + tw, y0 + th))
    return img

def letterbox_vertical(frames: List[Image.Image], out_wh=(1080, 1920)) -> List[Image.Image]:
    """
    1024x576(landscape) 결과를 1080x1920(세로)로 안전 변환.
    블러 배경 + 가운데 원본 프레임 배치.
    """
    OW, OH = out_wh
    out_frames = []
    for fr in frames:
        base = fr.copy().resize((OW, int(OW * fr.height / fr.width)), Image.LANCZOS)
        # 배경용 블러
        bg = base.copy().resize((OW, OH), Image.LANCZOS).filter(ImageFilter.GaussianBlur(32))
        # 가운데 배치용 (가로폭 맞춤)
        fg_w = OW
        fg_h = int(fr.height * (OW / fr.width))
        fg = fr.resize((fg_w, fg_h), Image.LANCZOS)
        y = (OH - fg_h) // 2
        bg.paste(fg, (0, y))
        out_frames.append(bg)
    return out_frames

def save_mp4(frames: List[Image.Image], out_path: str, fps: int = 25, progress_cb=None):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    
    # FFmpeg 로그 레벨 설정
    os.environ.setdefault("IMAGEIO_FFMPEG_LOGLEVEL", "info")
    
    print(f"[SVD] Writing mp4 → {out_path}")
    
    # PIL.Image를 numpy array로 변환
    arr = [np.array(img) for img in frames]
    
    # FFmpeg writer로 진행률 표시하며 저장
    with iio.get_writer(
        out_path,
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p"  # 호환성 좋음
    ) as w:
        for i, frame in enumerate(tqdm(arr, desc="[write]", unit="frame")):
            w.append_data(frame)
            if progress_cb:
                progress_cb(("write", (i+1)/len(arr)))

def make_svd_video(
    product_image: str,
    num_frames: int = 25,
    fps: int = 25,
    seed: Optional[int] = 42,
    output: str = "outputs/videos/svd_preview.mp4",
    portrait_1080x1920: bool = True,
    decode_chunk_size: int = 8,
    overlap: int = 4,
    progress_cb=None,
):
    if DEVICE != "cuda":
        raise RuntimeError("CUDA GPU가 필요합니다. (CPU 실행은 비현실적으로 느립니다)")

    # GPU 메모리 제한 제거됨 - 전체 VRAM 사용 허용

    # Hugging Face 자동 로그인
    token = os.getenv("HUGGINGFACE_HUB_TOKEN")
    if token:
        try:
            login(token=token)
            print("✅ Hugging Face 로그인 성공")
        except Exception as e:
            print(f"⚠️ Hugging Face 로그인 실패: {e}")
    else:
        print("⚠️ HUGGINGFACE_HUB_TOKEN 환경변수가 없어도 캐시된 모델이 있으면 동작하지만, 최초 실행이면 필요합니다.")

    print(f"[SVD] Loading model: {MODEL_ID} on {DEVICE} ({DTYPE})")
    
    try:
        pipe = StableVideoDiffusionPipeline.from_pretrained(
            MODEL_ID, torch_dtype=DTYPE, variant="fp16" if DTYPE==torch.float16 else None
        ).to(DEVICE)
        
        # <<< 메모리 절약 옵션들 >>>
        # 1) 공통적으로 지원되는 주의집중 슬라이싱
        pipe.enable_attention_slicing()
        
        # 2) VAE slicing을 쓰고 싶다면, SVD에선 파이프라인이 아니라 VAE 객체에 붙어 있습니다.
        #    안전 가드 걸고, 있으면 켜고 없으면 건너뜁니다.
        if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_slicing"):
            pipe.vae.enable_slicing()
            print("[SVD] VAE slicing enabled")
        else:
            print("[SVD] VAE slicing not available on this pipeline/version; skipped")
        
        # 3) VRAM을 더 아끼고 싶으면(느려짐 감수), 아래 둘 중 하나를 선택
        #    - 순차 CPU 오프로딩(안전)
        # pipe.enable_sequential_cpu_offload()
        #    - 모델 CPU 오프로딩(가끔 더 공격적)
        # from accelerate import cpu_offload
        # pipe.enable_model_cpu_offload()  # accelerate가 있을 때만 동작
        
        torch.cuda.empty_cache()
        print("✅ 메모리 절약 옵션 설정 완료")
        
    except GatedRepoError as e:
        raise SystemExit(
            "❌ SVD 게이트 저장소 접근 거부(401).\n"
            " 1) 모델 페이지에서 Access/Agree 수락\n"
            "    https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt-1-1\n"
            " 2) HUGGINGFACE_HUB_TOKEN 읽기 토큰 설정\n"
            "    https://huggingface.co/settings/tokens\n"
            " 3) 같은 파이썬/가상환경에서 실행\n"
            f" 상세: {e}"
        )

    # 저메모리 모드
    pipe.enable_model_cpu_offload() if DTYPE==torch.float16 else None

    # 입력 이미지
    img = load_product_image(product_image, target_wh=(1024, 576))

    # 시드 고정
    g = torch.Generator(device=DEVICE)
    if seed is not None:
        g.manual_seed(seed)

    # SVD 호출 (SVD에서 지원하는 인자만 사용)
    print(f"[SVD] Generating frames... (frames={num_frames}, chunk_size={decode_chunk_size})")
    
    # SVD 파이프라인에 지원되는 인자만 안전하게 전달
    kwargs = {
        "image": img,                    # PIL.Image (RGB), 크기는 사전에 리사이즈
        "num_frames": num_frames,        # 25 등
        "decode_chunk_size": decode_chunk_size,  # 메모리 여유 없으면 2~4
        "motion_bucket_id": 127,         # 0~255 (크면 더 역동적), 중간값 사용
        "noise_aug_strength": 0.1,       # 0.0~1.0 (제품보존 높이면 0.1~0.2)
        "fps": fps,                      # 24/25/30
        "generator": g,
    }
    
    # 방지용: 지원되는 인자만 자동 필터링
    import inspect
    valid = set(inspect.signature(type(pipe).__call__).parameters)
    
    # 위에서 만든 kwargs를 안전하게 필터링
    kwargs = {k: v for k, v in kwargs.items() if k in valid}
    
    # 디버그로 실제 전달되는 키 확인
    print("[SVD] call kwargs:", sorted(kwargs.keys()))
    
    # SVD 파이프라인 실행 (진행률 표시)
    with tqdm(total=num_frames, desc="[SVD] Generating", unit="frame") as pbar:
        result = pipe(**kwargs)
        pbar.update(num_frames)
    
    # diffusers 0.30.0 기준 반환은 .frames[0]에 프레임 리스트
    frames = result.frames[0] if hasattr(result, "frames") else result[0]
    
    # 프레임 디코딩 진행률 표시 (필요시)
    if progress_cb:
        for i, frame in enumerate(frames):
            progress_cb(("decode", (i+1)/len(frames)))

    # 세로 1080x1920로 변환(릴스/숏츠)
    if portrait_1080x1920:
        frames = letterbox_vertical(frames, out_wh=(1080, 1920))

    save_mp4(frames, output, fps=fps, progress_cb=progress_cb)
    print("✅ Done!")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="제품 이미지 경로 (JPG/PNG)")
    ap.add_argument("--frames", type=int, default=25, help="생성할 프레임 수 (메모리 절약: 14~20)")
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="outputs/videos/svd_preview.mp4")
    ap.add_argument("--portrait", action="store_true", help="1080x1920 세로로 출력")
# GPU 메모리 제한 옵션 제거됨 - 전체 VRAM 사용 허용
    ap.add_argument("--decode-chunk-size", type=int, default=8, help="디코딩 청크 크기 (메모리 절약: 2~4)")
    ap.add_argument("--overlap", type=int, default=4, help="타임 오버랩 (메모리 절약: 2)")
    args = ap.parse_args()

    make_svd_video(
        product_image=args.image,
        num_frames=args.frames,
        fps=args.fps,
        seed=args.seed,
        output=args.out,
        portrait_1080x1920=args.portrait,
        decode_chunk_size=args.decode_chunk_size,
        overlap=args.overlap,
    )
