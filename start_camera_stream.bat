@echo off
echo ================================================
echo        Camera Streaming Server Launcher
echo ================================================
echo.
echo Select which camera to stream:
echo 1. Intel RealSense D435
echo 2. ZED2i Stereo Camera (ZED SDK - requires CUDA 12.6)
echo 3. ZED2i Stereo Camera (OpenCV fallback - always works)
echo.
set /p choice="Enter your choice (1, 2, or 3): "

if "%choice%"=="1" (
    echo.
    echo 🚀 Starting RealSense streaming server...
    echo Press Ctrl+C to stop
    cd simple_realsense_demo
    python realsense_stream_server.py
) else if "%choice%"=="2" (
    echo.
    echo 🚀 Starting ZED2i streaming server (ZED SDK)...
    echo Note: Requires CUDA 12.6 installation
    echo Press Ctrl+C to stop
    cd simple_zed2i_stream
    python zed2i_stream_server.py
) else if "%choice%"=="3" (
    echo.
    echo 🚀 Starting ZED2i streaming server (OpenCV fallback)...
    echo Press Ctrl+C to stop
    cd simple_zed2i_stream
    python zed2i_stream_server_fallback.py
) else (
    echo Invalid choice. Please run the script again.
    pause
)
