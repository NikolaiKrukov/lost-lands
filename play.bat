@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY="
if exist "%USERPROFILE%\miniconda3\pythonw.exe" set "PY=%USERPROFILE%\miniconda3\pythonw.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\pythonw.exe" set "PY=%USERPROFILE%\anaconda3\pythonw.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY (
  for /f "delims=" %%I in ('where pythonw 2^>nul') do (
    set "PY=%%I"
    goto :run
  )
)
if not defined PY (
  for /f "delims=" %%I in ('where python 2^>nul') do (
    set "PY=%%I"
    goto :run
  )
)

if not defined PY (
  echo Python not found. Install Miniconda or add python to PATH.
  pause
  exit /b 1
)

:run
start "" /D "%~dp0." "%PY%" -m src %*
