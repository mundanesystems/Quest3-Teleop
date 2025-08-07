# ZED2i Streaming Server

This folder contains a streaming server for the ZED2i stereo camera that maintains compatibility with the existing Unity VR video receiver.

## Setup Requirements

### 1. Install ZED SDK
1. Download the ZED SDK from: https://www.stereolabs.com/developers/release/
2. Install the ZED SDK (includes CUDA runtime if needed)
3. The SDK includes the Python API (pyzed)

### 2. Install Python Dependencies
```bash
pip install opencv-python numpy
```

### 3. Verify ZED2i Camera Connection
- Connect your ZED2i camera via USB 3.0
- Run ZED Depth Viewer or ZED Explorer to verify the camera is detected

## Usage

### Basic Usage (Same as RealSense)
```bash
cd simple_zed2i_stream
python zed2i_stream_server.py
```

### Custom Configuration
```bash
python zed2i_stream_server.py --host 192.168.0.196 --port 8080 --ping-port 8081
```

## Switching Between Cameras

**For RealSense:**
```bash
cd simple_realsense_demo
python realsense_stream_server.py
```

**For ZED2i:**
```bash
cd simple_zed2i_stream
python zed2i_stream_server.py
```

The Unity code requires **no changes** - both servers use identical network protocols:
- TCP port 8080 for video stream
- UDP port 8081 for latency measurement
- Same image encoding (JPEG)
- Same packet structure

## Features

✅ **720p @ 30fps streaming** (higher resolution than RealSense 640x480)
✅ **Identical network protocol** - no Unity changes needed
✅ **Built-in latency measurement** via UDP ping
✅ **Automatic client reconnection**
✅ **Same command-line arguments** as RealSense server

## Camera Specifications

| Feature | RealSense D435 | ZED2i |
|---------|----------------|-------|
| Resolution | 640x480 | 1280x720 |
| Frame Rate | 30 FPS | 30 FPS |
| Field of View | 69° × 42° | 110° × 70° |
| Depth | Yes | Yes (better quality) |
| IMU | No | Yes |
| SDK | pyrealsense2 | pyzed |

## Troubleshooting

**Camera not detected:**
- Ensure ZED2i is connected to USB 3.0 port
- Run ZED Depth Viewer to test camera
- Check if another application is using the camera

**Import errors:**
- Verify ZED SDK is installed
- Check that `pip install opencv-python numpy` completed successfully

**Network issues:**
- Same troubleshooting as RealSense server
- Ensure firewall allows connections on ports 8080/8081
