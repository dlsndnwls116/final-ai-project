import streamlit as st
import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv

# 페이지 설정
st.set_page_config(
    page_title="AI 광고 계획 생성기",
    page_icon="🎬",
    layout="wide"
)

# 환경 변수 로드
load_dotenv()

# API 키 설정
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# 제목
st.title("🎬 AI 광고 계획 생성기")
st.markdown("---")

# 사이드바 - 설정
st.sidebar.header("⚙️ 설정")

# API 키 상태 표시
col1, col2 = st.sidebar.columns(2)
with col1:
    st.metric("OpenAI", "✅" if OPENAI_KEY else "❌")
with col2:
    st.metric("GEMINI", "✅" if GEMINI_KEY else "❌")

# 프로바이더 선택
provider = st.sidebar.selectbox(
    "AI 프로바이더 선택",
    ["auto", "gpt", "gemini"],
    index=0,
    help="auto: OpenAI 우선, 실패 시 GEMINI"
)

# 메인 컨텐츠
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📝 프로젝트 정보")
    
    # 기본 입력
    ref_summary = st.text_area(
        "레퍼런스 요약",
        value="빠른 템포로 도시·건물 공간 스냅컷 → 마지막 3초 제품 클로즈업",
        help="원하는 광고 스타일이나 레퍼런스를 설명해주세요"
    )
    
    product_desc = st.text_area(
        "제품 설명",
        value="매트 블랙 무선 이어버즈, 저지연/하이브리드 ANC, 메탈릭 포인트",
        help="광고할 제품에 대해 자세히 설명해주세요"
    )
    
    brand_tone = st.text_input(
        "브랜드 톤",
        value="미니멀, 프리미엄, 하이컨트라스트",
        help="브랜드의 톤앤매너를 설명해주세요"
    )
    
    avoid_elements = st.text_input(
        "금지요소",
        value="귀여움, 파스텔, 저해상도, 과한 보케",
        help="피하고 싶은 요소들을 나열해주세요"
    )
    
    # 커스텀 프롬프트
    use_custom = st.checkbox("커스텀 프롬프트 사용")
    custom_prompt = ""
    if use_custom:
        custom_prompt = st.text_area(
            "커스텀 프롬프트",
            placeholder="직접 프롬프트를 입력하세요..."
        )

with col2:
    st.header("🚀 실행")
    
    # 출력 디렉토리
    outdir = st.text_input(
        "출력 디렉토리",
        value="out",
        help="결과 파일들이 저장될 폴더명"
    )
    
    # 실행 버튼
    if st.button("🎬 광고 계획 생성", type="primary", use_container_width=True):
        if not OPENAI_KEY and not GEMINI_KEY:
            st.error("❌ API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        else:
            with st.spinner("AI가 광고 계획을 생성하고 있습니다..."):
                try:
                    # make_plan.py의 핵심 함수들
                    from make_plan import select_engine, SYSTEM_TEMPLATE
                    
                    # 프롬프트 생성
                    if custom_prompt and use_custom:
                        prompt = custom_prompt
                    else:
                        prompt = SYSTEM_TEMPLATE.format(
                            ref_summary=ref_summary,
                            product_desc=product_desc,
                            brand_tone=brand_tone,
                            avoid=avoid_elements
                        )
                    
                    # 엔진 선택 및 실행
                    name, maker = select_engine(provider)
                    st.info(f"🤖 사용 중인 AI: {name}")
                    
                    # AI 호출
                    result = maker(prompt)
                    
                    st.success("✅ 광고 계획 생성 완료!")
                    
                    # 결과 표시
                    st.header("📋 생성된 결과")
                    
                    # JSON 결과
                    if isinstance(result, dict):
                        st.json(result)
                        
                        # 주요 정보 표시
                        if 'shots' in result:
                            st.subheader("🎬 샷 리스트")
                            for i, shot in enumerate(result['shots'], 1):
                                with st.expander(f"샷 {i}: {shot.get('caption', '제목 없음')}"):
                                    st.write(f"**시간**: {shot.get('start', 0)}s - {shot.get('end', 0)}s")
                                    st.write(f"**카메라**: {shot.get('camera', 'N/A')}")
                                    st.write(f"**배경**: {shot.get('bg_prompt', 'N/A')}")
                                    if shot.get('mj_prompt'):
                                        st.write(f"**미드저니 프롬프트**: {shot['mj_prompt']}")
                        
                        # 파일 저장
                        os.makedirs(outdir, exist_ok=True)
                        
                        # storyboard.json
                        with open(os.path.join(outdir, "storyboard.json"), "w", encoding="utf-8") as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                        
                        # prompts_midjourney.txt
                        if 'shots' in result:
                            mj_lines = []
                            for s in result['shots']:
                                mj_lines.append(f"CUT {s['id']} [{s['start']:.2f}-{s['end']:.2f}s] : {s.get('mj_prompt','')}")
                            with open(os.path.join(outdir, "prompts_midjourney.txt"), "w", encoding="utf-8") as f:
                                f.write("\n".join(mj_lines))
                        
                        # captions.srt
                        srt = []
                        idx = 1
                        for s in result['shots']:
                            cap = (s.get("caption") or "").strip()
                            if not cap:
                                continue
                            start_time = f"{int(s['start']//3600):02d}:{int((s['start']%3600)//60):02d}:{int(s['start']%60):02d},000"
                            end_time = f"{int(s['end']//3600):02d}:{int((s['end']%3600)//60):02d}:{int(s['end']%60):02d},000"
                            srt.extend([str(idx), f"{start_time} --> {end_time}", cap, ""])
                            idx += 1
                        with open(os.path.join(outdir, "captions.srt"), "w", encoding="utf-8") as f:
                            f.write("\n".join(srt))
                        
                        # editlist.txt
                        edit = []
                        for s in result['shots']:
                            dur = round(s["end"]-s["start"], 2)
                            edit.append(f"{s['id']},{dur}")
                        with open(os.path.join(outdir, "editlist.txt"), "w") as f:
                            f.write("\n".join(edit))
                        
                        st.success(f"📁 파일들이 {outdir}/ 폴더에 저장되었습니다!")
                        
                        # 다운로드 링크
                        st.subheader("📥 파일 다운로드")
                        files = ["storyboard.json", "prompts_midjourney.txt", "captions.srt", "editlist.txt"]
                        for file in files:
                            if os.path.exists(os.path.join(outdir, file)):
                                with open(os.path.join(outdir, file), "r", encoding="utf-8") as f:
                                    st.download_button(
                                        label=f"📄 {file}",
                                        data=f.read(),
                                        file_name=file,
                                        mime="text/plain"
                                    )
                    else:
                        st.text_area("생성된 결과", value=str(result), height=400)
                        
                except Exception as e:
                    st.error(f"❌ 오류가 발생했습니다: {str(e)}")
                    st.exception(e)

# 푸터
st.markdown("---")
st.markdown("💡 **팁**: 더 나은 결과를 위해 구체적인 제품 설명과 브랜드 톤을 입력해주세요!")
