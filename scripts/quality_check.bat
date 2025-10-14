@echo off
echo 🔍 코드 품질 검사 시작...

echo.
echo 1️⃣ 전체 린트 + 자동수정
python -m ruff check . --fix --show-fixes --force-exclude

echo.
echo 2️⃣ 포맷팅
python -m ruff format . --force-exclude

echo.
echo 3️⃣ 타입 검사 (선택적)
python -m mypy . 2>nul || echo "mypy 설치 필요: pip install mypy"

echo.
echo ✅ 코드 품질 검사 완료!
pause
