"""
SVD (Stable Video Diffusion) 테스트 스크립트
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def test_svd_availability():
    """SVD 사용 가능 여부 테스트"""
    print("🔍 SVD 사용 가능 여부 테스트...")
    
    # 1. 패키지 설치 확인
    try:
        import torch
        print(f"✅ PyTorch: {torch.__version__}")
        
        import diffusers
        print(f"✅ Diffusers: {diffusers.__version__}")
        
        import transformers
        print(f"✅ Transformers: {transformers.__version__}")
        
    except ImportError as e:
        print(f"❌ 패키지 누락: {e}")
        return False
    
    # 2. CUDA 확인
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"✅ CUDA 사용 가능: {gpu_name} ({gpu_memory:.1f}GB)")
    else:
        print("⚠️ CUDA 사용 불가 (CPU 모드)")
    
    # 3. Hugging Face 토큰 확인
    hf_token = os.getenv("HUGGINGFACE_HUB_TOKEN")
    if hf_token:
        print(f"✅ Hugging Face 토큰: {len(hf_token)} chars")
    else:
        print("❌ Hugging Face 토큰 없음")
        print("💡 .env 파일에 HUGGINGFACE_HUB_TOKEN 추가하세요")
        return False
    
    # 4. SVD 서비스 테스트
    try:
        from services.video_generation import is_svd_available
        if is_svd_available():
            print("✅ SVD 서비스 사용 가능")
            return True
        else:
            print("❌ SVD 서비스 사용 불가")
            return False
    except Exception as e:
        print(f"❌ SVD 서비스 테스트 실패: {e}")
        return False

def test_simple_generation():
    """간단한 SVD 생성 테스트"""
    print("\n🎬 간단한 SVD 생성 테스트...")
    
    try:
        from services.video_generation import generate_ai_video
        
        # 테스트용 이미지 생성
        from PIL import Image, ImageDraw
        test_img = Image.new("RGB", (1024, 576), (100, 150, 200))
        draw = ImageDraw.Draw(test_img)
        draw.rectangle((100, 100, 924, 476), fill=(200, 100, 150))
        draw.text((400, 250), "TEST", fill=(255, 255, 255))
        
        test_img_path = ROOT / "outputs" / "test_input.jpg"
        test_img_path.parent.mkdir(parents=True, exist_ok=True)
        test_img.save(test_img_path)
        
        print(f"📸 테스트 이미지 생성: {test_img_path}")
        
        # 진행률 콜백
        def progress_callback(pct, msg):
            print(f"  진행률 {pct}%: {msg}")
        
        # AI 영상 생성 (빠른 설정)
        output_path, metadata = generate_ai_video(
            image_path=test_img_path,
            duration_seconds=1.0,
            motion_level="low",
            quality="fast",
            progress_callback=progress_callback
        )
        
        print(f"✅ AI 영상 생성 완료: {output_path}")
        print(f"📊 메타데이터: {metadata}")
        
        return True
        
    except Exception as e:
        print(f"❌ SVD 생성 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 SVD (Stable Video Diffusion) 테스트 시작\n")
    
    # 1. 사용 가능 여부 테스트
    if not test_svd_availability():
        print("\n❌ SVD 사용 불가. 설정을 확인하세요.")
        return 1
    
    print("\n" + "="*50)
    
    # 2. 간단한 생성 테스트
    if test_simple_generation():
        print("\n🎉 SVD 테스트 성공!")
        return 0
    else:
        print("\n❌ SVD 테스트 실패!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
