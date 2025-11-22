@echo off
setlocal

set "SCRIPTROOT=%~dp0"
set "PYTHON_BIN=%SCRIPTROOT%python\python.exe"
set "OLLAMA_BIN=%SCRIPTROOT%ollama\ollama.exe"

:: Avoid port conflict
set "OLLAMA_HOST=http://127.0.0.1:11435"
set "OLLAMA_MODELS=%SCRIPTROOT%models"

echo Starting Ollama...
start /B "" "%OLLAMA_BIN%" serve >nul 2>&1
timeout /t 3 /nobreak >nul

echo Removing deepseek-ocr:3b (fp16)...
"%OLLAMA_BIN%" rm deepseek-ocr:3b

echo Stopping Ollama...
taskkill /F /IM ollama.exe >nul 2>&1

endlocal
