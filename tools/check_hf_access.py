#!/usr/bin/env python3
"""
Hugging Face 접근 권한 진단 스크립트
"""
import os
import sys

def check_hf_access():
    print("🔍 Hugging Face 접근 권한 진단")
    print("=" * 50)
    
    # 1. 토큰 확인
    has_token = 'HUGGINGFACE_HUB_TOKEN' in os.environ
    print(f"HAS_TOKEN: {has_token}")
    
    if has_token:
        token = os.environ['HUGGINGFACE_HUB_TOKEN']
        print(f"TOKEN_LENGTH: {len(token)} chars")
        print(f"TOKEN_START: {token[:10]}...")
    else:
        print("❌ HUGGINGFACE_HUB_TOKEN 환경변수가 없습니다")
        print("💡 다음 중 하나로 설정하세요:")
        print("   $env:HUGGINGFACE_HUB_TOKEN = \"hf_...\"")
        print("   또는 .env 파일에 추가")
        return False
    
    # 2. huggingface_hub import 확인
    try:
        from huggingface_hub import whoami, hf_hub_download
        print("✅ huggingface_hub 모듈 로드 성공")
    except ImportError as e:
        print(f"❌ huggingface_hub 모듈 로드 실패: {e}")
        return False
    
    # 3. 인증 확인
    try:
        user_info = whoami()
        print(f"WHOAMI: {user_info}")
        print("✅ Hugging Face 인증 성공")
    except Exception as e:
        print(f"❌ Hugging Face 인증 실패: {e}")
        return False
    
    # 4. SVD 모델 접근 확인
    try:
        model_path = hf_hub_download(
            "stabilityai/stable-video-diffusion-img2vid-xt-1-1", 
            "model_index.json"
        )
        print(f"ACCESS_OK: {model_path}")
        print("✅ SVD 모델 접근 성공!")
        return True
    except Exception as e:
        print(f"❌ SVD 모델 접근 실패: {e}")
        print("💡 해결 방법:")
        print("   1) https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt-1-1")
        print("   2) 'Request access' 버튼 클릭하여 권한 신청")
        print("   3) 승인 후 다시 시도")
        return False

if __name__ == "__main__":
    success = check_hf_access()
    sys.exit(0 if success else 1)
