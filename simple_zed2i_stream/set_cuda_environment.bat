@echo off
echo ==========================================
echo    CUDA Environment Switcher
echo ==========================================
echo.
echo Current CUDA versions detected:
if exist "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0" (
    echo   ✅ CUDA 13.0 - Your primary installation
)
if exist "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6" (
    echo   ✅ CUDA 12.6 - For ZED SDK compatibility
) else (
    echo   ❌ CUDA 12.6 - Not installed yet
)
echo.
echo Select CUDA version for this session:
echo 1. CUDA 13.0 (Default - for other applications)
echo 2. CUDA 12.6 (For ZED SDK)
echo 3. Show current CUDA version
echo 4. Exit
echo.
set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" (
    echo.
    echo Setting environment for CUDA 13.0...
    set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0"
    set "PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin;%PATH%"
    echo ✅ CUDA 13.0 environment set for this session
    echo.
    nvcc --version
) else if "%choice%"=="2" (
    echo.
    echo Setting environment for CUDA 12.6...
    set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6"
    set "PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin;%PATH%"
    echo ✅ CUDA 12.6 environment set for this session
    echo.
    nvcc --version
) else if "%choice%"=="3" (
    echo.
    echo Current CUDA version:
    nvcc --version
) else if "%choice%"=="4" (
    echo Goodbye!
    exit /b 0
) else (
    echo Invalid choice. Please try again.
    pause
    goto :eof
)

echo.
echo ==========================================
echo Environment set! You can now run:
echo   python zed2i_stream_server.py
echo ==========================================
pause
