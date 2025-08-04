# MundaneNeck - Quest 3 Gyroscope & RealSense Integration

A Unity VR project that integrates Meta Quest 3 gyroscope data with Intel RealSense D435 camera streaming and Dynamixel robot control.

## 🎯 Features

- **Quest 3 Gyroscope Tracking**: Real-time head movement tracking
- **RealSense Camera Streaming**: Live video and point cloud streaming
- **Robot Control**: Dynamixel servo control based on head movements
- **VR Integration**: Full Unity VR experience with Oculus SDK

## 🚀 Components

### Unity Project (`Assets/`)
- `GyroscopeReader.cs` - Captures Quest 3 gyroscope data and sends via UDP
- `VideoStreamReceiver.cs` - Receives video stream from RealSense camera
- `PointCloudReceiver.cs` - Receives and renders 3D point cloud data
- `EfficientPointCloudReceiver.cs` - Optimized point cloud rendering

### Python Scripts (`dynamixel/`)
- `Television_Quest_Sync.py` - Main robot control script
- `dynamixel_robot.py` - Robot interface and control
- `driver.py` - Low-level Dynamixel communication
- `test_udp_listener.py` - Network debugging utility

### RealSense Streaming (`simple_realsense_demo/`)
- `realsense_stream_server.py` - Basic video streaming server
- `realsense_pointcloud_server.py` - 3D point cloud streaming server
- `simple_realsense_streaming_robust.py` - High-performance streaming with profiling

## 🔧 Setup

### Requirements
- Meta Quest 3 VR headset
- Intel RealSense D435 camera
- Dynamixel servo motors
- Unity 2022.3+ with Oculus SDK
- Python 3.8+ with dependencies

### Python Dependencies
```bash
pip install pyrealsense2 opencv-python open3d numpy numba
```

### Network Configuration
- Ensure Quest 3 and PC are on the same Wi-Fi network
- Default IP: `192.168.0.196` (update in Unity scripts if different)
- Ports: `8080` (video), `8081` (point cloud), `9050` (gyroscope)

## 🎮 Usage

1. **Start Robot Control**:
   ```bash
   cd dynamixel
   python Television_Quest_Sync.py
   ```

2. **Start Camera Streaming**:
   ```bash
   cd simple_realsense_demo
   python realsense_stream_server.py
   # or for point clouds:
   python realsense_pointcloud_server.py
   ```

3. **Deploy Unity App** to Quest 3 and run

## 🔗 System Architecture

```
Quest 3 ──UDP──→ PC ──Serial──→ Dynamixel Robot
   ↓                ↓
Unity VR ←──TCP──→ RealSense Camera
```

- Quest 3 sends gyroscope data to PC via UDP
- PC processes data and controls robot servos
- RealSense camera streams video/point clouds to Unity
- Unity displays immersive view with robot control

## 📊 Performance

- **Video Streaming**: 30 FPS @ 640x480
- **Point Cloud**: 15,000+ points @ 30 FPS
- **Gyroscope**: 20 Hz update rate
- **Robot Control**: Real-time servo positioning

## 🛠️ Development

Built with:
- Unity 2022.3 LTS
- Oculus Integration SDK
- Intel RealSense SDK 2.0
- Dynamixel SDK
- Python 3.8+

## 📝 License

This project is part of the MundaneNeck system for VR-controlled robotics.
