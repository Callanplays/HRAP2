@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Build HRAP Windows exe

set "PYTHON="
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PYTHON if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe" set "PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe"
if not defined PYTHON if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not defined PYTHON (
  where python >nul 2>&1
  if not errorlevel 1 for /f "usebackq delims=" %%I in (`where python`) do (
    if not defined PYTHON set "PYTHON=%%I"
  )
)

if not defined PYTHON (
  echo Python 3.10+ was not found.
  pause
  exit /b 1
)

echo Installing build dependencies...
"%PYTHON%" -m pip install -e ".[build]"
if errorlevel 1 goto :fail

echo Building versioned Windows zip...
"%PYTHON%" packaging\build_windows.py
if errorlevel 1 goto :fail

echo.
echo Done. Zip is in dist\
dir /b dist\HRAP-HCAT-Fork-*-windows.zip
echo.
pause
exit /b 0

:fail
echo Build failed.
pause
exit /b 1
