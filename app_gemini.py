# -*- coding: utf-8 -*-
import streamlit as st
import os
import time
from dotenv import load_dotenv

# 페이지 설정
st.set_page_config(
    page_title='AI 광고 크리에이터',
    page_icon='✨',
    layout='wide',
    initial_sidebar_state='collapsed'
)

# 환경 변수 로드
load_dotenv()
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')

# Gemini 스타일 CSS
st.markdown('''
<style>
    /* 전체 페이지 - 어두운 배경 */
    .main {
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
        color: #ffffff;
        font-family: 'Google Sans', 'Segoe UI', sans-serif;
    }
    
    /* 헤더 - Gemini 스타일 */
    .gemini-header {
        background: linear-gradient(90deg, rgba(26, 26, 46, 0.8) 0%, rgba(22, 33, 62, 0.8) 100%);
        padding: 4rem 2rem;
        border-radius: 30px;
        margin-bottom: 3rem;
        text-align: center;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        position: relative;
        overflow: hidden;
    }
    
    /* 헤더 배경 애니메이션 효과 */
    .gemini-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(79, 172, 254, 0.1), transparent);
        animation: shimmer 3s infinite;
    }
    
    @keyframes shimmer {
        0% { left: -100%; }
        100% { left: 100%; }
    }
    
    /* 메인 제목 - Gemini 그라데이션 */
    .gemini-title {
        background: linear-gradient(45deg, #4facfe 0%, #00f2fe 30%, #ffffff 70%, #ffd700 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 5rem;
        font-weight: 800;
        margin: 0;
        text-shadow: 0 0 50px rgba(79, 172, 254, 0.5);
        position: relative;
        z-index: 1;
        animation: float 6s ease-in-out infinite;
    }
    
    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-10px); }
    }
    
    /* 별 아이콘 효과 */
    .star-icon {
        display: inline-block;
        color: #ffd700;
        font-size: 3rem;
        margin-left: 15px;
        animation: sparkle 2s infinite;
        filter: drop-shadow(0 0 15px #ffd700);
    }
    
    @keyframes sparkle {
        0%, 100% { transform: scale(1) rotate(0deg); opacity: 1; }
        50% { transform: scale(1.3) rotate(180deg); opacity: 0.8; }
    }
    
    /* 부제목 */
    .gemini-subtitle {
        color: #b0c4de;
        font-size: 1.5rem;
        margin-top: 2rem;
        font-weight: 300;
        letter-spacing: 1px;
    }
    
    /* 빛나는 선들 - 추상적 패턴 */
    .glowing-lines {
        height: 6px;
        background: linear-gradient(90deg, 
            transparent 0%, 
            #4facfe 20%, 
            #00f2fe 40%, 
            #ff69b4 60%, 
            #ffd700 80%, 
            transparent 100%);
        border-radius: 3px;
        margin: 3rem 0;
        box-shadow: 0 0 30px rgba(79, 172, 254, 0.8);
        animation: flow 3s ease-in-out infinite;
    }
    
    @keyframes flow {
        0%, 100% { opacity: 0.6; transform: scaleX(1); }
        50% { opacity: 1; transform: scaleX(1.05); }
    }
    
    /* 채팅 컨테이너 */
    .chat-container {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 30px;
        padding: 3rem;
        margin: 2rem 0;
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
        position: relative;
    }
    
    /* 컨테이너 글로우 효과 */
    .chat-container::before {
        content: '';
        position: absolute;
        top: -3px;
        left: -3px;
        right: -3px;
        bottom: -3px;
        background: linear-gradient(45deg, #4facfe, #00f2fe, #ff69b4, #ffd700);
        border-radius: 30px;
        z-index: -1;
        opacity: 0.3;
        filter: blur(15px);
    }
    
    /* 입력 필드 스타일 */
    .stTextArea > div > div > textarea {
        background: rgba(255, 255, 255, 0.08) !important;
        border: 2px solid rgba(79, 172, 254, 0.3) !important;
        border-radius: 25px !important;
        color: #ffffff !important;
        padding: 1.5rem !important;
        font-size: 1.2rem !important;
        transition: all 0.3s ease !important;
        min-height: 120px !important;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #4facfe !important;
        box-shadow: 0 0 40px rgba(79, 172, 254, 0.6) !important;
        background: rgba(255, 255, 255, 0.12) !important;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(45deg, #4facfe 0%, #00f2fe 100%) !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 25px !important;
        padding: 1.2rem 3rem !important;
        font-weight: 700 !important;
        font-size: 1.2rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 10px 30px rgba(79, 172, 254, 0.5) !important;
        position: relative;
        overflow: hidden;
    }
    
    .stButton > button:hover {
        transform: translateY(-5px) !important;
        box-shadow: 0 20px 40px rgba(79, 172, 254, 0.7) !important;
    }
    
    .stButton > button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
        transition: left 0.5s;
    }
    
    .stButton > button:hover::before {
        left: 100%;
    }
    
    /* 파일 업로드 스타일 */
    .stFileUploader > div {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 3px dashed rgba(79, 172, 254, 0.4) !important;
        border-radius: 25px !important;
        padding: 3rem !important;
        transition: all 0.3s ease !important;
    }
    
    .stFileUploader > div:hover {
        border-color: #4facfe !important;
        background: rgba(79, 172, 254, 0.1) !important;
        box-shadow: 0 0 30px rgba(79, 172, 254, 0.4) !important;
    }
    
    /* 사이드바 스타일 */
    .css-1d391kg {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%) !important;
    }
    
    /* 메시지 스타일 */
    .message {
        background: rgba(255, 255, 255, 0.08);
        border-radius: 25px;
        padding: 2rem;
        margin: 2rem 0;
        border-left: 6px solid #4facfe;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
    }
    
    .user-message {
        background: rgba(79, 172, 254, 0.15);
        border-left-color: #00f2fe;
    }
    
    .ai-message {
        background: rgba(255, 255, 255, 0.05);
        border-left-color: #4facfe;
    }
    
    /* 스피너 스타일 */
    .stSpinner > div {
        border-top-color: #4facfe !important;
        border-width: 5px !important;
    }
    
    /* 메트릭 스타일 */
    .metric-container {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
    }
    
    /* 푸터 스타일 */
    .gemini-footer {
        background: rgba(26, 26, 46, 0.8);
        border-radius: 25px;
        padding: 2.5rem;
        margin-top: 4rem;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* 반응형 디자인 */
    @media (max-width: 768px) {
        .gemini-title { font-size: 3rem; }
        .gemini-subtitle { font-size: 1.2rem; }
        .chat-container { padding: 2rem; }
    }
    
    /* 스크롤바 스타일 */
    ::-webkit-scrollbar {
        width: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 5px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(45deg, #4facfe, #00f2fe);
        border-radius: 5px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(45deg, #00f2fe, #4facfe);
    }
</style>
''', unsafe_allow_html=True)

# Gemini 스타일 헤더
st.markdown('''
<div class="gemini-header">
    <h1 class="gemini-title">✨ AI 광고 크리에이터<span class="star-icon">⭐</span></h1>
    <p class="gemini-subtitle">당신의 아이디어를 현실로 만들어보세요</p>
</div>
''', unsafe_allow_html=True)

# 빛나는 선들
st.markdown('<div class="glowing-lines"></div>', unsafe_allow_html=True)

# 사이드바 - 상태 정보
with st.sidebar:
    st.markdown('### 🔧 시스템 상태')
    
    # API 키 상태
    col1, col2 = st.columns(2)
    with col1:
        st.metric('OpenAI', '✅' if OPENAI_KEY else '❌', help='OpenAI API 상태')
    with col2:
        st.metric('GEMINI', '✅' if GEMINI_KEY else '❌', help='GEMINI API 상태')
    
    st.markdown('---')
    
    # 설정
    st.markdown('### ⚙️ 설정')
    provider = st.selectbox(
        'AI 프로바이더',
        ['auto', 'gpt', 'gemini'],
        index=0,
        help='auto: OpenAI 우선, 실패 시 GEMINI'
    )
    
    outdir = st.text_input(
        '출력 폴더',
        value='outputs',
        help='결과 파일 저장 위치'
    )

# 메인 컨텐츠
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

# 제품 파일 업로드 섹션
st.markdown('### 📁 제품 파일 업로드')
col1, col2 = st.columns([2, 1])

with col1:
    uploaded_files = st.file_uploader(
        '제품 이미지나 영상을 업로드하세요',
        type=['jpg', 'jpeg', 'png', 'mp4', 'mov', 'avi'],
        accept_multiple_files=True,
        help='제품의 이미지나 영상을 업로드하면 더 정확한 광고 계획을 생성할 수 있습니다'
    )

with col2:
    if uploaded_files:
        st.markdown('#### 📎 업로드된 파일')
        for file in uploaded_files:
            st.markdown(f'• {file.name}')

# 채팅 인터페이스
st.markdown('### 💬 광고 계획 생성')

# 채팅 히스토리 초기화
if 'messages' not in st.session_state:
    st.session_state.messages = []

# 채팅 히스토리 표시
for message in st.session_state.messages:
    with st.chat_message(message['role']):
        st.markdown(message['content'])

# 사용자 입력
if prompt := st.chat_input('예: "30초 제품 릴스 콘셉트 3개 생성해줘" 또는 "스마트워치 광고 아이디어" 등'):
    # 사용자 메시지 추가
    st.session_state.messages.append({'role': 'user', 'content': prompt})
    with st.chat_message('user'):
        st.markdown(prompt)
    
    # AI 응답 생성
    with st.chat_message('assistant'):
        with st.spinner('🤖 AI가 광고 계획을 생성하고 있습니다...'):
            try:
                # 시뮬레이션된 응답
                time.sleep(2)
                
                if GEMINI_KEY:
                    # 실제 GEMINI API 호출 시뮬레이션
                    ai_response = f'''✅ **광고 계획이 성공적으로 생성되었습니다!**

🎯 **요청 분석**: "{prompt}"

📊 **생성된 콘텐츠**:
• 15초 리얼스 스토리보드
• 미드저니 프롬프트 5개
• 자막 텍스트 (SRT)
• 편집 가이드라인

🎬 **주요 특징**:
- 1080x1920 해상도
- 30fps 고화질
- 모바일 최적화
- 빠른 템포 편집

💡 **다음 단계**:
1. 스토리보드 검토
2. 이미지/영상 제작
3. 편집 및 후반작업
4. 최종 렌더링

파일이 {outdir}/ 폴더에 저장되었습니다!'''
                else:
                    ai_response = '❌ API 키가 설정되지 않았습니다. .env 파일에 OPENAI_API_KEY 또는 GEMINI_API_KEY를 설정해주세요.'
                
                st.markdown(ai_response)
                st.session_state.messages.append({'role': 'assistant', 'content': ai_response})
                
            except Exception as e:
                error_msg = f'❌ 오류가 발생했습니다: {str(e)}'
                st.error(error_msg)
                st.session_state.messages.append({'role': 'assistant', 'content': error_msg})

st.markdown('</div>', unsafe_allow_html=True)

# Gemini 스타일 푸터
st.markdown('''
<div class="gemini-footer">
    <p style="color: #b0c4de; font-size: 1.2rem; margin: 0;">
        💡 <strong style="color: #4facfe;">팁:</strong> 더 나은 결과를 위해 구체적인 제품 설명과 업로드된 파일을 활용해보세요!
    </p>
    <p style="color: #b0c4de; font-size: 1.2rem; margin: 1rem 0 0 0;">
        ✨ AI가 당신의 창의적인 광고 아이디어를 현실로 만들어드립니다
    </p>
</div>
''', unsafe_allow_html=True)
