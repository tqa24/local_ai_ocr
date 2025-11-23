@echo off
setlocal

set "SCRIPTROOT=%~dp0"
set "PYTHON_BIN=%SCRIPTROOT%python\python.exe"

:: Force CPU-Only & hide GPU from PyTorch
set "FORCE_CPU=1"
set "CUDA_VISIBLE_DEVICES=-1"

echo Starting Local AI OCR (CPU-Only)...
"%PYTHON_BIN%" "%SCRIPTROOT%src\main.py"

endlocal