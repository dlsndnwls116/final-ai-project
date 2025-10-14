# 🔐 민감정보는 .env에서만, 화면/로그 노출 금지
import json
import os
import shutil
import sys
import time
from pathlib import Path

import streamlit as st
from openai import OpenAI

# ── 루트 경로 주입(반드시 최상단) ───────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
assert os.path.exists(os.path.join(ROOT, "utils", "config.py")), "utils/config.py not found"
from utils.config import OPENAI_API_KEY

# 공통 유틸
OUT_DIR = Path(ROOT) / "outputs"
REF_DIR = OUT_DIR / "refs"
VID_DIR = OUT_DIR / "videos"
VID_DIR.mkdir(parents=True, exist_ok=True)


def save_json_util(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def switch_tab(label: str):
    # 실험적: 탭 자동 전환 (DOM을 클릭). 실패해도 앱 동작에는 영향 없음.
    st.markdown(
        f"""
        <script>
        const labels = Array.from(parent.document.querySelectorAll('button[role="tab"], div[role="tab"]'));
        const el = labels.find(x => x.innerText.trim() === "{label}");
        if (el) el.click();
        </script>
        """,
        unsafe_allow_html=True,
    )


# 최초 세션 기본값 - 안전한 초기화
NEEDED_KEYS = {
    "refs_frames": [],  # 유튜브 추출 프레임 (경로 리스트)
    "brief": None,
    "shotlist": None,
    "palette": None,
    "style_guide": None,
    "overlay_plan": None,
    "preview_video": None,
    "active_tab": "D1",  # 현재 선택된 탭 (D1/D2/D3/D4)
    # 기존 키들도 유지
    "shots": None,
    "style": None,
    "overlays": None,
}
for k, v in NEEDED_KEYS.items():
    st.session_state.setdefault(k, v)

# 디버그용: 현재 키 상태를 항상 좌측에 표시(문제 잡을 때 매우 유용)
st.sidebar.caption("Session keys")
st.sidebar.json({k: bool(st.session_state.get(k)) for k in NEEDED_KEYS})

# D2 서비스 임포트 시도(실패해도 탭은 보이게)
D2_IMPORT_ERR = None
try:
    from services.brief_and_shots import generate_brief, generate_shotlist, save_json

    HAS_D2 = True
except Exception as e:
    HAS_D2 = False
    D2_IMPORT_ERR = e

# D3 서비스 임포트 시도
D3_IMPORT_ERR = None
try:
    from services.style_guide import build_overlay_plan, extract_palette, summarize_style
    from services.style_guide import save_json as save_json_d3

    HAS_D3 = True
except Exception as e:
    HAS_D3 = False
    D3_IMPORT_ERR = e

# D4 서비스 임포트 시도
D4_IMPORT_ERR = None
try:
    from services.renderer import render_preview

    HAS_D4 = True
except Exception as e:
    HAS_D4 = False
    D4_IMPORT_ERR = e

st.set_page_config(page_title="AdGen MVP", page_icon="🎬", layout="centered")
st.caption("BUILD: D1+D2+D3+D4 tabs")  # ← 이 문구가 보이면 새 파일이 로드된 것!

# 라우팅을 index 기반으로 변경 (문자열 오타 방지)
labels = ["D1 · Healthcheck", "D2 · Brief & Shotlist", "D3 · Style & Refs", "D4 · Preview Render"]

# 마지막으로 방문한 탭 기억 후 복원
default = {"D1": 0, "D2": 1, "D3": 2, "D4": 3}[st.session_state["active_tab"]]
selected = st.segmented_control("BUILD: D1+D2+D3+D4 tabs", labels, index=default)

# active_tab 업데이트
st.session_state["active_tab"] = ["D1", "D2", "D3", "D4"][labels.index(selected)]
idx = labels.index(selected)


# ============ 렌더링 함수들 정의 ============
def render_d1():
    st.title("AdGen MVP · D1 환경 점검")
    masked = f"{len(OPENAI_API_KEY)} chars" if OPENAI_API_KEY else "MISSING"
    st.info(f"🔑 OpenAI API Key: {masked}")
    prompt = st.text_input("테스트 프롬프트", value="pong만 한 단어로 답해줘")
    if shutil.which("ffmpeg"):
        st.success("🎬 ffmpeg 감지됨 (영상 합성 준비 OK)")
    else:
        st.warning("🎬 ffmpeg 미감지 (D4~D6에서 설치 예정)")
    if st.button("환경 점검 실행"):
        start = time.time()
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            st.success("✅ OpenAI 호출 성공")
            st.write("• 응답:", resp.choices[0].message.content.strip())
            st.write(f"• 왕복지연: {int((time.time() - start) * 1000)} ms")
        except Exception as e:
            st.error("❌ OpenAI 호출 실패")
            st.exception(e)


def render_d2():
    st.title("AdGen MVP · D2 Brief & Shotlist")
    if not HAS_D2:
        st.error("D2 모듈 임포트 실패: services/brief_and_shots.py 또는 prompts/*.md 확인")
        if D2_IMPORT_ERR:
            st.exception(D2_IMPORT_ERR)
        st.code(
            "필수 파일:\n  prompts/intent_prompt.md\n  prompts/shotlist_prompt.md\n  services/brief_and_shots.py"
        )
    else:
        user_text = st.text_area(
            "요구사항 입력",
            key="d2_prompt",
            height=140,
            value="카페 오픈 20% 할인. 따뜻하고 감성 톤. 9:16 릴스.",
        )

        # 유튜브 레퍼런스 섹션
        st.subheader("🎬 유튜브 레퍼런스 (선택)")
        st.caption(f"Python: {sys.executable}")
        st.info(
            "⚠️ **권한 안내**: 본인 소유이거나 사용 허용된 영상만 입력해 주세요. 저작권을 준수해야 합니다."
        )
        yt_url = st.text_input(
            "유튜브 URL:", placeholder="https://www.youtube.com/watch?v=...", key="yt_url"
        )

        # 프레임 수 설정
        st.session_state.setdefault("yt_target_frames", 60)
        col_slider1, col_slider2 = st.columns([2, 1])
        with col_slider1:
            st.session_state["yt_target_frames"] = st.slider(
                "추출 프레임 수",
                min_value=24,
                max_value=180,
                value=60,
                step=6,
                help="60장 이상 권장: 색상/톤/장면 다양성 확보",
            )
        with col_slider2:
            st.metric("예상 용량", f"~{st.session_state['yt_target_frames'] * 0.5:.1f}MB")

        col_yt1, col_yt2 = st.columns([1, 1])
        with col_yt1:
            if st.button(
                "🎬 스마트 키프레임 추출 (권장)",
                use_container_width=True,
                disabled=not yt_url.strip(),
            ):
                try:
                    # 캐시 클리어 (안전장치)
                    import importlib

                    import utils.youtube_refs as yrefs

                    importlib.reload(yrefs)
                    from utils.youtube_refs import download_youtube, extract_keyframes

                    YT_DIR = OUT_DIR / "yt_tmp"

                    with st.spinner("유튜브 영상 다운로드 중..."):
                        vid_path = download_youtube(yt_url.strip(), YT_DIR)
                    with st.spinner("스마트 키프레임 추출 중..."):
                        refs = extract_keyframes(
                            video_path=vid_path,
                            save_dir=REF_DIR,
                            target_frames=st.session_state["yt_target_frames"],
                            candidate_fps=3.0,
                            min_sharpness=60.0,
                            hash_thresh=8,
                            min_scene_diff=0.3,
                            resize_width=960,
                        )
                    # 세션에 프레임 경로 저장
                    st.session_state["refs_frames"] = [str(p) for p in refs]
                    st.success(f"스마트 키프레임 {len(refs)}장 추출 완료! (outputs/refs)")
                    st.info("💡 중복 제거, 흐림 필터, 장면 다양성 확보로 고품질 레퍼런스 생성")
                except Exception as e:
                    st.error(f"키프레임 추출 실패: {e}")
                    st.code(
                        "필요 패키지: pip install yt-dlp opencv-python imagehash", language="bash"
                    )
                    st.warning("💡 **해결 방법**: 위 Python 경로로 패키지를 설치하세요.")
                    st.code(
                        f'"{sys.executable}" -m pip install yt-dlp opencv-python imagehash',
                        language="bash",
                    )

        with col_yt2:
            if st.button(
                "⚡ 빠른 6장 추출 (MVP)", use_container_width=True, disabled=not yt_url.strip()
            ):
                try:
                    # 캐시 클리어 (안전장치)
                    import importlib

                    import utils.youtube_refs as yrefs

                    importlib.reload(yrefs)
                    from utils.youtube_refs import download_youtube, sample_frames

                    YT_DIR = OUT_DIR / "yt_tmp"

                    with st.spinner("유튜브 영상 다운로드 중..."):
                        vid_path = download_youtube(yt_url.strip(), YT_DIR)
                    with st.spinner("프레임 추출 중..."):
                        refs = sample_frames(
                            vid_path, REF_DIR, num_frames=6, start_sec=3.0, end_sec=None
                        )
                    # 세션에 프레임 경로 저장
                    st.session_state["refs_frames"] = [str(p) for p in refs]
                    st.success(
                        f"빠른 레퍼런스 {len(refs)}장 추출 완료. D3에서 자동으로 사용됩니다."
                    )
                except Exception as e:
                    st.error(f"레퍼런스 추출 실패: {e}")
                    st.code("필요 패키지: pip install yt-dlp opencv-python", language="bash")
                    st.warning("💡 **해결 방법**: 위 Python 경로로 패키지를 설치하세요.")
                    st.code(
                        f'"{sys.executable}" -m pip install yt-dlp opencv-python', language="bash"
                    )

        st.divider()
        ref_desc = st.text_input("레퍼런스(선택): 이미지/영상 키워드")

        # 원-클릭 버튼
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("⚡ 원-클릭: 브리프 + 샷리스트", use_container_width=True):
                if not user_text.strip():
                    st.warning("요구사항을 입력해 주세요.")
                    return

                with st.spinner("브리프 생성 중..."):
                    brief = generate_brief(user_text, ref_desc or None)
                    st.session_state["brief"] = brief
                    st.session_state["shotlist"] = brief  # 호환성
                    save_json_util(brief, OUT_DIR / "brief.json")

                with st.spinner("샷리스트 생성 중..."):
                    shots = generate_shotlist(brief)
                    st.session_state["shots"] = shots
                    st.session_state["shotlist"] = shots  # 호환성
                    save_json_util(shots, OUT_DIR / "shots.json")

                st.success("D2 완료! D3로 이동합니다.")
                # D3로 자동 전환
                st.session_state["active_tab"] = "D3"
                st.rerun()

        with col2:
            st.write("← 이 버튼 하나면 D2는 끝!")

        st.divider()
        st.write("**개별 실행** (원-클릭 사용 시 생략 가능)")
        c1, c2 = st.columns(2)
        if c1.button("1) 브리프 생성"):
            with st.spinner("브리프 생성 중..."):
                brief = generate_brief(user_text, ref_desc or None)
                st.session_state["brief"] = brief
                save_json(brief, Path(ROOT) / "outputs/briefs/brief_latest.json")
                st.success("브리프 생성 완료")
                st.code(json.dumps(brief, ensure_ascii=False, indent=2), "json")
        if c2.button("2) 샷리스트 생성"):
            if "brief" not in st.session_state:
                st.warning("먼저 브리프를 생성하세요.")
            else:
                with st.spinner("샷리스트 생성 중..."):
                    shots = generate_shotlist(st.session_state["brief"])
                    st.session_state["shots"] = shots
                    save_json(shots, Path(ROOT) / "outputs/briefs/shotlist_latest.json")
                    total = sum(s["dur"] for s in shots)
                    st.success(f"샷리스트 생성 완료 · 총 {total:.1f}s")
                    st.code(json.dumps(shots, ensure_ascii=False, indent=2), "json")


def render_d3():
    st.title("AdGen MVP · D3 Style & Refs")
    st.write(
        "레퍼런스 이미지로 팔레트를 뽑고, 브리프 기반 스타일 가이드와 오버레이 플랜을 생성합니다."
    )

    # D3가 빈화면으로 보이지 않도록, 조건 미충족 시 안내 메시지 출력
    s = st.session_state
    if not s.get("brief") or not s.get("shotlist"):
        st.info("D2에서 브리프/샷리스트를 먼저 생성해 주세요.")
        return

    if not HAS_D3:
        st.error("D3 모듈 임포트 실패: services/style_guide.py 또는 prompts/style_prompt.md 확인")
        if D3_IMPORT_ERR:
            st.exception(D3_IMPORT_ERR)
        st.code("필수 파일:\n  prompts/style_prompt.md\n  services/style_guide.py")
    else:
        up = st.file_uploader(
            "레퍼런스 이미지(최대 6장)",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
        )
        extra_kw = st.text_input(
            "추가 키워드(선택)", placeholder="우드톤, 따뜻한 조명, 필름그레인…"
        )

        def _save_refs(files):
            REF_DIR.mkdir(parents=True, exist_ok=True)
            saved = []
            for f in files:
                p = REF_DIR / f.name
                p.write_bytes(f.read())
                saved.append(p)
            return saved

        # 원-클릭 버튼 (항상 보이되, 조건 체크는 내부에서)
        do_all = st.button(
            "🚀 원-클릭: 팔레트→스타일→오버레이→프리뷰 렌더", use_container_width=True
        )
        if do_all:
            ref_paths = []
            if up:
                ref_paths = _save_refs(up)
            elif s.get("refs_frames"):
                # 유튜브에서 추출한 프레임 사용
                ref_paths = [Path(p) for p in s["refs_frames"]]

            # 1) 팔레트
            with st.spinner("팔레트 추출 중..."):
                if ref_paths:
                    palette = extract_palette(ref_paths, k=5)
                else:
                    palette = st.session_state.get("brief", {}).get("colors", []) or [
                        "#F5EDE0",
                        "#2C2C2C",
                    ]
                st.session_state["palette"] = palette
                save_json_util(palette, OUT_DIR / "palette.json")

            # 2) 스타일 가이드
            with st.spinner("스타일 가이드 생성 중..."):
                style = summarize_style(st.session_state["brief"], palette, extra_kw or None)
                st.session_state["style"] = style
                st.session_state["style_guide"] = style  # 호환성
                save_json_util(style, OUT_DIR / "style.json")

            # 3) 오버레이 플랜
            with st.spinner("오버레이 플랜 생성 중..."):
                overlays = build_overlay_plan(st.session_state["shots"], style)
                st.session_state["overlays"] = overlays
                st.session_state["overlay_plan"] = overlays  # 호환성
                save_json_util(overlays, OUT_DIR / "overlays.json")

            # 4) D4 프리뷰 렌더
            with st.spinner("프리뷰 렌더 중... (mp4)"):
                out_path = VID_DIR / "preview_d4.mp4"
                render_preview(
                    shots=st.session_state["shots"],
                    style=style,
                    overlays=overlays,
                    out_path=out_path,
                )
                st.session_state["preview_video"] = str(out_path)

            st.success("렌더 완료! D4로 이동합니다.")
            # D3에서도 바로 미리보기
            st.video(st.session_state["preview_video"])

            # D4로 자동 전환
            st.session_state["active_tab"] = "D4"
            st.rerun()

        # 현재 세션 상태 디버그
        with st.expander("세션 상태 확인(디버그)"):
            st.json(
                {
                    "has_brief": st.session_state.get("brief") is not None,
                    "has_shots": st.session_state.get("shots") is not None,
                    "has_palette": st.session_state.get("palette") is not None,
                    "has_style": st.session_state.get("style") is not None,
                    "has_overlays": st.session_state.get("overlays") is not None,
                    "preview_video": st.session_state.get("preview_video"),
                }
            )

        st.divider()
        st.write("**개별 실행** (원-클릭 사용 시 생략 가능)")
        c1, c2 = st.columns(2)

        if c1.button("1) 팔레트 추출"):
            if not up:
                # 브리프 colors가 있으면 그걸 사용(백업 경로)
                pal = st.session_state.get("brief", {}).get("colors", []) or ["#F5EDE0", "#2C2C2C"]
                st.session_state["palette"] = pal
                save_json_d3(pal, Path(ROOT) / "outputs/briefs/palette_latest.json")
                st.warning("이미지 없음 → 브리프 colors/기본 팔레트 사용")
            else:
                tmp_dir = Path(ROOT) / "outputs/refs"
                tmp_dir.mkdir(parents=True, exist_ok=True)
                paths = []
                for f in up[:6]:
                    p = tmp_dir / f.name
                    with open(p, "wb") as w:
                        w.write(f.read())
                    paths.append(p)
                pal = extract_palette(paths, k=5)
                st.session_state["palette"] = pal
                save_json_d3(pal, Path(ROOT) / "outputs/briefs/palette_latest.json")
            st.success(f"팔레트: {st.session_state['palette']}")

        if c2.button("2) 스타일 가이드 생성"):
            if "brief" not in st.session_state:
                st.warning("먼저 D2에서 브리프를 생성하세요.")
            else:
                pal = st.session_state.get(
                    "palette", st.session_state["brief"].get("colors", []) or ["#F5EDE0", "#2C2C2C"]
                )
                style = summarize_style(st.session_state["brief"], pal, extra_kw or None)
                st.session_state["style"] = style
                save_json_d3(style, Path(ROOT) / "outputs/briefs/style_guide.json")
                st.success("스타일 가이드 생성 완료")
                st.code(json.dumps(style, ensure_ascii=False, indent=2), "json")

        if st.button("3) 오버레이 플랜 생성"):
            if "shots" not in st.session_state:
                st.warning("D2에서 샷리스트를 먼저 생성하세요.")
            elif "style" not in st.session_state:
                st.warning("스타일 가이드를 먼저 생성하세요.")
            else:
                overlays = build_overlay_plan(st.session_state["shots"], st.session_state["style"])
                st.session_state["overlays"] = overlays
                save_json_d3(overlays, Path(ROOT) / "outputs/briefs/overlay_plan.json")
                st.success("오버레이 플랜 생성 완료")
                st.code(json.dumps(overlays, ensure_ascii=False, indent=2), "json")


def render_d4():
    st.title("AdGen MVP · D4 Preview Render")
    st.write("샷리스트 + 스타일 가이드 + 오버레이 플랜으로 9:16 미리보기 mp4를 생성합니다.")

    # D4가 빈화면으로 보이지 않도록, 조건 미충족 시 안내 메시지 출력
    s = st.session_state
    if not s.get("style_guide"):
        st.info("D3에서 스타일 가이드를 먼저 생성해 주세요.")
        return

    if not HAS_D4:
        st.error("D4 모듈 임포트 실패: services/renderer.py 또는 moviepy 패키지 확인")
        if D4_IMPORT_ERR:
            st.exception(D4_IMPORT_ERR)
        st.code("필수 패키지:\n  pip install moviepy imageio-ffmpeg pillow numpy")
    else:
        # 결과 자동 표시
        st.header("프리뷰 영상")
        vid = st.session_state.get("preview_video")
        if vid and Path(vid).exists():
            st.video(vid)
        else:
            st.info("아직 렌더된 영상이 없습니다. D3에서 원-클릭 버튼으로 렌더를 실행하세요.")

        # 현재 세션 상태 디버그
        with st.expander("세션 상태 확인(디버그)"):
            st.json(
                {
                    "preview_video": st.session_state.get("preview_video"),
                    "has_shots": st.session_state.get("shots") is not None,
                    "has_style": st.session_state.get("style") is not None,
                    "has_overlays": st.session_state.get("overlays") is not None,
                }
            )

        st.divider()
        st.write("**수동 렌더** (원-클릭 사용 시 생략 가능)")
        if st.button("프리뷰 렌더(mp4)"):
            if "shots" not in st.session_state:
                st.warning("D2에서 샷리스트를 먼저 생성하세요.")
            elif "style" not in st.session_state:
                st.warning("D3에서 스타일 가이드를 먼저 생성하세요.")
            else:
                # overlays가 없으면 즉석에서 만들어도 됨 (D3에서 생성했으면 세션에 존재)
                if "overlays" not in st.session_state:
                    from services.style_guide import build_overlay_plan

                    st.session_state["overlays"] = build_overlay_plan(
                        st.session_state["shots"], st.session_state["style"]
                    )

                out = Path(ROOT) / "outputs/videos/preview_d4.mp4"
                try:
                    with st.spinner("렌더링 중..."):
                        render_preview(
                            shots=st.session_state["shots"],
                            style=st.session_state["style"],
                            overlays=st.session_state["overlays"],
                            out_path=out,
                            crossfade=0.2,
                        )
                    st.session_state["preview_video"] = str(out)
                    st.success("렌더 완료")
                    st.video(str(out))
                except Exception as e:
                    st.error(
                        f"렌더 실패: {e}\n\nffmpeg 또는 imageio-ffmpeg가 없는 경우 설치가 필요합니다."
                    )
                    st.code("pip install imageio-ffmpeg", language="bash")


# ============ index 기반 렌더링 ============
[render_d1, render_d2, render_d3, render_d4][idx]()
