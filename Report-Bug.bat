@echo off
rem Double-click right after something looks wrong (black textures, blur, a crash).
rem Zips the newest logs, preset, runtime build and frame stats into logs\bug-<time>.zip.
setlocal EnableExtensions
cd /d "%~dp0"
title Kalaga bug report
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY set "PY=python"
echo What did you see, and where? One line, then Enter (or just Enter to skip):
set "WHAT="
set /p "WHAT=> "
%PY% -m kalaga bug "%WHAT%"
echo.
echo Send the logs\bug-....zip named above.
explorer "%~dp0logs"
pause
endlocal
