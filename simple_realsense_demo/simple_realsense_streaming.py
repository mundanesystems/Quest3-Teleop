#!/usr/bin/env python3
"""
Simple Intel RealSense D435 Point Cloud Streaming
Clean visualization like iPhone Record3D demo
"""

import numpy as np
import pyrealsense2 as rs
import cv2
import time
import open3d as o3d
from threading import Thread, Event
import queue


class SimpleRealSenseStreamer:
    def __init__(self):
        print("Initializing RealSense D435 for smooth point cloud streaming...")
        
        # Pipeline setup
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        
        # Stream configuration - optimized for smooth performance
        self.width = 640
        self.height = 480
        self.fps = 30
        
        self.config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
        self.config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
        
        # Start pipeline
        self.profile = self.pipeline.start(self.config)
        
        # Get depth scale
        depth_sensor = self.profile.get_device().first_depth_sensor()
        self.depth_scale = depth_sensor.get_depth_scale()
        
        # Alignment
        self.align = rs.align(rs.stream.color)
        
        # Camera intrinsics
        color_profile = self.profile.get_stream(rs.stream.color)
        self.intrinsics = color_profile.as_video_stream_profile().get_intrinsics()
        
        # Simple filtering
        self.spatial = rs.spatial_filter()
        self.temporal = rs.temporal_filter()
        
        # Threading
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = Event()
        self.running.set()
        
        # Visualization setup
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window("Intel RealSense D435 - Point Cloud Stream", 
                              width=1200, height=800)
        
        # Clean iPhone-like appearance
        render_option = self.vis.get_render_option()
        render_option.background_color = np.asarray([0.0, 0.0, 0.0])  # Black background
        render_option.point_size = 1.5
        render_option.show_coordinate_frame = False
        
        # Point cloud object
        self.pcd = o3d.geometry.PointCloud()
        
        print("Setup complete!")
    
    def _get_intrinsic_matrix(self):
        """Get camera intrinsic matrix"""
        return np.array([[self.intrinsics.fx, 0, self.intrinsics.ppx],
                        [0, self.intrinsics.fy, self.intrinsics.ppy],
                        [0, 0, 1]])
    
    def _create_point_cloud(self, color_image, depth_image):
        """Create point cloud from RGB-D data"""
        # Ensure same dimensions
        if color_image.shape[:2] != depth_image.shape[:2]:
            depth_image = cv2.resize(depth_image, (color_image.shape[1], color_image.shape[0]))
        
        # Convert to Open3D format
        color_o3d = o3d.geometry.Image(color_image)
        depth_o3d = o3d.geometry.Image(depth_image.astype(np.float32))
        
        # Create RGBD image
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_o3d, depth_o3d,
            depth_scale=1.0/self.depth_scale,
            depth_trunc=3,  # 3m max depth
            convert_rgb_to_intensity=False
        )
        
        # Camera intrinsics
        intrinsic_matrix = self._get_intrinsic_matrix()
        camera_intrinsic = o3d.camera.PinholeCameraIntrinsic(
            width=self.width,
            height=self.height,
            fx=intrinsic_matrix[0, 0],
            fy=intrinsic_matrix[1, 1],
            cx=intrinsic_matrix[0, 2],
            cy=intrinsic_matrix[1, 2]
        )
        
        # Generate point cloud
        pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, camera_intrinsic)
        
        # Apply coordinate transformation
        transform = np.array([[1, 0, 0, 0],
                             [0, -1, 0, 0], 
                             [0, 0, -1, 0],
                             [0, 0, 0, 1]])
        pcd.transform(transform)
        
        # Simple filtering
        if len(pcd.points) > 0:
            points = np.asarray(pcd.points)
            colors = np.asarray(pcd.colors)
            
            # Remove points too close/far
            distances = np.linalg.norm(points, axis=1)
            valid_mask = (distances > 0.3) & (distances < 3.0)

            if np.any(valid_mask):
                pcd.points = o3d.utility.Vector3dVector(points[valid_mask])
                pcd.colors = o3d.utility.Vector3dVector(colors[valid_mask])
        
        # Downsample if too many points
        if len(pcd.points) > 30000:
            pcd = pcd.voxel_down_sample(0.005)
        
        return pcd
    
    def _capture_frames(self):
        """Frame capture thread"""
        while self.running.is_set():
            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=50)
                aligned_frames = self.align.process(frames)
                
                depth_frame = aligned_frames.get_depth_frame()
                color_frame = aligned_frames.get_color_frame()
                
                if depth_frame and color_frame:
                    # Apply simple filtering
                    depth_frame = self.spatial.process(depth_frame)
                    depth_frame = self.temporal.process(depth_frame)
                    
                    # Convert to numpy
                    color_image = np.asanyarray(color_frame.get_data())
                    depth_image = np.asanyarray(depth_frame.get_data())
                    
                    # Convert BGR to RGB
                    color_image_rgb = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                    
                    # Add to queue
                    try:
                        self.frame_queue.put((color_image_rgb, depth_image), block=False)
                    except queue.Full:
                        pass
                        
            except Exception:
                continue
    
    def start_streaming(self):
        """Start the streaming"""
        print("\\n🎯 Starting smooth point cloud streaming...")
        print("📱 iPhone Record3D style visualization")
        print("\\nControls:")
        print("  ESC/Q  - Quit")
        print("  R      - Reset view") 
        print("  Mouse  - Rotate, pan, zoom")
        print("=" * 50)
        
        # Start capture thread
        capture_thread = Thread(target=self._capture_frames, daemon=True)
        capture_thread.start()
        
        # Set nice initial view
        view_control = self.vis.get_view_control()
        view_control.set_front([0.0, 0.0, -1.0])
        view_control.set_lookat([0, 0, 1])
        view_control.set_up([0, -1, 0])
        view_control.set_zoom(0.8)
        
        geometry_added = False
        frame_count = 0
        start_time = time.time()
        
        try:
            while True:
                # Get latest frame
                try:
                    color_rgb, depth_data = self.frame_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Create point cloud
                current_pcd = self._create_point_cloud(color_rgb, depth_data)
                
                if len(current_pcd.points) == 0:
                    continue
                
                # Update visualization
                self.pcd.points = current_pcd.points
                self.pcd.colors = current_pcd.colors
                
                # Add or update geometry
                if not geometry_added:
                    self.vis.add_geometry(self.pcd)
                    geometry_added = True
                else:
                    self.vis.update_geometry(self.pcd)
                
                # Update visualization
                self.vis.poll_events()
                self.vis.update_renderer()
                
                # Handle keyboard
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord('q'):  # ESC or Q
                    break
                elif key == ord('r'):
                    # Reset view
                    view_control.set_front([0.0, 0.0, -1.0])
                    view_control.set_lookat([0, 0, 1])
                    view_control.set_up([0, -1, 0])
                    view_control.set_zoom(0.8)
                
                # Print FPS occasionally
                frame_count += 1
                if frame_count % 90 == 0:  # Every 3 seconds at 30fps
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed
                    point_count = len(self.pcd.points)
                    print(f"🔥 {fps:.1f} fps | {point_count:,} points | Smooth streaming!")
                
        except KeyboardInterrupt:
            print("\\n👋 Streaming stopped by user")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        self.running.clear()
        try:
            self.pipeline.stop()
            cv2.destroyAllWindows()
            self.vis.destroy_window()
        except:
            pass
        print("✅ Cleanup complete")


if __name__ == '__main__':
    try:
        streamer = SimpleRealSenseStreamer()
        streamer.start_streaming()
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        print("\\n🔧 Troubleshooting:")
        print("1. Check RealSense D435 is connected via USB 3.0")
        print("2. Run: rs-enumerate-devices")
        print("3. Install: pip install pyrealsense2 opencv-python open3d")
