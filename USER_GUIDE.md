# 🚀 make_plan.py 사용자 가이드

## 📋 현재 상태
- ✅ **conda 환경**: `adgen-svd` 활성화됨
- ✅ **API 키**: OpenAI와 GEMINI 모두 설정 완료
- ✅ **패키지**: 모든 필요한 패키지 설치 완료
- ✅ **스크립트**: make_plan.py 업데이트 완료

## 🎯 사용 방법

### **1단계: 기본 실행**
```bash
# GEMINI 사용 (권장)
python make_plan.py --provider gemini --prompt "30초 제품 릴스 콘셉트 3개"

# OpenAI 사용
python make_plan.py --provider openai --prompt "30초 제품 릴스 콘셉트 3개"

# 자동 선택 (OpenAI 우선, 실패 시 GEMINI)
python make_plan.py --provider auto --prompt "30초 제품 릴스 콘셉트 3개"
```

### **2단계: 커스터마이징**
```bash
# 제품 설명 변경
python make_plan.py --provider gemini --prompt "스마트워치 30초 광고 콘셉트 3개"

# 브랜드 톤 변경
python make_plan.py --provider gemini --product "프리미엄 헤드폰" --tone "럭셔리, 미니멀"

# 출력 디렉토리 변경
python make_plan.py --provider gemini --prompt "30초 제품 릴스 콘셉트" --outdir "my_project"
```

### **3단계: 출력 파일 확인**
실행 후 다음 파일들이 생성됩니다:
- `out/storyboard.json` - 전체 계획 (JSON)
- `out/prompts_midjourney.txt` - 미드저니 프롬프트
- `out/captions.srt` - 자막 파일
- `out/editlist.txt` - 편집 리스트

## 🔧 문제 해결

### **환경 변수 문제**
```bash
# 환경 변수 다시 로드
from dotenv import load_dotenv
import os
load_dotenv()
```

### **패키지 문제**
```bash
# 필요한 패키지 재설치
pip install python-dotenv openai google-generativeai
```

### **API 키 문제**
```bash
# .env 파일 확인
cat .env
```

## 📞 지원

문제가 발생하면:
1. 환경 변수 확인
2. 패키지 설치 상태 확인
3. API 키 유효성 확인
4. 오류 메시지 확인

## 🎉 성공!

모든 설정이 완료되었으니 바로 사용하실 수 있습니다!

```bash
python make_plan.py --provider gemini --prompt "30초 제품 릴스 콘셉트 3개"
```
