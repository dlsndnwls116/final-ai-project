# make_plan.py 사용법

## 개요
GPT와 Gemini를 모두 지원하는 숏폼 광고 계획 생성 스크립트입니다.

## 설치
```bash
pip install python-dotenv openai google-generativeai
```

## 환경 설정
`.env` 파일에 API 키를 설정:
```
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here
```

## 사용법

### 기본 사용
```bash
python make_plan.py
```

### 엔진 선택
```bash
# GPT 사용
python make_plan.py --engine gpt

# Gemini 사용  
python make_plan.py --engine gemini

# 자동 선택 (GPT 우선, 없으면 Gemini)
python make_plan.py --engine auto
```

### 커스텀 파라미터
```bash
python make_plan.py \
  --ref "빠른 템포로 도시·건물 공간 스냅컷 → 마지막 3초 제품 클로즈업" \
  --product "매트 블랙 무선 이어버즈, 저지연/하이브리드 ANC, 메탈릭 포인트" \
  --tone "미니멀, 프리미엄, 하이컨트라스트" \
  --avoid "귀여움, 파스텔, 저해상도, 과한 보케" \
  --outdir "my_project"
```

## 출력 파일
- `storyboard.json`: 전체 계획 (JSON)
- `prompts_midjourney.txt`: 미드저니 프롬프트 목록
- `captions.srt`: 자막 파일 (SRT 형식)
- `editlist.txt`: 편집 리스트

## 출력 예시
```
▶ 엔진: gpt
✅ 완료: out/storyboard.json, prompts_midjourney.txt, captions.srt, editlist.txt
```
