@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

set "PY="
where py >nul 2>&1
if not errorlevel 1 (
  set "PY=py -3"
) else (
  where python >nul 2>&1
  if not errorlevel 1 set "PY=python"
)

if not defined PY (
  echo Python was not found on PATH.
  echo Install Python 3.10+ and check "Add python.exe to PATH", then try again.
  echo.
  pause
  exit /b 1
)

%PY% -c "import hrap, PySide6, pyqtgraph" >nul 2>&1
if errorlevel 1 (
  echo Installing HRAP (HCAT Fork) and GUI dependencies...
  %PY% -m pip install -e . || goto :fail
)

%PY% -m hrap
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo HRAP (HCAT Fork) failed to start.
echo From this folder you can also run:
echo   %PY% -m pip install -e .
echo   %PY% -m hrap
echo.
pause
exit /b 1
