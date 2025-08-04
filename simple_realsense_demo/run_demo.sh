#!/bin/bash

echo "🎯 Intel RealSense D435 - Simple Point Cloud Demo"
echo "================================================"
echo ""

# Check if setup has been run
if [ ! -f "requirements.txt" ]; then
    echo "❌ Setup files not found!"
    echo "   Please make sure you're in the simple_realsense_demo directory"
    exit 1
fi

# Check if RealSense device is connected
echo "🔍 Checking for RealSense device..."
if ! rs-enumerate-devices | grep -q "Intel RealSense"; then
    echo "⚠️  No Intel RealSense device detected!"
    echo ""
    echo "📋 Troubleshooting:"
    echo "   1. Connect your Intel RealSense D435 via USB 3.0+ port"
    echo "   2. Try a different USB port or cable"  
    echo "   3. Run: rs-enumerate-devices (to verify detection)"
    echo "   4. Check permissions: sudo chmod 666 /dev/video*"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ Intel RealSense device found"
fi

echo ""
echo "🚀 Starting iPhone Record3D style point cloud streaming..."
echo ""
echo "🎮 Controls:"
echo "   ESC/Q  - Quit"
echo "   R      - Reset view"
echo "   Mouse  - Rotate, pan, zoom 3D view"
echo ""
echo "💡 Tips:"
echo "   - Move the camera slowly for best results"
echo "   - Ensure good lighting"
echo "   - Stay within 0.3m - 2.0m range"
echo ""

# Run the demo
python3 simple_realsense_streaming.py
