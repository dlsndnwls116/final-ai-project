#!/usr/bin/env python3
"""
업로드 시스템 테스트 스크립트
수동으로 outputs/assets/product.jpg를 배치하고 시스템이 인식하는지 확인
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def test_asset_recognition():
    """자산 인식 테스트"""
    ROOT = Path(__file__).resolve().parents[1]
    ASSETS_DIR = ROOT / "outputs" / "assets"
    
    print(f"🔍 자산 디렉토리 검사: {ASSETS_DIR}")
    print(f"   존재 여부: {ASSETS_DIR.exists()}")
    
    # 제품 이미지 후보들
    product_candidates = [
        "product.jpg",
        "product.png", 
        "product.jpeg",
        "product.webp"
    ]
    
    print("\n📁 제품 이미지 후보들:")
    found_products = []
    for candidate in product_candidates:
        path = ASSETS_DIR / candidate
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        print(f"   {candidate}: {'✅' if exists else '❌'} ({size:,} bytes)")
        if exists:
            found_products.append(str(path))
    
    # product/ 하위 디렉토리도 확인
    product_dir = ASSETS_DIR / "product"
    if product_dir.exists():
        print(f"\n📁 product/ 하위 디렉토리:")
        for item in product_dir.iterdir():
            if item.is_file():
                size = item.stat().st_size
                print(f"   product/{item.name}: ✅ ({size:,} bytes)")
                if item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                    found_products.append(str(item))
    
    print(f"\n🎯 발견된 제품 이미지: {len(found_products)}개")
    for i, path in enumerate(found_products, 1):
        print(f"   {i}. {path}")
    
    # 최우선 제품 이미지 선택
    if found_products:
        primary_product = found_products[0]
        print(f"\n✅ 최우선 제품 이미지: {primary_product}")
        
        # 절대 경로로 변환
        abs_path = str(Path(primary_product).resolve())
        print(f"   절대 경로: {abs_path}")
        
        return abs_path
    else:
        print(f"\n❌ 제품 이미지를 찾을 수 없습니다.")
        print(f"   수동 배치: {ASSETS_DIR}/product.jpg")
        return None

def test_frame_extraction():
    """프레임 추출 테스트"""
    try:
        from utils.frame_extractor import extract_frame_to_image
        print("\n🎬 프레임 추출 테스트:")
        
        # 테스트용 영상 파일 찾기
        ROOT = Path(__file__).resolve().parents[1]
        video_candidates = [
            ROOT / "outputs/assets/product_shot.mp4",
            ROOT / "outputs/assets/product/product.mp4",
        ]
        
        test_video = None
        for candidate in video_candidates:
            if candidate.exists():
                test_video = str(candidate)
                break
        
        if test_video:
            print(f"   테스트 영상: {test_video}")
            try:
                thumb = extract_frame_to_image(test_video, t=0.5)
                print(f"   썸네일 생성: ✅ {thumb.size}")
                
                # 테스트 저장
                test_thumb_path = ROOT / "outputs/assets/test_thumb.jpg"
                thumb.save(test_thumb_path, quality=95)
                print(f"   테스트 저장: ✅ {test_thumb_path}")
                return True
            except Exception as e:
                print(f"   썸네일 생성 실패: ❌ {e}")
                return False
        else:
            print("   테스트 영상 없음: 영상 파일을 outputs/assets/에 배치하세요")
            return False
            
    except ImportError as e:
        print(f"\n❌ 프레임 추출 모듈 import 실패: {e}")
        return False

def main():
    """메인 테스트"""
    print("🚀 업로드 시스템 테스트 시작")
    print("=" * 50)
    
    # 1. 자산 인식 테스트
    product_path = test_asset_recognition()
    
    # 2. 프레임 추출 테스트
    frame_ok = test_frame_extraction()
    
    # 3. 종합 결과
    print("\n" + "=" * 50)
    print("📊 테스트 결과:")
    print(f"   제품 이미지: {'✅' if product_path else '❌'}")
    print(f"   프레임 추출: {'✅' if frame_ok else '❌'}")
    
    if product_path and frame_ok:
        print("\n🎉 모든 테스트 통과! D2 탭에서 업로더를 사용할 수 있습니다.")
    else:
        print("\n⚠️  일부 테스트 실패. 아래 방법으로 수정하세요:")
        print("   1. outputs/assets/product.jpg 수동 배치")
        print("   2. 영상 파일을 outputs/assets/에 배치")
        print("   3. D2 탭에서 업로더 테스트")

if __name__ == "__main__":
    main()
