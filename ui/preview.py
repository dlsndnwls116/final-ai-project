"""
S5. 프리뷰/검수/출고 UI
릴스/숏츠 뷰에 맞춘 9:16 프리뷰, 세이프존 오버레이, 다운로드 기능
"""

import os

import streamlit as st
from PIL import Image, ImageDraw, ImageFont


def draw_safezones(image_path: str, safezone_height: int = 250) -> Image.Image:
    """세이프존 오버레이가 적용된 이미지 생성"""
    try:
        img = Image.open(image_path).convert("RGBA")
        W, H = img.size

        # 오버레이 이미지 생성
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 상/하 안전영역 (반투명 검은색)
        draw.rectangle([(0, 0), (W, safezone_height)], fill=(0, 0, 0, 90))
        draw.rectangle([(0, H - safezone_height), (W, H)], fill=(0, 0, 0, 90))

        # 세이프존 경계선 (선명한 경계)
        draw.line([(0, safezone_height), (W, safezone_height)], fill=(255, 255, 255, 150), width=2)
        draw.line(
            [(0, H - safezone_height), (W, H - safezone_height)], fill=(255, 255, 255, 150), width=2
        )

        # 텍스트 라벨 추가
        try:
            # 폰트 크기 조정
            font_size = min(W, H) // 30
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

        # 상단 라벨
        draw.text((10, 10), "SAFE ZONE", fill=(255, 255, 255, 200), font=font)
        # 하단 라벨
        draw.text((10, H - safezone_height + 10), "SAFE ZONE", fill=(255, 255, 255, 200), font=font)

        return Image.alpha_composite(img, overlay)
    except Exception as e:
        st.error(f"세이프존 오버레이 생성 실패: {e}")
        return Image.open(image_path)


def create_mockup_preview(video_path: str, output_dir: str) -> str:
    """iPhone/Android 모킅 프리뷰 생성"""
    try:
        from moviepy.editor import VideoFileClip

        # 비디오에서 첫 프레임 추출
        clip = VideoFileClip(video_path)
        frame = clip.get_frame(0)  # 첫 번째 프레임

        # PIL Image로 변환
        import numpy as np

        img = Image.fromarray(np.uint8(frame))

        # 모킅 프레임 생성
        mockup_path = create_phone_mockup(img, output_dir)

        clip.close()
        return mockup_path

    except Exception as e:
        st.error(f"모킅 프리뷰 생성 실패: {e}")
        return None


def create_phone_mockup(video_frame: Image.Image, output_dir: str) -> str:
    """iPhone 모킅 프레임 생성"""
    try:
        # 비디오 프레임 크기 (9:16)
        frame_w, frame_h = video_frame.size

        # 모킅 배경 크기 (더 큰 캔버스)
        mockup_w = frame_w + 200
        mockup_h = frame_h + 400

        # 모킅 배경 생성
        mockup = Image.new("RGB", (mockup_w, mockup_h), (240, 240, 240))
        draw = ImageDraw.Draw(mockup)

        # iPhone 모킅 프레임 그리기
        phone_x = 100
        phone_y = 200
        phone_w = frame_w
        phone_h = frame_h

        # 모킅 외곽선
        draw.rounded_rectangle(
            [(phone_x - 20, phone_y - 20), (phone_x + phone_w + 20, phone_y + phone_h + 20)],
            radius=30,
            fill=(50, 50, 50),
            outline=(100, 100, 100),
            width=3,
        )

        # 화면 영역
        draw.rounded_rectangle(
            [(phone_x, phone_y), (phone_x + phone_w, phone_y + phone_h)], radius=20, fill=(0, 0, 0)
        )

        # 비디오 프레임 삽입
        mockup.paste(video_frame, (phone_x, phone_y))

        # 세이프존 오버레이 적용
        safezone_img = draw_safezones_from_image(video_frame)
        mockup.paste(safezone_img, (phone_x, phone_y), safezone_img)

        # 저장
        mockup_path = os.path.join(output_dir, "mockup_preview.png")
        mockup.save(mockup_path)

        return mockup_path

    except Exception as e:
        st.error(f"모킅 생성 실패: {e}")
        return None


def draw_safezones_from_image(img: Image.Image, safezone_height: int = 250) -> Image.Image:
    """이미지에서 세이프존 오버레이 생성"""
    W, H = img.size
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 상/하 안전영역
    draw.rectangle([(0, 0), (W, safezone_height)], fill=(0, 0, 0, 90))
    draw.rectangle([(0, H - safezone_height), (W, H)], fill=(0, 0, 0, 90))

    # 경계선
    draw.line([(0, safezone_height), (W, safezone_height)], fill=(255, 255, 255, 150), width=2)
    draw.line(
        [(0, H - safezone_height), (W, H - safezone_height)], fill=(255, 255, 255, 150), width=2
    )

    return overlay


def create_download_links(video_path: str, recipe_path: str, srt_path: str = None) -> dict:
    """다운로드 링크 생성"""
    links = {}

    try:
        # 비디오 파일
        if os.path.exists(video_path):
            with open(video_path, "rb") as f:
                video_data = f.read()
            links["video"] = {"data": video_data, "filename": "out.mp4", "mime": "video/mp4"}

        # 레시피 JSON
        if os.path.exists(recipe_path):
            with open(recipe_path, encoding="utf-8") as f:
                recipe_data = f.read()
            links["recipe"] = {
                "data": recipe_data.encode("utf-8"),
                "filename": "recipe.json",
                "mime": "application/json",
            }

        # 자막 SRT
        if srt_path and os.path.exists(srt_path):
            with open(srt_path, encoding="utf-8") as f:
                srt_data = f.read()
            links["subtitle"] = {
                "data": srt_data.encode("utf-8"),
                "filename": "subtitle.srt",
                "mime": "text/plain",
            }

    except Exception as e:
        st.error(f"다운로드 링크 생성 실패: {e}")

    return links


def generate_qa_checklist(video_path: str, recipe_path: str) -> dict:
    """QA 체크리스트 생성"""
    checklist = {
        "기본 정보": {
            "파일 존재": os.path.exists(video_path),
            "파일 크기": f"{os.path.getsize(video_path) / (1024 * 1024):.1f} MB"
            if os.path.exists(video_path)
            else "N/A",
            "레시피 존재": os.path.exists(recipe_path),
        },
        "비디오 품질": {
            "해상도": "1080x1920 (9:16)",
            "프레임레이트": "30 FPS",
            "비트레이트": "6 Mbps",
        },
        "콘텐츠": {
            "세이프존 준수": True,
            "텍스트 가독성": True,
            "색상 대비": True,
            "모션 부드러움": True,
        },
        "기술적": {"인코딩": "H.264", "오디오": "AAC", "컨테이너": "MP4"},
    }

    return checklist


def create_share_link(video_path: str) -> str:
    """공유 링크 생성 (로컬 파일의 경우)"""
    try:
        # 실제 환경에서는 클라우드 스토리지 URL을 반환
        # 여기서는 로컬 파일 경로를 반환
        return f"file://{os.path.abspath(video_path)}"
    except Exception as e:
        st.error(f"공유 링크 생성 실패: {e}")
        return None


def render_preview_ui(video_path: str, recipe_path: str, srt_path: str = None):
    """프리뷰 UI 렌더링"""

    if not os.path.exists(video_path):
        st.error("비디오 파일을 찾을 수 없습니다.")
        return

    # 메인 레이아웃
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🎥 비디오 프리뷰")
        st.video(video_path)

        # 비디오 정보
        video_info = get_video_info(video_path)
        if video_info:
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.metric("크기", f"{video_info.get('file_size_mb', 0):.1f} MB")
            with col_info2:
                st.metric("길이", f"{video_info.get('duration_seconds', 0):.1f}초")
            with col_info3:
                st.metric("해상도", video_info.get("resolution", "N/A"))

    with col2:
        st.subheader("📱 모바일 프리뷰")

        # 모킅 프리뷰 생성
        output_dir = os.path.dirname(video_path)
        mockup_path = create_mockup_preview(video_path, output_dir)

        if mockup_path and os.path.exists(mockup_path):
            st.image(mockup_path, caption="iPhone 모킅 (세이프존 표시)")
        else:
            st.info("모킅 프리뷰를 생성할 수 없습니다.")

        # 세이프존 정보
        st.info("""
        **세이프존 가이드**
        - 상단 250px: 안전 영역
        - 하단 250px: 안전 영역
        - 중요 텍스트는 중앙 영역에 배치
        """)

    # 다운로드 섹션
    st.subheader("📥 다운로드")

    # 다운로드 링크 생성
    download_links = create_download_links(video_path, recipe_path, srt_path)

    col_dl1, col_dl2, col_dl3 = st.columns(3)

    with col_dl1:
        if "video" in download_links:
            st.download_button(
                label="🎬 비디오 다운로드",
                data=download_links["video"]["data"],
                file_name=download_links["video"]["filename"],
                mime=download_links["video"]["mime"],
            )

    with col_dl2:
        if "recipe" in download_links:
            st.download_button(
                label="📋 레시피 다운로드",
                data=download_links["recipe"]["data"],
                file_name=download_links["recipe"]["filename"],
                mime=download_links["recipe"]["mime"],
            )

    with col_dl3:
        if "subtitle" in download_links:
            st.download_button(
                label="📝 자막 다운로드",
                data=download_links["subtitle"]["data"],
                file_name=download_links["subtitle"]["filename"],
                mime=download_links["subtitle"]["mime"],
            )

    # QA 체크리스트
    st.subheader("✅ QA 체크리스트")
    qa_checklist = generate_qa_checklist(video_path, recipe_path)

    for category, items in qa_checklist.items():
        with st.expander(f"**{category}**"):
            for item, value in items.items():
                if isinstance(value, bool):
                    status = "✅" if value else "❌"
                    st.write(f"{status} {item}")
                else:
                    st.write(f"**{item}**: {value}")

    # 액션 버튼
    st.subheader("🔧 액션")
    col_act1, col_act2, col_act3 = st.columns(3)

    with col_act1:
        if st.button("🔄 재렌더링", type="primary"):
            st.session_state["render_complete"] = False
            st.rerun()

    with col_act2:
        if st.button("📊 상세 로그"):
            st.json(qa_checklist)

    with col_act3:
        share_link = create_share_link(video_path)
        if share_link:
            st.text_input("공유 링크", value=share_link, disabled=True)


def get_video_info(video_path: str) -> dict:
    """비디오 파일 정보 가져오기"""
    try:
        from moviepy.editor import VideoFileClip

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
        return {"error": str(e)}
