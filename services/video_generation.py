"""
AI 영상 생성 서비스 - Stable Video Diffusion 통합
"""
from __future__ import annotations

import os
import torch
from pathlib import Path
from typing import Optional, Callable, Tuple
from PIL import Image
import numpy as np
import imageio.v3 as iio

try:
    from diffusers import StableVideoDiffusionPipeline
    from diffusers.utils import load_image, export_to_video
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import GatedRepoError
    SVD_AVAILABLE = True
except ImportError:
    SVD_AVAILABLE = False
    StableVideoDiffusionPipeline = None
    load_image = None
    export_to_video = None
    GatedRepoError = Exception

from utils.config import OPENAI_API_KEY
from utils.diagnostics import heartbeat
from .errors import AdGenError, ErrorCode

ROOT = Path(__file__).resolve().parents[1]

# Hugging Face 토큰 확인
HUGGINGFACE_HUB_TOKEN = os.getenv("HUGGINGFACE_HUB_TOKEN")
if not HUGGINGFACE_HUB_TOKEN:
    print("⚠️ HUGGINGFACE_HUB_TOKEN이 설정되지 않았습니다. .env 파일에 추가하세요.")

class SVDGenerator:
    """Stable Video Diffusion 영상 생성기"""
    
    def __init__(self):
        self.pipeline = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_id = "stabilityai/stable-video-diffusion-img2vid-xt-1-1"
        
    def _ensure_loaded(self) -> None:
        """파이프라인 로드 (필요시)"""
        if self.pipeline is not None:
            return
            
        if not SVD_AVAILABLE:
            raise AdGenError(
                ErrorCode.EXTERNAL_API_FAIL,
                "SVD 패키지가 설치되지 않았습니다",
                hint="pip install diffusers transformers accelerate"
            )
        
        heartbeat("svd_loading")
        print(f"🤖 SVD 모델 로딩 중... (디바이스: {self.device})")
        
        try:
            # 모델 로드
            self.pipeline = StableVideoDiffusionPipeline.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                variant="fp16" if self.device == "cuda" else None,
                use_auth_token=HUGGINGFACE_HUB_TOKEN
            )
            
            # GPU 최적화
            if self.device == "cuda":
                self.pipeline = self.pipeline.to(self.device)
                self.pipeline.enable_model_cpu_offload()  # 메모리 절약
                
            print("✅ SVD 모델 로드 완료")
            
        except GatedRepoError as e:
            raise AdGenError(
                ErrorCode.EXTERNAL_API_FAIL,
                "SVD 게이트 저장소 접근 거부 (401 Unauthorized)",
                hint="Hugging Face에서 모델 접근 권한을 신청하고 토큰을 설정하세요",
                detail=f"GatedRepoError: {str(e)}"
            )
        except torch.cuda.OutOfMemoryError as e:
            raise AdGenError(
                ErrorCode.RENDER_FAILED,
                "GPU 메모리 부족 (OOM)",
                hint="프레임 수를 줄이거나 다른 프로그램을 종료하세요",
                detail=f"CUDA OOM: {str(e)}"
            )
        except Exception as e:
            raise AdGenError(
                ErrorCode.EXTERNAL_API_FAIL,
                f"SVD 모델 로드 실패: {str(e)}",
                hint="Hugging Face 토큰과 GPU 메모리를 확인하세요",
                detail=str(e)
            )
    
    def generate_video(
        self, 
        image_path: str | Path,
        num_frames: int = 25,
        motion_bucket_id: int = 127,
        noise_aug_strength: float = 0.02,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[str, dict]:
        """
        이미지에서 영상 생성
        
        Args:
            image_path: 입력 이미지 경로
            num_frames: 생성할 프레임 수 (25 = 1초@25fps)
            motion_bucket_id: 움직임 강도 (1-255)
            noise_aug_strength: 노이즈 강도
            progress_callback: 진행률 콜백 (pct, message)
            
        Returns:
            (output_video_path, metadata)
        """
        self._ensure_loaded()
        
        image_path = Path(image_path)
        if not image_path.exists():
            raise AdGenError(
                ErrorCode.MISSING_PRODUCT,
                f"입력 이미지를 찾을 수 없습니다: {image_path}"
            )
        
        # 출력 경로 설정
        output_dir = ROOT / "outputs" / "ai_videos"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = int(torch.cuda.Event(enable_timing=True).elapsed_time(torch.cuda.Event(enable_timing=True)) * 1000)
        output_path = output_dir / f"svd_generated_{timestamp}.mp4"
        
        try:
            heartbeat("svd_preprocess")
            if progress_callback:
                progress_callback(10, "이미지 전처리 중...")
            
            # 이미지 로드 및 전처리
            image = load_image(str(image_path))
            image = image.resize((1024, 576))  # SVD 권장 해상도
            
            heartbeat("svd_generation")
            if progress_callback:
                progress_callback(20, "AI 영상 생성 중...")
            
            # 영상 생성 (SVD 파이프라인 호출)
            gen = torch.Generator(device=self.device).manual_seed(42)  # 재현 가능한 결과
            result = self.pipeline(
                image=image,
                num_frames=num_frames,
                decode_chunk_size=8,          # 메모리 절약
                motion_bucket_id=motion_bucket_id,
                noise_aug_strength=noise_aug_strength,
                fps=25,                       # 고정 fps
                generator=gen,
            )
            # diffusers 0.30.0 기준 반환은 .frames[0]에 프레임 리스트
            frames = result.frames[0] if hasattr(result, "frames") else result[0]
            
            heartbeat("svd_export")
            if progress_callback:
                progress_callback(90, "영상 내보내기 중...")
            
            # 비디오로 내보내기 (PIL.Image 리스트를 numpy array로 변환)
            arr = [np.array(img) for img in frames]
            iio.mimwrite(str(output_path), arr, fps=25, codec="h264", quality=8)
            
            # 메타데이터
            metadata = {
                "model": self.model_id,
                "input_image": str(image_path),
                "output_video": str(output_path),
                "num_frames": num_frames,
                "motion_bucket_id": motion_bucket_id,
                "noise_aug_strength": noise_aug_strength,
                "duration": num_frames / 25.0,  # 초
                "resolution": "1024x576",
                "fps": 25
            }
            
            if progress_callback:
                progress_callback(100, f"완료! {output_path}")
            
            return str(output_path), metadata
            
        except Exception as e:
            raise AdGenError(
                ErrorCode.RENDER_FAILED,
                f"SVD 영상 생성 실패: {str(e)}",
                detail=f"모델: {self.model_id}, 입력: {image_path}",
                hint="GPU 메모리 부족일 수 있습니다. num_frames나 inference_steps를 줄여보세요."
            )
    
    def cleanup(self):
        """메모리 정리"""
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

# 전역 인스턴스
_svd_generator: Optional[SVDGenerator] = None

def get_svd_generator() -> SVDGenerator:
    """SVD 생성기 싱글톤"""
    global _svd_generator
    if _svd_generator is None:
        _svd_generator = SVDGenerator()
    return _svd_generator

def generate_ai_video(
    image_path: str | Path,
    duration_seconds: float = 1.0,
    motion_level: str = "medium",
    quality: str = "standard",
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Tuple[str, dict]:
    """
    편의 함수: AI 영상 생성
    
    Args:
        image_path: 입력 이미지
        duration_seconds: 영상 길이 (초)
        motion_level: "low", "medium", "high"
        quality: "fast", "standard", "high"
        progress_callback: 진행률 콜백
        
    Returns:
        (output_video_path, metadata)
    """
    # 설정 매핑
    motion_configs = {
        "low": {"motion_bucket_id": 65, "noise_aug_strength": 0.01},
        "medium": {"motion_bucket_id": 127, "noise_aug_strength": 0.02},
        "high": {"motion_bucket_id": 200, "noise_aug_strength": 0.05}
    }
    
    quality_configs = {
        "fast": {"num_frames": 25},
        "standard": {"num_frames": 50},
        "high": {"num_frames": 75}
    }
    
    # 프레임 수 계산 (duration_seconds 기반)
    base_frames = int(duration_seconds * 25)  # 25fps 기준
    base_frames = max(25, min(base_frames, 100))  # 1-4초 범위
    
    config = {
        **motion_configs.get(motion_level, motion_configs["medium"]),
        **quality_configs.get(quality, quality_configs["standard"]),
        "num_frames": base_frames
    }
    
    generator = get_svd_generator()
    return generator.generate_video(
        image_path=image_path,
        progress_callback=progress_callback,
        **config
    )

def is_svd_available() -> bool:
    """SVD 사용 가능 여부"""
    if not SVD_AVAILABLE:
        return False
    if not HUGGINGFACE_HUB_TOKEN:
        return False
    try:
        # 실제 모델 접근 가능 여부 확인
        hf_hub_download(
            "stabilityai/stable-video-diffusion-img2vid-xt-1-1", 
            "model_index.json",
            use_auth_token=HUGGINGFACE_HUB_TOKEN
        )
        return True
    except Exception:
        return False

__all__ = [
    "generate_ai_video", 
    "get_svd_generator", 
    "is_svd_available",
    "SVDGenerator"
]
