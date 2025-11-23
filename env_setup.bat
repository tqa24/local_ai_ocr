@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: CONFIGURATION
:: ============================================================
set "PYTHON_VER=3.13.9"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/python-%PYTHON_VER%-embed-amd64.zip"
set "PIP_URL=https://bootstrap.pypa.io/get-pip.py"

set "SCRIPTROOT=%~dp0"
set "PYTHON_DIR=%SCRIPTROOT%python"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "PTH_FILE=%PYTHON_DIR%\python313._pth"

:: ============================================================
:: 1. CHECK & INSTALL PYTHON
:: ============================================================
echo [1/5] Checking Python environment...

if exist "%PYTHON_EXE%" (
    echo - Python found in %PYTHON_DIR%. Skipping download.
) else (
    echo - Python missing or incomplete. Starting download...

    :: Clean up partial downloads from previous failed runs
    if exist "python.zip" (
        echo - Found leftover python.zip. Deleting to ensure fresh download...
        del "python.zip"
    )

    echo - Downloading Python %PYTHON_VER% Embeddable...
    powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile 'python.zip'"
    if !errorlevel! neq 0 goto :ERROR_NETWORK

    echo - Extracting to %PYTHON_DIR%...
    powershell -ExecutionPolicy Bypass -Command "Expand-Archive -Path 'python.zip' -DestinationPath '%PYTHON_DIR%' -Force"
    if !errorlevel! neq 0 goto :ERROR_EXTRACT

    echo - Cleaning up zip file...
    del python.zip
)

:: Double check that extraction actually worked
if not exist "%PYTHON_EXE%" goto :ERROR_EXTRACT

:: ============================================================
:: 2. CONFIGURE ._pth FILE
:: ============================================================
echo [2/5] Configuring python313._pth...
:: This is safe to run repeatedly; it simply replaces the string if found.
powershell -ExecutionPolicy Bypass -Command "(Get-Content '%PTH_FILE%') -replace '#import site', 'import site' | Set-Content '%PTH_FILE%'"

:: ============================================================
:: 3. INSTALL PIP
:: ============================================================
echo [3/5] Checking for pip...

if exist "%PYTHON_DIR%\Scripts\pip.exe" (
    echo - pip found. Skipping.
) else (
    echo - pip not found.

    :: Clean up partial get-pip.py
    if exist "get-pip.py" del "get-pip.py"

    echo - Downloading get-pip.py...
    powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PIP_URL%' -OutFile 'get-pip.py'"
    if !errorlevel! neq 0 goto :ERROR_NETWORK

    echo - Installing pip...
    "%PYTHON_EXE%" get-pip.py --no-warn-script-location
    if !errorlevel! neq 0 goto :ERROR_PIP

    del "get-pip.py"
)

:: ============================================================
:: 4. INSTALL REQUIREMENTS
:: ============================================================
echo [4/5] Installing requirements...
:: Pip handles partially installed packages automatically (idempotent).
if exist "%SCRIPTROOT%requirements.txt" (
    "%PYTHON_EXE%" -m pip install -r "%SCRIPTROOT%requirements.txt" --no-warn-script-location
    if !errorlevel! neq 0 goto :ERROR_PIP
) else (
    echo [ERROR] requirements.txt not found!
    goto :ERROR
)

:: ============================================================
:: 5. DOWNLOAD MODEL
:: ============================================================
echo [5/5] Checking for DeepSeek-OCR Model...
:: The Hugging Face library (snapshot_download) inside get_model.py handles 
:: SHA256 verification and resuming automatically.

if exist "%SCRIPTROOT%get_model.py" (
    "%PYTHON_EXE%" "%SCRIPTROOT%get_model.py"
    if !errorlevel! neq 0 goto :ERROR_MODEL
) else (
    echo [ERROR] get_model.py not found!
    goto :ERROR
)

pause
exit /b 0

:: ============================================================
:: ERROR HANDLERS
:: ============================================================
:ERROR_NETWORK
echo.
echo [FATAL ERROR] Network request failed.
echo Please check your internet connection and try again.
pause
exit /b 1

:ERROR_EXTRACT
echo.
echo [FATAL ERROR] Failed to extract Python.
echo The downloaded zip might be corrupt. 
echo The script will delete it automatically on the next run.
pause
exit /b 1

:ERROR_PIP
echo.
echo [FATAL ERROR] Pip installation or Package install failed.
pause
exit /b 1

:ERROR_MODEL
echo.
echo [FATAL ERROR] Model download failed.
echo You can resume the download by running 'get_model.bat' directly.
pause
exit /b 1

:ERROR
echo.
echo [FATAL ERROR] An unexpected error occurred.
pause
exit /b 1