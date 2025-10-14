"""
SVD 테스트용 제품 이미지 생성
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def create_test_product_image():
    """테스트용 제품 이미지 생성"""
    # 1024x576 해상도 (SVD 권장)
    img = Image.new("RGB", (1024, 576), (240, 240, 240))
    draw = ImageDraw.Draw(img)
    
    # 배경 그라디언트
    for y in range(576):
        color = (int(240 - y * 0.1), int(240 - y * 0.05), int(255 - y * 0.02))
        draw.line([(0, y), (1024, y)], fill=color)
    
    # 제품 영역 (원형)
    center_x, center_y = 512, 288
    radius = 120
    draw.ellipse(
        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
        fill=(100, 150, 200),
        outline=(50, 100, 150),
        width=3
    )
    
    # 제품 내부 디테일
    inner_radius = 80
    draw.ellipse(
        [center_x - inner_radius, center_y - inner_radius, center_x + inner_radius, center_y + inner_radius],
        fill=(150, 200, 250),
        outline=(100, 150, 200),
        width=2
    )
    
    # 텍스트 (가능한 경우)
    try:
        # 기본 폰트 사용
        font_size = 48
        draw.text((center_x - 100, center_y - 20), "TEST", fill=(255, 255, 255))
        draw.text((center_x - 80, center_y + 20), "PRODUCT", fill=(255, 255, 255))
    except:
        pass
    
    # 하이라이트 효과
    for i in range(5):
        alpha = int(50 - i * 8)
        highlight_radius = radius - 20 + i * 4
        draw.ellipse(
            [center_x - highlight_radius, center_y - highlight_radius, 
             center_x + highlight_radius, center_y + highlight_radius],
            outline=(255, 255, 255, alpha),
            width=1
        )
    
    return img

if __name__ == "__main__":
    # 테스트 이미지 생성
    test_img = create_test_product_image()
    
    # 저장
    output_dir = Path("outputs/test_images")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "test_product.jpg"
    
    test_img.save(output_path, quality=95)
    print(f"✅ 테스트 이미지 생성: {output_path}")
    print(f"📐 해상도: {test_img.size}")
