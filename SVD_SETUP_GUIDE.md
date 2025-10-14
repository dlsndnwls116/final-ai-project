# 🎬 SVD (Stable Video Diffusion) 설정 가이드

## 1. Hugging Face 토큰 발급

1. **Hugging Face 계정 생성**: https://huggingface.co/join
2. **SVD 모델 접근 신청**: 
   - https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt-1-1 방문
   - "Request access" 버튼 클릭
   - 사용 목적 작성 후 신청
3. **토큰 생성**:
   - https://huggingface.co/settings/tokens 방문
   - "New token" 클릭
   - Name: `SVD-API-Key`
   - Type: `Read` 선택
   - "Generate a token" 클릭
   - 생성된 토큰 복사 (hf_로 시작)

## 2. 환경변수 설정

### 방법 1: .env 파일 (권장)
```bash
# .env 파일에 추가
HUGGINGFACE_HUB_TOKEN=hf_XXXXXXXXXXXXXXXXXXXXXXXX
```

### 방법 2: PowerShell 환경변수
```powershell
$env:HUGGINGFACE_HUB_TOKEN="hf_XXXXXXXXXXXXXXXXXXXXXXXX"
```

### 방법 3: 시스템 환경변수 (영구)
```powershell
setx HUGGINGFACE_HUB_TOKEN "hf_XXXXXXXXXXXXXXXXXXXXXXXX"
```

## 3. 테스트 실행

```bash
# 1. 테스트 이미지 생성
python tools/create_test_image.py

# 2. SVD 테스트 실행
python tools/svd_make.py --image outputs/test_images/test_product.jpg --frames 25 --portrait

# 3. Streamlit에서 테스트
streamlit run app/app_streamlit.py
```

## 4. 시스템 요구사항

- **GPU**: RTX 5070 12GB ✅ (현재 시스템)
- **CUDA**: 13.0 ✅ (설치됨)
- **VRAM**: 최소 8GB, 권장 12GB+ ✅
- **Python**: 3.10+ ✅

## 5. 문제 해결

### 토큰 오류 (401 Unauthorized)
```
huggingface_hub.errors.GatedRepoError: 401 Client Error
```
**해결**: Hugging Face 토큰 설정 및 모델 접근 권한 확인

### CUDA 메모리 부족
```
torch.cuda.OutOfMemoryError
```
**해결**: 
- `num_frames` 줄이기 (25 → 15)
- `decode_chunk_size` 줄이기 (8 → 4)
- 다른 GPU 프로세스 종료

### 모델 다운로드 실패
```
ConnectionError: Failed to download
```
**해결**: 
- 인터넷 연결 확인
- Hugging Face 서버 상태 확인
- 토큰 권한 확인

## 6. 사용법

### CLI 사용
```bash
python tools/svd_make.py \
  --image "제품이미지.jpg" \
  --frames 25 \
  --portrait \
  --out "output.mp4"
```

### Streamlit UI 사용
1. D1: 환경 체크 (SVD 상태 확인)
2. D2: 제품 이미지 업로드
3. "🤖 AI 영상 생성 (SVD)" 버튼 클릭
4. D4: 결과 미리보기

## 7. 성능 최적화

### 빠른 테스트
```bash
python tools/svd_make.py --image test.jpg --frames 15 --fps 15
```

### 고품질 생성
```bash
python tools/svd_make.py --image test.jpg --frames 50 --fps 25
```

### 메모리 절약
```bash
python tools/svd_make.py --image test.jpg --frames 25 --portrait
```

---

**⚠️ 중요**: SVD 모델은 Stability AI의 gated repository입니다. 반드시 Hugging Face에서 접근 권한을 신청하고 토큰을 설정해야 합니다.
