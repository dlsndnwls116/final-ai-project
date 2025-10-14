@echo off
echo 🔍 코드 품질 상태 점검...

echo.
echo 📁 현재 위치 및 설정 파일 확인:
echo 현재 디렉토리: %CD%
if exist pyproject.toml (
    echo ✅ pyproject.toml 존재
) else (
    echo ❌ pyproject.toml 없음 - 프로젝트 루트에서 실행하세요
)

echo.
echo 🔍 린트 상태만 확인 (수정하지 않음):
python -m ruff check . --check --force-exclude

echo.
echo 📊 포맷팅 상태 확인 (수정하지 않음):
python -m ruff format . --check --force-exclude

echo.
echo 🎯 핵심 폴더만 빠른 점검:
python -m ruff check app services utils --check --force-exclude

echo.
echo ✅ 상태 점검 완료!
pause
