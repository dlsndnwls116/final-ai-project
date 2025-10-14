# 코드 품질 관리 가이드

## 🔧 일상 명령어

### 전체 검사 및 자동 수정
```bash
# 1) 전파일 자동 수정
python -m ruff check . --fix --force-exclude
python -m ruff format . --force-exclude

# 2) 타입 점검
python -m mypy .
```

### 빠른 검사 (핵심 폴더만)
```bash
python -m ruff check app services utils --fix --force-exclude
python -m ruff format app services utils --force-exclude
```

### 상태 확인만 (수정하지 않음)
```bash
python -m ruff check . --check --force-exclude
python -m ruff format . --check --force-exclude
```

## 🎯 자주 나는 에러 & 해결법

### Ruff가 자주 잡는 것
- **F401** 미사용 임포트 → 자동 제거됨
- **F841** 사용하지 않는 변수 → `_`로 변경하거나 제거
- **E501** 라인 길이 초과 (100자) → 자동 포맷팅
- **UP** pyupgrade → `typing.Tuple` → `tuple[...]` 현대화

### 특수 케이스 무시
```python
sys.path.insert(0, ROOT)  # noqa: E402
```

### mypy 타입 힌트 예시
```python
from __future__ import annotations
from typing import Any

def process_assets(assets: dict[str, str]) -> dict[str, Any]:
    ...

session: dict[str, Any] = st.session_state
```

## 🔍 품질 체크리스트

- [ ] `ruff check . --fix` 후 다시 `ruff check .`에서 0 문제
- [ ] `ruff format .` 실행 후 변경 없음  
- [ ] `mypy .` 주요 경고 0개 (또는 무시 가능한 1-2개)
- [ ] VS Code에서 저장 시 자동 포맷팅 동작
- [ ] Git 커밋 시 pre-commit 훅 정상 동작

## 🚨 문제 해결

### 실행 안 될 때
```bash
# 현재 위치 확인 (pyproject.toml 있어야 함)
dir pyproject.toml

# 강제 제외 옵션 사용
python -m ruff check . --force-exclude

# 스코프 축소
python -m ruff check app services utils --fix
```

### PowerShell 인코딩 설정
```powershell
$env:PYTHONIOENCODING = "utf-8"
```

## 🎨 VS Code 연동

1. Ruff 확장 설치
2. 설정에서 "Format on Save" 활성화  
3. `.vscode/settings.json` 자동 적용됨

이제 코드 저장만 해도 자동으로 품질 관리가 됩니다!
