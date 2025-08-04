#!/usr/bin/env python3
"""
ULTRA-OPTIMIZED Intel RealSense D435 Point Cloud Streaming
Targeting 30 FPS by eliminating the point cloud creation bottleneck
"""

import numpy as np
import pyrealsense2 as rs
import cv2
import time
import open3d as o3d
from threading import Thread, Event
import queue
from numba import jit
import warnings
warnings.filterwarnings("ignore")


@jit(nopython=True)
def fast_depth_to_points(depth_array, fx, fy, ppx, ppy, depth_scale, min_depth=0.1, max_depth=2.0):
    """Ultra-fast depth to 3D points conversion using Numba JIT"""
    h, w = depth_array.shape
    points = np.empty((h * w, 3), dtype=np.float32)
    valid_mask = np.empty(h * w, dtype=np.bool_)
    
    idx = 0
    for j in range(h):
        for i in range(w):
            z = depth_array[j, i] * depth_scale
            if min_depth < z < max_depth:
                x = (i - ppx) * z / fx
                y = (j - ppy) * z / fy
                points[idx, 0] = x
                points[idx, 1] = -y  # Flip Y
                points[idx, 2] = -z  # Flip Z
                valid_mask[idx] = True
            else:
                valid_mask[idx] = False
            idx += 1
    
    return points, valid_mask


class UltraOptimizedStreamer:
    def __init__(self):
        print("🚀 Initializing ULTRA-OPTIMIZED RealSense D435...")
        
        # Pipeline setup with fastest possible config
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        
        # OPTIMIZED: Use native D435 resolution for best performance
        self.width = 848
        self.height = 480
        self.fps = 30
        
        self.config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
        self.config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
        
        # Start pipeline
        self.profile = self.pipeline.start(self.config)
        print(f"✅ Streaming at {self.width}x{self.height} @ {self.fps}fps")
        
        # Get camera parameters for fast math
        depth_sensor = self.profile.get_device().first_depth_sensor()
        self.depth_scale = depth_sensor.get_depth_scale()
        
        color_profile = self.profile.get_stream(rs.stream.color)
        self.intrinsics = color_profile.as_video_stream_profile().get_intrinsics()
        
        # OPTIMIZED: Minimal filtering for maximum speed
        self.align = rs.align(rs.stream.color)
        self.spatial = rs.spatial_filter()
        self.spatial.set_option(rs.option.filter_magnitude, 1)  # Minimal filtering
        self.spatial.set_option(rs.option.filter_smooth_alpha, 0.1)
        
        # Skip temporal filtering for max speed
        # self.temporal = rs.temporal_filter()
        
        # Threading with larger buffer
        self.frame_queue = queue.Queue(maxsize=3)
        self.running = Event()
        self.running.set()
        
        # OPTIMIZED: Smaller window for faster rendering
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window("ULTRA-FAST RealSense Stream", width=1000, height=750)
        
        # Ultra-performance render settings
        render_option = self.vis.get_render_option()
        render_option.background_color = np.asarray([0.0, 0.0, 0.0])
        render_option.point_size = 1.0  # Smallest points for speed
        render_option.show_coordinate_frame = False
        render_option.light_on = False  # Disable lighting for speed
        
        # Point cloud object
        self.pcd = o3d.geometry.PointCloud()
        
        # Pre-allocate arrays for speed
        self.max_points = 50000
        self.points_buffer = np.zeros((self.max_points, 3), dtype=np.float32)
        self.colors_buffer = np.zeros((self.max_points, 3), dtype=np.float32)
        
        print("🔥 ULTRA-OPTIMIZED setup complete!")
    
    def _create_point_cloud_ultra_fast(self, color_image, depth_image):
        """ULTRA-FAST point cloud creation with Numba acceleration"""
        start_time = time.perf_counter()
        
        # Use JIT-compiled function for speed
        points_3d, valid_mask = fast_depth_to_points(
            depth_image, 
            self.intrinsics.fx, self.intrinsics.fy,
            self.intrinsics.ppx, self.intrinsics.ppy,
            self.depth_scale
        )
        
        # Extract valid points and colors
        valid_points = points_3d[valid_mask]
        color_flat = color_image.reshape(-1, 3)[valid_mask] / 255.0
        
        # Aggressive downsampling for 60+ FPS
        if len(valid_points) > self.max_points:
            # Ultra-fast random sampling
            step = len(valid_points) // self.max_points
            indices = np.arange(0, len(valid_points), step)[:self.max_points]
            valid_points = valid_points[indices]
            color_flat = color_flat[indices]
        
        # Create point cloud
        pcd = o3d.geometry.PointCloud()
        if len(valid_points) > 0:
            pcd.points = o3d.utility.Vector3dVector(valid_points.astype(np.float64))
            pcd.colors = o3d.utility.Vector3dVector(color_flat.astype(np.float64))
        
        elapsed = (time.perf_counter() - start_time) * 1000
        return pcd, elapsed
    
    def _capture_frames_ultra_fast(self):
        """Ultra-fast frame capture"""
        while self.running.is_set():
            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=10)
                aligned_frames = self.align.process(frames)
                
                depth_frame = aligned_frames.get_depth_frame()
                color_frame = aligned_frames.get_color_frame()
                
                if depth_frame and color_frame:
                    # Minimal filtering for speed
                    depth_frame = self.spatial.process(depth_frame)
                    
                    # Convert to numpy
                    color_image = np.asanyarray(color_frame.get_data())
                    depth_image = np.asanyarray(depth_frame.get_data())
                    
                    # Quick BGR to RGB
                    color_rgb = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                    
                    # Non-blocking queue add
                    try:
                        self.frame_queue.put((color_rgb, depth_image), block=False)
                    except queue.Full:
                        # Drop oldest frame
                        try:
                            self.frame_queue.get_nowait()
                            self.frame_queue.put((color_rgb, depth_image), block=False)
                        except:
                            pass
                        
            except Exception:
                continue
    
    def start_streaming(self):
        """Start ultra-optimized streaming"""
        print(f"\\n⚡ ULTRA-FAST MODE @ {self.width}x{self.height}")
        print("🎯 Target: 30 FPS")
        print("\\nControls:")
        print("  ESC/Q  - Quit")
        print("  R      - Reset view")
        print("=" * 50)
        
        # Start capture thread
        capture_thread = Thread(target=self._capture_frames_ultra_fast, daemon=True)
        capture_thread.start()
        
        # Set view
        view_control = self.vis.get_view_control()
        view_control.set_front([0.0, 0.0, -1.0])
        view_control.set_lookat([0, 0, 1])
        view_control.set_up([0, -1, 0])
        view_control.set_zoom(0.8)
        
        geometry_added = False
        frame_count = 0
        start_time = time.time()
        last_fps_time = start_time
        
        # Performance tracking
        processing_times = []
        
        try:
            while True:
                loop_start = time.perf_counter()
                
                # Get frame with minimal timeout
                try:
                    color_rgb, depth_data = self.frame_queue.get(timeout=0.005)
                except queue.Empty:
                    continue
                
                # Ultra-fast point cloud creation
                current_pcd, processing_time = self._create_point_cloud_ultra_fast(color_rgb, depth_data)
                processing_times.append(processing_time)
                
                if len(current_pcd.points) == 0:
                    continue
                
                # Minimal visualization update
                self.pcd.points = current_pcd.points
                self.pcd.colors = current_pcd.colors
                
                if not geometry_added:
                    self.vis.add_geometry(self.pcd)
                    geometry_added = True
                else:
                    self.vis.update_geometry(self.pcd)
                
                # Fast rendering
                self.vis.poll_events()
                self.vis.update_renderer()
                
                # Quick keyboard check
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord('q'):
                    break
                elif key == ord('r'):
                    view_control.set_front([0.0, 0.0, -1.0])
                    view_control.set_lookat([0, 0, 1])
                    view_control.set_up([0, -1, 0])
                    view_control.set_zoom(0.8)
                
                # FPS calculation and display
                frame_count += 1
                current_time = time.time()
                
                if current_time - last_fps_time > 2.0:  # Every 2 seconds
                    fps = frame_count / (current_time - start_time)
                    point_count = len(self.pcd.points)
                    queue_size = self.frame_queue.qsize()
                    
                    # Average processing time
                    avg_processing = np.mean(processing_times[-50:]) if processing_times else 0
                    
                    # Performance indicator
                    perf_indicator = "🔥" if fps > 25 else "⚡" if fps > 20 else "🐌"
                    queue_indicator = "🟢" if queue_size < 2 else "🟡"
                    
                    print(f"{perf_indicator} {fps:.1f} FPS | {point_count:,} pts | "
                          f"Proc: {avg_processing:.1f}ms | Q: {queue_indicator}{queue_size}")
                    
                    last_fps_time = current_time
                
        except KeyboardInterrupt:
            print("\\n👋 Ultra-fast streaming stopped")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            # Final performance report
            if processing_times:
                avg_proc = np.mean(processing_times)
                final_fps = frame_count / (time.time() - start_time)
                print(f"\\n📊 FINAL PERFORMANCE:")
                print(f"   Average FPS: {final_fps:.1f}")
                print(f"   Processing Time: {avg_proc:.1f}ms")
                print(f"   Theoretical Max FPS: {1000/avg_proc:.1f}")
            
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
        # Check if numba is available
        import numba
        print("✅ Numba JIT compilation available for maximum speed")
        
        streamer = UltraOptimizedStreamer()
        streamer.start_streaming()
    except ImportError:
        print("⚠️  Installing numba for maximum performance...")
        import subprocess
        subprocess.run(["pip", "install", "numba"], check=True)
        print("✅ Numba installed! Please run again for ultra-fast performance.")
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        print("\\n🔧 Troubleshooting:")
        print("1. Check RealSense D435 is connected via USB 3.0")
        print("2. Install: pip install numba (for JIT acceleration)")
        print("3. Close other applications using camera")
