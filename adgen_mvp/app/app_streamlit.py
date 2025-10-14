# app/app_streamlit.py
import sys
from pathlib import Path

# 1) 이 파일에서 위로 올라가며 'utils/config.py'가 보이는 지점까지 탐색
_here = Path(__file__).resolve()
ROOT = _here
for _ in range(8):  # 최대 8단계 위까지
    if (ROOT.parent / "utils" / "config.py").exists():
        ROOT = ROOT.parent
        break
    ROOT = ROOT.parent
else:
    raise FileNotFoundError(f"utils/config.py not found. start={_here}")

# 2) sys.path 주입
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import shutil
import time

import streamlit as st
from openai import OpenAI

from utils.config import OPENAI_API_KEY  # ← 이제 안전하게 import 가능

# D2 서비스 임포트 시도(실패해도 탭은 보이게)
D2_IMPORT_ERR = None
try:
    from services.brief_and_shots import generate_brief, generate_shotlist, save_json

    HAS_D2 = True
except Exception as e:
    HAS_D2 = False
    D2_IMPORT_ERR = e

st.set_page_config(page_title="AdGen MVP", page_icon="🎬", layout="centered")
st.caption("BUILD: D1+D2 tabs")  # ← 이 문구가 보이면 새 파일이 로드된 것!

# 탭 구성(항상 D2 탭은 보여주고, 실패 시 이유를 화면에 표시)
tab1, tab2 = st.tabs(["D1 · Healthcheck", "D2 · Brief & Shotlist"])

# ============ D1 ============
with tab1:
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

# ============ D2 ============
with tab2:
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
            "요구사항 입력", height=140, value="카페 오픈 20% 할인. 따뜻하고 감성 톤. 9:16 릴스."
        )
        ref_desc = st.text_input("레퍼런스(선택): 이미지/영상 키워드")

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
                    save_json(shots, Path(ROOT) / "outputs/briefs/shotlist_latest.json")
                    total = sum(s["dur"] for s in shots)
                    st.success(f"샷리스트 생성 완료 · 총 {total:.1f}s")
                    st.code(json.dumps(shots, ensure_ascii=False, indent=2), "json")
