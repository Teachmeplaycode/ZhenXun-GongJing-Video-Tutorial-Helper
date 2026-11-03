@echo off
chcp 65001 >nul 2>&1
setlocal

REM ── Find Python ──────────────────────────────────────────────────────
set "PY="
for %%e in (python3 python) do (
    where %%e >nul 2>&1 && (
        for /f "delims=" %%p in ('where %%e') do (
            if not defined PY set "PY=%%p"
        )
    )
)
if not defined PY (
    echo.
    echo   没有找到 Python。请安装 Python 3.12+：
    echo     https://www.python.org/downloads/
    echo   安装时勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

REM ── Run the launcher ─────────────────────────────────────────────────
cd /d "%~dp0"
"%PY%" "%~dp0start.py" %*
set EXITCODE=%ERRORLEVEL%

if not "%1"=="--check" (
    if not "%EXITCODE%"=="0" (
        echo.
        pause
    )
)
exit /b %EXITCODE%
