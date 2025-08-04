#!/usr/bin/env python3
"""
ROBUST ULTRA-FAST RealSense D435 with Detailed Latency Analysis
Fixed crash issues + comprehensive performance profiling
"""

import numpy as np
import pyrealsense2 as rs
import cv2
import time
import open3d as o3d
from threading import Thread, Event
import queue
from collections import deque
import signal
import sys
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


class RobustUltraFastStreamer:
    def __init__(self):
        print("🚀 Initializing ROBUST ULTRA-FAST RealSense D435...")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Pipeline setup
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        
        # Optimized resolution
        self.width = 848
        self.height = 480
        self.fps = 30
        
        self.config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
        self.config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
        
        # Start pipeline
        self.profile = self.pipeline.start(self.config)
        print(f"✅ Streaming at {self.width}x{self.height} @ {self.fps}fps")
        
        # Camera parameters
        depth_sensor = self.profile.get_device().first_depth_sensor()
        self.depth_scale = depth_sensor.get_depth_scale()
        
        color_profile = self.profile.get_stream(rs.stream.color)
        self.intrinsics = color_profile.as_video_stream_profile().get_intrinsics()
        
        # Optimized filtering
        self.align = rs.align(rs.stream.color)
        self.spatial = rs.spatial_filter()
        self.spatial.set_option(rs.option.filter_magnitude, 2)
        self.spatial.set_option(rs.option.filter_smooth_alpha, 0.4)
        
        # Threading
        self.frame_queue = queue.Queue(maxsize=3)
        self.running = Event()
        self.running.set()
        self.shutdown_requested = False
        
        # Visualization with error handling
        try:
            self.vis = o3d.visualization.Visualizer()
            self.vis.create_window("ROBUST Ultra-Fast RealSense Stream", width=1000, height=750)
            
            # Performance render settings
            render_option = self.vis.get_render_option()
            render_option.background_color = np.asarray([0.0, 0.0, 0.0])
            render_option.point_size = 1.0
            render_option.show_coordinate_frame = False
            render_option.light_on = False
            
            self.pcd = o3d.geometry.PointCloud()
            self.vis_available = True
        except Exception as e:
            print(f"⚠️  Visualization error: {e}, continuing without display")
            self.vis_available = False
        
        # DETAILED LATENCY TRACKING
        self.latency_tracker = {
            'frame_capture': deque(maxlen=100),
            'frame_alignment': deque(maxlen=100),
            'depth_filtering': deque(maxlen=100),
            'numpy_conversion': deque(maxlen=100),
            'bgr_to_rgb': deque(maxlen=100),
            'point_cloud_creation': deque(maxlen=100),
            'open3d_conversion': deque(maxlen=100),
            'visualization_update': deque(maxlen=100),
            'total_frame_time': deque(maxlen=100)
        }
        
        # Performance settings
        self.max_points = 50000
        
        print("🔥 ROBUST ULTRA-FAST setup complete!")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\\n📡 Received signal {signum}, shutting down gracefully...")
        self.shutdown_requested = True
        self.running.clear()
    
    def _create_point_cloud_with_profiling(self, color_image, depth_image):
        """Point cloud creation with detailed latency profiling"""
        total_start = time.perf_counter()
        
        # Step 1: Point cloud generation
        pc_start = time.perf_counter()
        if NUMBA_AVAILABLE:
            # Use JIT-compiled version
            points_3d, valid_mask = fast_depth_to_points(
                depth_image, 
                self.intrinsics.fx, self.intrinsics.fy,
                self.intrinsics.ppx, self.intrinsics.ppy,
                self.depth_scale
            )
            valid_points = points_3d[valid_mask]
            color_flat = color_image.reshape(-1, 3)[valid_mask] / 255.0
        else:
            # Vectorized NumPy fallback
            h, w = depth_image.shape
            i, j = np.meshgrid(np.arange(w), np.arange(h), indexing='xy')
            
            z = depth_image.astype(np.float32) * self.depth_scale
            x = (i - self.intrinsics.ppx) * z / self.intrinsics.fx
            y = (j - self.intrinsics.ppy) * z / self.intrinsics.fy
            
            valid_mask = (z > 0.1) & (z < 2.0)
            valid_points = np.column_stack([x[valid_mask], -y[valid_mask], -z[valid_mask]])
            color_flat = color_image[valid_mask].astype(np.float32) / 255.0
        
        pc_time = (time.perf_counter() - pc_start) * 1000
        self.latency_tracker['point_cloud_creation'].append(pc_time)
        
        # Step 2: Downsampling
        if len(valid_points) > self.max_points:
            step = len(valid_points) // self.max_points
            indices = np.arange(0, len(valid_points), step)[:self.max_points]
            valid_points = valid_points[indices]
            color_flat = color_flat[indices]
        
        # Step 3: Open3D conversion
        o3d_start = time.perf_counter()
        pcd = o3d.geometry.PointCloud()
        if len(valid_points) > 0:
            pcd.points = o3d.utility.Vector3dVector(valid_points.astype(np.float64))
            pcd.colors = o3d.utility.Vector3dVector(color_flat.astype(np.float64))
        o3d_time = (time.perf_counter() - o3d_start) * 1000
        self.latency_tracker['open3d_conversion'].append(o3d_time)
        
        total_time = (time.perf_counter() - total_start) * 1000
        
        return pcd, total_time
    
    def _capture_frames_with_profiling(self):
        """Frame capture with detailed profiling"""
        while self.running.is_set() and not self.shutdown_requested:
            try:
                frame_start = time.perf_counter()
                
                # Step 1: Frame capture
                capture_start = time.perf_counter()
                frames = self.pipeline.wait_for_frames(timeout_ms=10)
                capture_time = (time.perf_counter() - capture_start) * 1000
                self.latency_tracker['frame_capture'].append(capture_time)
                
                # Step 2: Frame alignment
                align_start = time.perf_counter()
                aligned_frames = self.align.process(frames)
                align_time = (time.perf_counter() - align_start) * 1000
                self.latency_tracker['frame_alignment'].append(align_time)
                
                depth_frame = aligned_frames.get_depth_frame()
                color_frame = aligned_frames.get_color_frame()
                
                if depth_frame and color_frame:
                    # Step 3: Depth filtering
                    filter_start = time.perf_counter()
                    depth_frame = self.spatial.process(depth_frame)
                    filter_time = (time.perf_counter() - filter_start) * 1000
                    self.latency_tracker['depth_filtering'].append(filter_time)
                    
                    # Step 4: NumPy conversion
                    numpy_start = time.perf_counter()
                    color_image = np.asanyarray(color_frame.get_data())
                    depth_image = np.asanyarray(depth_frame.get_data())
                    numpy_time = (time.perf_counter() - numpy_start) * 1000
                    self.latency_tracker['numpy_conversion'].append(numpy_time)
                    
                    # Step 5: BGR to RGB conversion
                    bgr_start = time.perf_counter()
                    color_rgb = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                    bgr_time = (time.perf_counter() - bgr_start) * 1000
                    self.latency_tracker['bgr_to_rgb'].append(bgr_time)
                    
                    # Add to queue with timestamp
                    timestamp = time.perf_counter()
                    try:
                        self.frame_queue.put((color_rgb, depth_image, timestamp), block=False)
                    except queue.Full:
                        # Drop oldest frame
                        try:
                            self.frame_queue.get_nowait()
                            self.frame_queue.put((color_rgb, depth_image, timestamp), block=False)
                        except:
                            pass
                
                # Record total frame processing time
                total_frame_time = (time.perf_counter() - frame_start) * 1000
                self.latency_tracker['total_frame_time'].append(total_frame_time)
                        
            except Exception as e:
                if not self.shutdown_requested:
                    print(f"⚠️  Capture error: {e}")
                continue
    
    def start_streaming(self):
        """Start robust streaming with detailed latency analysis"""
        mode = "JIT + PROFILING" if NUMBA_AVAILABLE else "VECTORIZED + PROFILING"
        print(f"\\n⚡ ROBUST {mode} MODE")
        print(f"📐 Resolution: {self.width}x{self.height} @ {self.fps}fps")
        print("🔍 Detailed latency profiling enabled")
        print("\\nControls:")
        print("  ESC/Q  - Quit")
        print("  R      - Reset view")
        print("  L      - Latency analysis report")
        print("=" * 60)
        
        # Start capture thread
        capture_thread = Thread(target=self._capture_frames_with_profiling, daemon=True)
        capture_thread.start()
        
        # Setup visualization if available
        if self.vis_available:
            view_control = self.vis.get_view_control()
            view_control.set_front([0.0, 0.0, -1.0])
            view_control.set_lookat([0, 0, 1])
            view_control.set_up([0, -1, 0])
            view_control.set_zoom(0.8)
        
        geometry_added = False
        frame_count = 0
        start_time = time.time()
        last_report_time = start_time
        
        try:
            while not self.shutdown_requested:
                # Get frame
                try:
                    color_rgb, depth_data, capture_timestamp = self.frame_queue.get(timeout=0.01)
                except queue.Empty:
                    continue
                
                # Create point cloud with profiling
                current_pcd, processing_time = self._create_point_cloud_with_profiling(color_rgb, depth_data)
                
                if len(current_pcd.points) == 0:
                    continue
                
                # Visualization update with profiling
                if self.vis_available:
                    vis_start = time.perf_counter()
                    
                    self.pcd.points = current_pcd.points
                    self.pcd.colors = current_pcd.colors
                    
                    if not geometry_added:
                        self.vis.add_geometry(self.pcd)
                        geometry_added = True
                    else:
                        self.vis.update_geometry(self.pcd)
                    
                    self.vis.poll_events()
                    self.vis.update_renderer()
                    
                    vis_time = (time.perf_counter() - vis_start) * 1000
                    self.latency_tracker['visualization_update'].append(vis_time)
                
                # Handle keyboard
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord('q'):
                    break
                elif key == ord('r') and self.vis_available:
                    view_control.set_front([0.0, 0.0, -1.0])
                    view_control.set_lookat([0, 0, 1])
                    view_control.set_up([0, -1, 0])
                    view_control.set_zoom(0.8)
                elif key == ord('l'):
                    self._print_latency_analysis()
                
                # Performance monitoring
                frame_count += 1
                current_time = time.time()
                
                if current_time - last_report_time > 3.0:
                    fps = frame_count / (current_time - start_time)
                    point_count = len(self.pcd.points) if self.vis_available else len(current_pcd.points)
                    queue_size = self.frame_queue.qsize()
                    
                    # Calculate total latency
                    total_latency = (time.perf_counter() - capture_timestamp) * 1000
                    
                    # Performance indicators
                    fps_icon = "🔥" if fps > 50 else "⚡" if fps > 30 else "🐌"
                    latency_icon = "🟢" if total_latency < 30 else "🟡" if total_latency < 50 else "🔴"
                    mode_icon = "🚀" if NUMBA_AVAILABLE else "💻"
                    
                    print(f"{fps_icon} {fps:.1f} FPS | {point_count:,} pts | "
                          f"{mode_icon} Proc: {processing_time:.1f}ms | {latency_icon} Total: {total_latency:.1f}ms | "
                          f"Q: {queue_size}")
                    
                    last_report_time = current_time
                
        except KeyboardInterrupt:
            print("\\n👋 Robust streaming stopped by user")
        except Exception as e:
            print(f"❌ Error during streaming: {e}")
        finally:
            self.cleanup()
    
    def _print_latency_analysis(self):
        """Print detailed latency breakdown analysis"""
        print("\\n" + "="*70)
        print("🔍 DETAILED LATENCY ANALYSIS")
        print("="*70)
        
        total_time = 0
        for component, times in self.latency_tracker.items():
            if times:
                avg_time = np.mean(times)
                max_time = np.max(times)
                min_time = np.min(times)
                
                # Calculate percentage of total
                if component != 'total_frame_time':
                    total_time += avg_time
                
                print(f"{component:20} | Avg: {avg_time:5.1f}ms | Max: {max_time:5.1f}ms | Min: {min_time:5.1f}ms")
        
        print("="*70)
        print(f"{'ESTIMATED TOTAL':20} | {total_time:5.1f}ms")
        print(f"{'THEORETICAL MAX FPS':20} | {1000/total_time:.1f} fps")
        print("="*70)
        
        # Identify bottlenecks
        bottlenecks = []
        for component, times in self.latency_tracker.items():
            if times and component != 'total_frame_time':
                avg_time = np.mean(times)
                if avg_time > 5:  # >5ms is significant
                    bottlenecks.append((component, avg_time))
        
        if bottlenecks:
            bottlenecks.sort(key=lambda x: x[1], reverse=True)
            print("🚨 PERFORMANCE BOTTLENECKS (>5ms):")
            for component, time_ms in bottlenecks:
                percentage = (time_ms / total_time) * 100
                print(f"   {component}: {time_ms:.1f}ms ({percentage:.1f}%)")
        
        print("="*70)
    
    def cleanup(self):
        """Robust cleanup with error handling"""
        print("🧹 Starting robust cleanup...")
        self.shutdown_requested = True
        self.running.clear()
        
        try:
            # Stop pipeline
            if hasattr(self, 'pipeline'):
                self.pipeline.stop()
                print("✅ Pipeline stopped")
        except Exception as e:
            print(f"⚠️  Pipeline cleanup error: {e}")
        
        try:
            # Close OpenCV windows
            cv2.destroyAllWindows()
            print("✅ OpenCV windows closed")
        except Exception as e:
            print(f"⚠️  OpenCV cleanup error: {e}")
        
        try:
            # Close Open3D visualizer
            if self.vis_available and hasattr(self, 'vis'):
                self.vis.destroy_window()
                print("✅ Open3D visualizer closed")
        except Exception as e:
            print(f"⚠️  Open3D cleanup error: {e}")
        
        # Print final latency analysis
        self._print_latency_analysis()
        print("✅ Robust cleanup complete")


if __name__ == '__main__':
    try:
        streamer = RobustUltraFastStreamer()
        streamer.start_streaming()
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        print("\\n🔧 Troubleshooting:")
        print("1. Check RealSense D435 is connected via USB 3.0")
        print("2. For maximum speed: pip install numba")
        print("3. Close other applications using the camera")
        print("\\n💡 This version provides detailed latency profiling and robust error handling")
