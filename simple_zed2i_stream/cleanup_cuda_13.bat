@echo off
echo ==========================================
echo     CUDA 13.0 Environment Cleanup
echo ==========================================
echo.
echo This script will remove CUDA 13.0 references from your environment
echo Press any key to continue or Ctrl+C to cancel...
pause > nul

echo.
echo 🧹 Cleaning up CUDA 13.0 environment variables...

REM Remove CUDA 13.0 from system PATH (requires admin rights)
echo.
echo Note: You may need to manually remove these from System Environment Variables:
echo   - C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin
echo   - C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\libnvvp
echo.
echo To do this manually:
echo 1. Right-click "This PC" → Properties → Advanced System Settings
echo 2. Click "Environment Variables"
echo 3. Edit "Path" in System variables
echo 4. Remove any entries containing "v13.0"
echo.

echo ✅ Manual cleanup steps provided above
echo.
echo After installing CUDA 12.6, your environment will be clean and simple!
pause
