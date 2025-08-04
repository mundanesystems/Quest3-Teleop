# Intel RealSense D435 Simple Point Cloud Demo

A clean, standalone implementation of real-time point cloud streaming using the Intel RealSense D435 depth camera. This demo provides smooth, iPhone Record3D-style visualization.

## 🎯 Features

- **Smooth Real-time Streaming**: 25-30 FPS point cloud visualization
- **Clean Interface**: Single 3D window with intuitive mouse controls
- **iPhone Record3D Style**: Black background, clean point cloud rendering
- **Optimized Performance**: Smart filtering and downsampling
- **Easy Setup**: Standalone directory with all dependencies

## 📋 Requirements

### Hardware
- Intel RealSense D435 (or D415/D455) depth camera
- USB 3.0+ port for best performance
- Computer with decent graphics capability

### Software
- Ubuntu 18.04+ / Windows 10+ / macOS 10.14+
- Python 3.6+
- Intel RealSense SDK 2.0

## 🚀 Quick Start

### 1. Install Intel RealSense SDK

**Ubuntu/Debian:**
```bash
# Add Intel repository key
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-key F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE

# Add repository  
sudo add-apt-repository "deb https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main" -u

# Install SDK
sudo apt-get install librealsense2-dkms librealsense2-utils librealsense2-dev
```

**Windows:**
Download from: https://github.com/IntelRealSense/librealsense/releases

**macOS:**
```bash
brew install librealsense
```

### 2. Setup Demo

```bash
# Make setup script executable
chmod +x setup.sh

# Run setup
./setup.sh
```

### 3. Run Demo

```bash
# Make run script executable  
chmod +x run_demo.sh

# Start streaming
./run_demo.sh
```

**OR run directly:**
```bash
python3 simple_realsense_streaming.py
```

## 🎮 Controls

### During Streaming:
- **ESC/Q**: Quit application
- **R**: Reset camera view to default position
- **Mouse**: 
  - Left click + drag: Rotate 3D view
  - Right click + drag: Pan view
  - Scroll wheel: Zoom in/out

## 📊 Performance

### Typical Performance:
- **Frame Rate**: 25-30 FPS
- **Point Count**: 5,000 - 20,000 points per frame
- **Latency**: < 50ms
- **CPU Usage**: Medium (optimized filtering)

### Optimization Tips:
- **Lighting**: Ensure good ambient lighting
- **Distance**: Stay within 0.3m - 2.0m range for best results
- **Movement**: Move camera slowly for smoother visualization
- **USB**: Use USB 3.0+ port for best performance

## 🔧 Troubleshooting

### Camera Not Detected
```bash
# Check connected devices
rs-enumerate-devices

# Check USB permissions (Linux)
sudo chmod 666 /dev/video*

# Try different USB port/cable
```

### Poor Performance
1. **Close other applications** that use camera/GPU
2. **Check USB connection** - use USB 3.0+ port
3. **Reduce point density** by moving further from objects
4. **Restart application** if performance degrades

### Installation Issues
```bash
# Update pip
pip install --upgrade pip

# Reinstall packages
pip install --force-reinstall -r requirements.txt

# Check Python version
python3 --version  # Should be 3.6+
```

## 📁 Files

- `simple_realsense_streaming.py` - Main streaming application
- `requirements.txt` - Python dependencies
- `setup.sh` - Setup script with dependency installation
- `run_demo.sh` - Demo launcher with device checking
- `README.md` - This file

## 🎨 Customization

### Modify Visualization:
Edit `simple_realsense_streaming.py`:

```python
# Change background color
render_option.background_color = np.asarray([0.1, 0.1, 0.1])  # Dark gray

# Adjust point size
render_option.point_size = 2.0  # Larger points

# Change depth range
depth_trunc=3.0,  # Max 3 meters
distances > 0.2) & (distances < 3.0  # Filter range
```

### Performance Tuning:
```python
# Resolution (trade-off: quality vs performance)
self.width = 424   # Lower for better performance
self.height = 240

# Point cloud size
if len(pcd.points) > 15000:  # Reduce max points
    pcd = pcd.voxel_down_sample(0.008)  # Increase voxel size
```

## 🎯 Comparison with iPhone Record3D

| Feature | iPhone Record3D | This Demo |
|---------|----------------|-----------|
| Portability | High (wireless) | Medium (USB tethered) |
| Depth Range | 0.5m - 5m | 0.3m - 10m+ |
| Accuracy | Good | Excellent |
| Frame Rate | 30fps | 25-30fps |
| Setup | iPhone + $5 app | Camera ~$200 |
| Customization | Limited | Full source code |

## 📚 Resources

- [Intel RealSense Documentation](https://dev.intelrealsense.com/)
- [Open3D Documentation](http://www.open3d.org/docs/)
- [RealSense Python Examples](https://github.com/IntelRealSense/librealsense/tree/master/wrappers/python/examples)

## 🤝 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify your RealSense device with `rs-enumerate-devices`
3. Test with Intel RealSense Viewer first
4. Ensure proper lighting and distance from objects

## 📄 License

This project uses the same license as the original iPhone streaming implementation.
