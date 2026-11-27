@echo off
rem Double-click to set up and test VIctory-RDNA with Kalaga, start to finish.
rem Safe to run again: finished steps are skipped or quick. See docs\first-night.md.
setlocal EnableExtensions
cd /d "%~dp0"
title Kalaga

rem --- Python 3.11 or newer -------------------------------------------------
set "PY="
where py >nul 2>nul && py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Python 3.11 or newer was not found.
    echo Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^), then run this again.
    goto :end
)

rem --- git -------------------------------------------------------------------
where git >nul 2>nul
if errorlevel 1 (
    echo git was not found. Install Git for Windows from https://git-scm.com/download/win, then run this again.
    goto :end
)

rem --- kalaga.toml -------------------------------------------------------------
if not exist kalaga.toml (
    copy /y kalaga.example.toml kalaga.toml >nul
    echo Made kalaga.toml from the example. Notepad opens it now:
    echo   set [game] dir to your GTA VI dump folder and check the [runtime] paths,
    echo   save, close Notepad, and this carries on.
    start /wait notepad kalaga.toml
)

rem --- where VIctory-RDNA goes ----------------------------------------------------
rem The old victory-fork at D:\VIctory is left alone: RDNA gets its own folder.
set "RDNA_DIR="
for /f "usebackq delims=" %%P in (`%PY% -c "import tomllib; d=tomllib.load(open('kalaga.toml','rb')).get('runtime',{}).get('victory_dir',''); print(d if 'rdna' in d.lower() else '')"`) do set "RDNA_DIR=%%P"
if not defined RDNA_DIR (
    set "RDNA_DIR=D:\VIctory-RDNA"
    set /p "RDNA_DIR=Folder for VIctory-RDNA [D:\VIctory-RDNA]: "
)

echo.
echo Kalaga: update, patch, build, first run, prepare shaders, test session.
echo VIctory-RDNA folder: %RDNA_DIR%
echo Ctrl+C stops at any time; run this file again to carry on.
echo.

%PY% -m kalaga home --checkout rdna --runtime-dir "%RDNA_DIR%" %*
if errorlevel 1 (
    echo.
    echo Something stopped the run. The message above says what.
    echo Make a bug report for it with:  Report-Bug.bat
)

:end
echo.
pause
endlocal
