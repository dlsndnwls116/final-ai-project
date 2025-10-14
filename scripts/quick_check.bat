@echo off
echo ⚡ 빠른 소스 코드 검사...

echo.
echo 🔍 핵심 폴더만 검사 (app, services, utils)
python -m ruff check app services utils --fix --force-exclude
python -m ruff format app services utils --force-exclude

echo.
echo ✅ 빠른 검사 완료!
pause
