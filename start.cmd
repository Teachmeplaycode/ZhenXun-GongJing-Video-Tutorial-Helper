@echo off
chcp 65001 >nul 2>&1
setlocal
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto try_python
py -3.12 -c "import sys; sys.exit(sys.version_info < (3,12))" >nul 2>&1
if errorlevel 1 goto try_python
py -3.12 "%~dp0start.py" %*
goto finished
:try_python
for %%e in (python python3) do (
    %%e -c "import sys; sys.exit(sys.version_info < (3,12))" >nul 2>&1
    if not errorlevel 1 (
        %%e "%~dp0start.py" %*
        goto finished
    )
)
echo 请安装 Python 3.12，并勾选 Add Python to PATH
echo https://www.python.org/downloads/
if /i "%~1"=="--check" exit /b 1
pause
exit /b 1
:finished
set "EXITCODE=%ERRORLEVEL%"
if /i "%~1"=="--check" exit /b %EXITCODE%
if not "%EXITCODE%"=="0" pause
exit /b %EXITCODE%
