#!/usr/bin/env python3
"""
RealSense Point Cloud Streaming Server
Streams 3D point cloud data to Unity instead of raw video
"""

import numpy as np
import pyrealsense2 as rs
import cv2
import time
import socket
import struct
import pickle
import threading
from collections import deque
import argparse

try:
    from numba import jit
    NUMBA_AVAILABLE = True
    print("✅ Numba JIT available for maximum speed")
except ImportError:
    NUMBA_AVAILABLE = False
    print("⚠️  Numba not available, using optimized NumPy")

if NUMBA_AVAILABLE:
    @jit(nopython=True, fastmath=True)
    def fast_depth_to_points(depth_array, fx, fy, ppx, ppy, depth_scale, min_depth=0.1, max_depth=2.0):
        """Ultra-fast depth to 3D points conversion using Numba JIT"""
        h, w = depth_array.shape
        points = np.empty((h * w, 3), dtype=np.float32)
        colors = np.empty((h * w, 3), dtype=np.float32)
        valid_count = 0
        
        for j in range(h):
            for i in range(w):
                z = depth_array[j, i] * depth_scale
                if min_depth < z < max_depth:
                    x = (i - ppx) * z / fx
                    y = (j - ppy) * z / fy
                    points[valid_count, 0] = x
                    points[valid_count, 1] = -y  # Flip Y
                    points[valid_count, 2] = -z  # Flip Z
                    valid_count += 1
        
        return points[:valid_count], valid_count

class RealSensePointCloudServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        
        # Pipeline setup
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        
        # Stream configuration - optimized for point clouds
        self.width = 640
        self.height = 480
        self.fps = 30
        
        self.config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
        self.config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
        
        # Start pipeline
        self.profile = self.pipeline.start(self.config)
        
        # Get depth scale and intrinsics
        depth_sensor = self.profile.get_device().first_depth_sensor()
        self.depth_scale = depth_sensor.get_depth_scale()
        
        color_profile = self.profile.get_stream(rs.stream.color)
        self.intrinsics = color_profile.as_video_stream_profile().get_intrinsics()
        
        # Alignment and filtering
        self.align = rs.align(rs.stream.color)
        self.spatial = rs.spatial_filter()
        self.spatial.set_option(rs.option.filter_magnitude, 2)
        self.spatial.set_option(rs.option.filter_smooth_alpha, 0.4)
        
        # Network setup
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        # Point cloud settings
        self.max_points = 15000  # Limit for network performance
        
        print(f"Point Cloud server listening on {self.host}:{self.port}")
        print(f"Max points per frame: {self.max_points}")
        
    def create_point_cloud(self, color_image, depth_image):
        """Create point cloud from RGB-D data"""
        if NUMBA_AVAILABLE:
            # Use JIT-compiled version for colors
            points_3d, valid_count = fast_depth_to_points(
                depth_image, 
                self.intrinsics.fx, self.intrinsics.fy,
                self.intrinsics.ppx, self.intrinsics.ppy,
                self.depth_scale
            )
            
            # Get corresponding colors
            h, w = depth_image.shape
            color_flat = color_image.reshape(-1, 3)
            
            # Extract colors for valid points (this needs to be done in regular Python)
            valid_indices = []
            for j in range(h):
                for i in range(w):
                    z = depth_image[j, i] * self.depth_scale
                    if 0.1 < z < 2.0:
                        valid_indices.append(j * w + i)
            
            colors = color_flat[valid_indices[:valid_count]] / 255.0
            
        else:
            # Vectorized NumPy fallback
            h, w = depth_image.shape
            i, j = np.meshgrid(np.arange(w), np.arange(h), indexing='xy')
            
            z = depth_image.astype(np.float32) * self.depth_scale
            x = (i - self.intrinsics.ppx) * z / self.intrinsics.fx
            y = (j - self.intrinsics.ppy) * z / self.intrinsics.fy
            
            valid_mask = (z > 0.1) & (z < 2.0)
            points_3d = np.column_stack([x[valid_mask], -y[valid_mask], -z[valid_mask]])
            colors = color_image[valid_mask].astype(np.float32) / 255.0
        
        # Downsample if too many points
        if len(points_3d) > self.max_points:
            step = len(points_3d) // self.max_points
            indices = np.arange(0, len(points_3d), step)[:self.max_points]
            points_3d = points_3d[indices]
            colors = colors[indices]
        
        return points_3d.astype(np.float32), colors.astype(np.float32)
    
    def handle_client(self, conn, addr):
        """Handle individual client connection"""
        print(f"Client connected: {addr}")
        
        try:
            while True:
                # Capture frames
                frames = self.pipeline.wait_for_frames(timeout_ms=50)
                aligned_frames = self.align.process(frames)
                
                depth_frame = aligned_frames.get_depth_frame()
                color_frame = aligned_frames.get_color_frame()
                
                if not depth_frame or not color_frame:
                    continue
                
                # Apply filtering
                depth_frame = self.spatial.process(depth_frame)
                
                # Convert to numpy
                color_image = np.asanyarray(color_frame.get_data())
                depth_image = np.asanyarray(depth_frame.get_data())
                
                # Convert BGR to RGB
                color_rgb = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                
                # Create point cloud
                points, colors = self.create_point_cloud(color_rgb, depth_image)
                
                if len(points) == 0:
                    continue
                
                # Prepare data packet
                point_cloud_data = {
                    'points': points,
                    'colors': colors,
                    'timestamp': time.time(),
                    'point_count': len(points)
                }
                
                # Serialize data
                try:
                    serialized_data = pickle.dumps(point_cloud_data, protocol=pickle.HIGHEST_PROTOCOL)
                    data_size = len(serialized_data)
                    
                    # Send data size first, then data
                    conn.sendall(struct.pack('<L', data_size))
                    conn.sendall(serialized_data)
                    
                except Exception as e:
                    print(f"Error sending data: {e}")
                    break
                
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            print(f"Client {addr} disconnected")
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            conn.close()
    
    def start_streaming(self):
        """Start the point cloud streaming server"""
        print("🎯 Point Cloud streaming server started")
        print("📱 Waiting for Unity clients...")
        print("Controls: Ctrl+C to stop")
        print("=" * 50)
        
        try:
            while True:
                conn, addr = self.server_socket.accept()
                
                # Handle each client in a separate thread
                client_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(conn, addr), 
                    daemon=True
                )
                client_thread.start()
                
        except KeyboardInterrupt:
            print("\n👋 Server stopped by user")
        except Exception as e:
            print(f"❌ Server error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.pipeline.stop()
            self.server_socket.close()
        except:
            pass
        print("✅ Cleanup complete")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="RealSense Point Cloud Streaming Server")
    parser.add_argument('--host', type=str, default='0.0.0.0', 
                       help='Host IP address to bind the server to.')
    parser.add_argument('--port', type=int, default=8081, 
                       help='Port to listen on (default: 8081 to avoid conflict with video server).')
    args = parser.parse_args()
    
    try:
        server = RealSensePointCloudServer(args.host, args.port)
        server.start_streaming()
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Check RealSense D435 is connected via USB 3.0")
        print("2. Install dependencies: pip install pyrealsense2 opencv-python")
        print("3. For maximum speed: pip install numba")
