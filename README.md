# 🎬 Final AI Project - AI 광고 크리에이터

Codeit 고급 스프린트 최종 프로젝트로 개발된 AI 기반 광고 제작 웹 애플리케이션입니다.

## 📄 프로젝트 보고서

이 프로젝트의 상세한 보고서를 확인하실 수 있습니다:

**[📋 Final AI Project 보고서 보기](Final-AI-Project-Report.pdf)**

> 📊 **보고서 내용**: 프로젝트 개요, 기술적 구현, 실험 결과, 성능 분석, 향후 계획 등이 포함된 상세한 문서입니다.

### 보고서 주요 섹션:
- 🎯 **프로젝트 목표 및 개요**
- 🛠 **기술적 구현 방법**
- 📈 **실험 결과 및 성능 분석**
- 🔍 **문제 해결 과정**
- 🚀 **향후 개선 계획**
- 📚 **참고 문헌**

## ✨ 주요 기능

- **자연어 기반 광고 제작**: 텍스트 입력만으로 전문적인 광고 콘텐츠 생성
- **다중 AI 모델 지원**: OpenAI GPT와 Google Gemini API 통합
- **실시간 미리보기**: 생성된 광고 콘텐츠를 즉시 확인
- **파일 업로드**: 이미지, 영상 등 다양한 미디어 파일 지원
- **Streamlit 대시보드**: 직관적인 웹 인터페이스
- **반응형 디자인**: 모바일과 데스크톱 모두 최적화

## 🚀 빠른 시작

### 1. 저장소 클론
```bash
git clone https://github.com/dlsndnwls116/final-ai-project.git
cd final-ai-project
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정
`.env` 파일을 생성하고 API 키를 설정하세요:
```env
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. 애플리케이션 실행
```bash
# 메인 Streamlit 앱 실행
streamlit run app_modern.py --server.port 8501

# 또는 고급 기능이 포함된 앱 실행
streamlit run app/app_streamlit.py --server.port 8502
```

## 🛠 기술 스택

### Backend
- **Python 3.8+**: 메인 프로그래밍 언어
- **Streamlit**: 웹 애플리케이션 프레임워크
- **OpenAI API**: GPT 모델 연동
- **Google Gemini API**: Gemini 모델 연동
- **Pillow**: 이미지 처리

### Frontend
- **React 18**: 모던 UI 컴포넌트
- **Tailwind CSS**: 유틸리티 퍼스트 CSS
- **Vite**: 빠른 개발 서버
- **Lucide React**: 아이콘 라이브러리

## 📁 프로젝트 구조

```
final-ai-project/
├── app_modern.py              # 메인 Streamlit 앱 (Gemini 스타일 UI)
├── app/
│   ├── app_streamlit.py       # 고급 기능 Streamlit 앱
│   └── utils/                 # 유틸리티 함수들
├── services/                  # 비즈니스 로직
│   ├── brief_and_shots.py     # 광고 브리프 생성
│   ├── pipeline_oneclick.py   # 원클릭 파이프라인
│   └── video_generation.py    # 영상 생성 서비스
├── utils/                     # 공통 유틸리티
├── prompts/                   # AI 프롬프트 템플릿
├── assets/                    # 정적 자산
├── outputs/                   # 생성된 결과물
├── requirements.txt           # Python 의존성
├── package.json              # Node.js 의존성
└── README.md                 # 프로젝트 문서
```

## 🎯 사용 방법

### 1. 기본 사용법
1. 웹 브라우저에서 `http://localhost:8501` 접속
2. 중앙의 입력창에 광고 아이디어 입력
3. 필요한 경우 파일 업로드
4. "생성하기" 버튼 클릭
5. 생성된 결과 확인

### 2. 고급 기능
- **브리프 생성**: 자동으로 광고 브리프 작성
- **샷 리스트**: 영상 촬영 계획 자동 생성
- **스타일 가이드**: 브랜드 일관성 유지
- **원클릭 제작**: 전체 파이프라인 자동 실행

## 🔧 환경 설정

### API 키 발급
1. **OpenAI API**: [platform.openai.com](https://platform.openai.com)에서 발급
2. **Google Gemini API**: [makersuite.google.com](https://makersuite.google.com)에서 발급

### 환경 변수 설정
```bash
# .env 파일 생성
touch .env

# API 키 추가
echo "OPENAI_API_KEY=your_key_here" >> .env
echo "GEMINI_API_KEY=your_key_here" >> .env
```

## 🚀 배포

### Streamlit Cloud 배포
1. GitHub에 코드 푸시
2. [share.streamlit.io](https://share.streamlit.io)에서 배포
3. 환경 변수 설정 후 배포 완료

### 로컬 배포
```bash
# 프로덕션 모드로 실행
streamlit run app_modern.py --server.port 8501 --server.headless true
```

## 📊 성능 최적화

- **캐싱**: Streamlit 캐시 데코레이터 활용
- **비동기 처리**: 대용량 파일 처리 시 비동기 방식 적용
- **메모리 관리**: 대용량 모델 로딩 최적화

## 🤝 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 🆘 문제 해결

### 일반적인 문제
- **API 키 오류**: `.env` 파일의 API 키 확인
- **포트 충돌**: 다른 포트 번호 사용 (`--server.port 8502`)
- **메모리 부족**: 대용량 모델 사용 시 RAM 확인

### 로그 확인
```bash
# Streamlit 로그 확인
streamlit run app_modern.py --logger.level debug
```

## 📞 지원

문제가 있으시면 다음 방법으로 연락해주세요:
- GitHub Issues 생성
- 이메일: your-email@example.com

---

💡 **팁**: 더 나은 결과를 위해 구체적인 제품 설명과 참고 이미지를 제공해보세요!