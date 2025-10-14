# 빠른 체크 커맨드 모음

## 진단 시스템 사용법

### 1) 전체 스윕 (정적/동적 진단)
```bash
python tools/dev_sweep.py
```
- 결과 요약: `logs/dev_sweep.json`
- Python 컴파일 검사, ruff, mypy, pytest, 스모크 렌더 포함

### 2) 코드 품질 개선
```bash
# ruff 자동 수정
python -m ruff check . --fix

# 타입 점검
mypy services app utils --ignore-missing-imports

# 린트 검사
python -m ruff check .
```

### 3) 스모크 렌더 테스트
```bash
python tools/smoke_render.py
```
- 1초 비디오 생성으로 렌더 파이프라인 검증
- 출력: `outputs/smoke/smoke.mp4`

### 4) 개별 모듈 테스트
```bash
# 진단 시스템 테스트
python -c "from utils.diagnostics import start_watchdog; start_watchdog(); print('✅ 진단 시스템 시작')"

# 핵심 모듈 import 테스트
python -c "from app.app_streamlit import ASSET_DIR; from services.render_engine import render_video; print('✅ 핵심 모듈 로드 성공')"
```

## 진단 시스템 모니터링

### 실시간 로그 확인
```bash
# Windows PowerShell
Get-Content logs/app.log -Wait -Tail 10

# Linux/Mac
tail -f logs/app.log
```

### 행업 감지 로그
- `logs/hang_타임스탬프.log`: 스레드 덤프
- `logs/dev_sweep.json`: 스윕 결과

### 환경변수 설정
```bash
# 엄격 모드 (타임아웃/과회전 시 즉시 예외)
set ADGEN_DEBUG=1

# 워치독 타임아웃 설정 (기본 90초)
set WATCHDOG_TIMEOUT=120
```

## 문제 해결 가이드

### Streamlit 재실행 루프
**증상**: Streamlit이 계속 새로고침
**원인**: top-level에서 session_state를 매번 갱신
**해결**: 상태 갱신을 버튼/콜백 내부로 이동

### 렌더링 중 멈춤
**증상**: 렌더 중 멈춤
**원인**: heartbeat 미호출, 외부 프로세스 대기
**해결**: `logs/hang_*.log` 스레드 덤프 확인, 루프에 `heartbeat("render")` 추가

### 무한 루프
**증상**: LoopGuard loop_progress 로그가 계속 증가
**원인**: 종료 조건 누락 / 인덱스 전진 X
**해결**: LoopGuard로 한도 초과 시 예외 발생시키고 위치 고정

### 회색/검은 화면
**증상**: 렌더링 결과가 회색/검은 화면
**원인**: 알파/레이어 순서/fit 문제
**해결**: 1분 미리보기(샷0), RGBA→mask 분리, base 첫 원소, fit:cover 강제

## 성능 최적화

### 외부 프로세스 타임아웃
```python
proc = subprocess.run(cmd, timeout=120, ...)
```

### MoviePy 자원 회수
```python
clip.close()  # Clip 객체 사용 후
```

### 파일 변경 감지 비활성화
```bash
streamlit run app/app_streamlit.py --server.fileWatcherType=none
```
