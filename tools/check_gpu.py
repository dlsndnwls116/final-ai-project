#!/usr/bin/env python3
"""
GPU 인식 최종 점검 스크립트
RTX 5070 + CUDA 12.8 + PyTorch 호환성 확인
"""
import torch

print("=" * 50)
print("🎮 GPU 인식 최종 점검")
print("=" * 50)

print(f"torch = {torch.__version__}")
print(f"cuda available = {torch.cuda.is_available()}")
print(f"cuda version = {torch.version.cuda}")

if torch.cuda.is_available():
    device_name = torch.cuda.get_device_name(0)
    capability = torch.cuda.get_device_capability(0)
    
    print(f"device = {device_name}")
    print(f"capability = {capability}")
    
    # RTX 5070 특화 체크
    if "RTX 5070" in device_name:
        print("✅ RTX 5070 감지됨")
    
    # SM 120 (Ada Lovelace Next) 체크
    if capability >= (12, 0):
        print("✅ SM 120+ 아키텍처 지원됨")
    else:
        print(f"⚠️ SM {capability[0]}.{capability[1]} (SM 120 미만)")
        
    # 메모리 정보
    total_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"VRAM = {total_memory:.1f}GB")
    
    # 간단한 CUDA 테스트
    try:
        x = torch.randn(100, 100).cuda()
        y = torch.mm(x, x.t())
        print("✅ CUDA 연산 테스트 성공")
    except Exception as e:
        print(f"❌ CUDA 연산 테스트 실패: {e}")
        
else:
    print("❌ CUDA 사용 불가")

print("=" * 50)
