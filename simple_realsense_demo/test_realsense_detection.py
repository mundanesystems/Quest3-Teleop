#!/usr/bin/env python3
"""
Simple RealSense D435 Detection Test
"""

import pyrealsense2 as rs
import sys

def test_realsense_detection():
    print("🔍 Testing RealSense D435 detection...")
    
    try:
        # Create a context
        ctx = rs.context()
        devices = ctx.query_devices()
        
        if len(devices) == 0:
            print("❌ No RealSense devices found!")
            print("🔧 Troubleshooting:")
            print("1. Make sure RealSense D435 is connected via USB 3.0")
            print("2. Try a different USB 3.0 port")
            print("3. Check if RealSense Viewer can detect the camera")
            print("4. Restart the camera by unplugging and reconnecting")
            return False
        
        for i, device in enumerate(devices):
            print(f"✅ Device {i}: {device.get_info(rs.camera_info.name)}")
            print(f"   Serial: {device.get_info(rs.camera_info.serial_number)}")
            print(f"   Firmware: {device.get_info(rs.camera_info.firmware_version)}")
            
            # Check available sensors
            sensors = device.query_sensors()
            for j, sensor in enumerate(sensors):
                print(f"   Sensor {j}: {sensor.get_info(rs.camera_info.name)}")
        
        # Test pipeline creation
        print("\n🚀 Testing pipeline creation...")
        pipeline = rs.pipeline()
        config = rs.config()
        
        # Try different resolutions
        resolutions = [
            (640, 480),
            (848, 480),
            (1280, 720)
        ]
        
        for width, height in resolutions:
            try:
                config.enable_stream(rs.stream.depth, width, height, rs.format.z16, 30)
                config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, 30)
                
                profile = pipeline.start(config)
                print(f"✅ Pipeline started successfully at {width}x{height}")
                
                # Try to get a few frames
                for i in range(5):
                    frames = pipeline.wait_for_frames(timeout_ms=1000)
                    depth_frame = frames.get_depth_frame()
                    color_frame = frames.get_color_frame()
                    
                    if depth_frame and color_frame:
                        print(f"   Frame {i+1}: ✅ Got depth and color")
                    else:
                        print(f"   Frame {i+1}: ❌ Missing frames")
                
                pipeline.stop()
                print(f"✅ Test completed successfully at {width}x{height}")
                return True
                
            except Exception as e:
                print(f"❌ Failed at {width}x{height}: {e}")
                try:
                    pipeline.stop()
                except:
                    pass
                config = rs.config()  # Reset config
                pipeline = rs.pipeline()  # Reset pipeline
                continue
        
        print("❌ All resolutions failed")
        return False
        
    except Exception as e:
        print(f"❌ RealSense detection failed: {e}")
        print("🔧 Possible solutions:")
        print("1. Install RealSense SDK: https://github.com/IntelRealSense/librealsense")
        print("2. Install Python package: pip install pyrealsense2")
        print("3. Update RealSense firmware using Intel RealSense Viewer")
        print("4. Check USB connection (must be USB 3.0)")
        return False

if __name__ == '__main__':
    success = test_realsense_detection()
    if success:
        print("\n🎉 RealSense D435 is working correctly!")
        print("You can now run the point cloud server.")
    else:
        print("\n💡 Fix the RealSense issues above before running the point cloud server.")
        sys.exit(1)
