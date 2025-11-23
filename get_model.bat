@echo off
setlocal

set "SCRIPTROOT=%~dp0"
set "PYTHON_BIN=%SCRIPTROOT%python\python.exe"

echo Downloading DeepSeek-OCR (BF16)...
"%PYTHON_BIN%" "%SCRIPTROOT%get_model.py"
pause

endlocal