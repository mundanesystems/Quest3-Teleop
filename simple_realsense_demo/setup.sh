#!/bin/bash

echo "🎯 Intel RealSense D435 Simple Demo Setup"
echo "=========================================="
echo ""

# Check if RealSense SDK is installed
if ! command -v rs-enumerate-devices &> /dev/null; then
    echo "❌ Intel RealSense SDK not found!"
    echo ""
    echo "📦 Please install Intel RealSense SDK 2.0 first:"
    echo "   Ubuntu/Debian: https://github.com/IntelRealSense/librealsense/blob/master/doc/distribution_linux.md"
    echo "   Windows: https://github.com/IntelRealSense/librealsense/releases"
    echo "   macOS: brew install librealsense"
    exit 1
fi

echo "✅ Intel RealSense SDK found"

# Check for connected devices
echo "🔍 Checking for RealSense devices..."
if rs-enumerate-devices | grep -q "Intel RealSense"; then
    echo "✅ Intel RealSense device detected:"
    rs-enumerate-devices | grep -A 1 "Device info:"
else
    echo "⚠️  No RealSense device detected"
    echo "   Make sure your Intel RealSense D435 is connected via USB 3.0"
    echo "   You can still install dependencies and try again later"
fi

echo ""
echo "📦 Installing Python dependencies..."

# Install required packages
pip install --user -r requirements.txt

echo ""
echo "🧪 Testing imports..."

# Test if all packages can be imported
python3 -c "
import sys
try:
    import pyrealsense2 as rs
    print('✅ pyrealsense2')
except ImportError as e:
    print(f'❌ pyrealsense2: {e}')
    sys.exit(1)

try:
    import cv2
    print('✅ opencv-python')
except ImportError as e:
    print(f'❌ opencv-python: {e}')
    sys.exit(1)

try:
    import open3d as o3d
    print('✅ open3d')
except ImportError as e:
    print(f'❌ open3d: {e}')
    sys.exit(1)

try:
    import numpy as np
    print('✅ numpy')
except ImportError as e:
    print(f'❌ numpy: {e}')
    sys.exit(1)

print('')
print('🎉 All dependencies installed successfully!')
"

if [ $? -eq 0 ]; then
    echo ""
    echo "🚀 Setup complete! Ready to run:"
    echo "   python3 simple_realsense_streaming.py"
    echo ""
    echo "   OR use the launcher:"
    echo "   ./run_demo.sh"
else
    echo ""
    echo "❌ Some dependencies failed to install"
    echo "   Try: pip install --upgrade pip"
    echo "   Then run this script again"
fi
