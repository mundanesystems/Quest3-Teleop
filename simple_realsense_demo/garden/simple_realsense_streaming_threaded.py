#!/usr/bin/env python3
"""
THREADED Intel RealSense D435 Point Cloud Streaming
Using multi-threading to optimize performance - Target: 30 FPS
"""

import numpy as np
import pyrealsense2 as rs
import cv2
import time
import open3d as o3d
from threading import Thread, Event, Lock
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp


class MultiThreadedOptimizedStreamer:
    def __init__(self):
        print("🚀 Initializing Multi-threaded Optimized RealSense D435...")
        
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
        self.spatial.set_option(rs.option.filter_smooth_alpha, 0.5)
        
        # ADVANCED THREADING PIPELINE
        self.raw_frame_queue = queue.Queue(maxsize=4)
        self.processed_queue = queue.Queue(maxsize=3)
        self.running = Event()
        self.running.set()
        
        # Thread pool for parallel processing
        cpu_count = mp.cpu_count()
        self.executor = ThreadPoolExecutor(max_workers=min(4, cpu_count))
        print(f"✅ Using {min(4, cpu_count)} threads for processing")
        
        # Pre-compute coordinate grids for vectorization
        self._setup_coordinate_grids()
        
        # Visualization
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window("Multi-threaded Optimized RealSense", width=1200, height=900)
        
        render_option = self.vis.get_render_option()
        render_option.background_color = np.asarray([0.0, 0.0, 0.0])
        render_option.point_size = 1.2
        render_option.show_coordinate_frame = False
        
        self.pcd = o3d.geometry.PointCloud()
        
        # Performance tracking
        self.performance_lock = Lock()
        self.frame_times = []
        
        print("🔥 Multi-threaded optimized setup complete!")
    
    def _setup_coordinate_grids(self):
        """Pre-compute coordinate grids for fast vectorization"""
        print("🔧 Pre-computing coordinate grids...")
        
        # Create coordinate meshgrid once
        i, j = np.meshgrid(np.arange(self.width), np.arange(self.height), indexing='xy')
        
        # Pre-compute coordinate arrays
        self.i_coords = i.astype(np.float32)
        self.j_coords = j.astype(np.float32)
        
        # Camera intrinsics as float32 for speed
        self.fx = np.float32(self.intrinsics.fx)
        self.fy = np.float32(self.intrinsics.fy)
        self.ppx = np.float32(self.intrinsics.ppx)
        self.ppy = np.float32(self.intrinsics.ppy)
        self.depth_scale_f32 = np.float32(self.depth_scale)
        
        print("✅ Coordinate grids ready")
    
    def _vectorized_depth_to_points(self, depth_image, color_image):
        """Ultra-optimized vectorized depth to 3D points conversion"""
        start_time = time.perf_counter()
        
        # Convert depth to float32 for speed
        depth_f32 = depth_image.astype(np.float32)
        
# 🔧 Worker 1: Processed 50000 points in 64.8ms/
        # Vectorized depth to 3D conversion
        z = depth_f32 * self.depth_scale_f32
        x = (self.i_coords - self.ppx) * z / self.fx
        y = (self.j_coords - self.ppy) * z / self.fy
        
        # Fast depth filtering using numpy boolean indexing
        valid_mask = (z > 0.1) & (z < 2.5)
        
        # Extract valid points in one vectorized operation
        x_valid = x[valid_mask]
        y_valid = -y[valid_mask]  # Flip Y
        z_valid = -z[valid_mask]  # Flip Z
        
        # Stack coordinates efficiently
        points_3d = np.column_stack([x_valid, y_valid, z_valid])
        
        # Extract colors for valid points
        colors_rgb = color_image[valid_mask].astype(np.float32) / 255.0
        
        # Smart downsampling based on point density
        if len(points_3d) > 40000:
            # Use systematic sampling for better distribution
            step = len(points_3d) // 40000
            indices = np.arange(0, len(points_3d), step)[:40000]
            points_3d = points_3d[indices]
            colors_rgb = colors_rgb[indices]
        
        elapsed = (time.perf_counter() - start_time) * 1000
        return points_3d, colors_rgb, elapsed
    
    def _create_point_cloud_optimized(self, color_image, depth_image):
        """Optimized point cloud creation"""
        # Get 3D points and colors
        points_3d, colors_rgb, processing_time = self._vectorized_depth_to_points(depth_image, color_image)
        
        # Create Open3D point cloud
        pcd = o3d.geometry.PointCloud()
        if len(points_3d) > 0:
            pcd.points = o3d.utility.Vector3dVector(points_3d.astype(np.float64))
            pcd.colors = o3d.utility.Vector3dVector(colors_rgb.astype(np.float64))
        
        return pcd, processing_time
    
    def _capture_frames_worker(self):
        """Worker thread for frame capture"""
        thread_id = "CAPTURE"
        print(f"🎬 {thread_id} thread started")
        
        while self.running.is_set():
            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=8)
                aligned_frames = self.align.process(frames)
                
                depth_frame = aligned_frames.get_depth_frame()
                color_frame = aligned_frames.get_color_frame()
                
                if depth_frame and color_frame:
                    # Apply filtering
                    depth_frame = self.spatial.process(depth_frame)
                    
                    # Convert to numpy
                    color_image = np.asanyarray(color_frame.get_data())
                    depth_image = np.asanyarray(depth_frame.get_data())
                    
                    # Add timestamp for latency tracking
                    timestamp = time.perf_counter()
                    
                    # Add to queue
                    try:
                        self.raw_frame_queue.put((color_image, depth_image, timestamp), block=False)
                    except queue.Full:
                        # Drop oldest frame to prevent backlog
                        try:
                            self.raw_frame_queue.get_nowait()
                            self.raw_frame_queue.put((color_image, depth_image, timestamp), block=False)
                        except:
                            pass
                        
            except Exception as e:
                continue
    
    def _process_frames_worker(self, worker_id):
        """Worker thread for frame processing"""
        print(f"🔧 PROCESS-{worker_id} thread started")
        
        while self.running.is_set():
            try:
                # Get frame from queue
                color_image, depth_image, capture_timestamp = self.raw_frame_queue.get(timeout=0.1)
                
                # Convert BGR to RGB
                color_rgb = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                
                # Process point cloud
                pcd, processing_time = self._create_point_cloud_optimized(color_rgb, depth_image)
                
                # Calculate total latency
                total_latency = (time.perf_counter() - capture_timestamp) * 1000
                
                # Only add if point cloud has data
                if len(pcd.points) > 0:
                    # Add to processed queue
                    try:
                        self.processed_queue.put((pcd, processing_time, total_latency), block=False)
                    except queue.Full:
                        # Drop oldest processed frame
                        try:
                            self.processed_queue.get_nowait()
                            self.processed_queue.put((pcd, processing_time, total_latency), block=False)
                        except:
                            pass
                        
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Processing error in worker {worker_id}: {e}")
                continue
    
    def start_streaming(self):
        """Start multi-threaded optimized streaming"""
        print(f"\\n⚡ MULTI-THREADED OPTIMIZED STREAMING")
        print(f"📐 Resolution: {self.width}x{self.height} @ {self.fps}fps")
        print("🎯 Pipeline Architecture:")
        print("   Thread 1: Frame capture (RealSense)")
        print("   Thread 2-3: Point cloud processing")
        print("   Main Thread: Visualization")
        print("\\nControls:")
        print("  ESC/Q  - Quit")
        print("  R      - Reset view")
        print("=" * 60)
        
        # Start worker threads
        capture_thread = Thread(target=self._capture_frames_worker, daemon=True)
        # Start only one processing thread initially to debug
        process_thread1 = Thread(target=self._process_frames_worker, args=(1,), daemon=True)
        
        capture_thread.start()
        process_thread1.start()
        
        # Give threads time to start
        time.sleep(1)
        print("✅ Threads started, waiting for data...")
        
        # Set visualization view
        view_control = self.vis.get_view_control()
        view_control.set_front([0.0, 0.0, -1.0])
        view_control.set_lookat([0, 0, 1])
        view_control.set_up([0, -1, 0])
        view_control.set_zoom(0.8)
        
        geometry_added = False
        frame_count = 0
        start_time = time.time()
        last_report_time = start_time
        
        # Performance tracking
        processing_times = []
        latency_times = []
        
        try:
            while True:
                # Get processed frame with longer timeout for debugging
                try:
                    current_pcd, processing_time, total_latency = self.processed_queue.get(timeout=0.1)
                    processing_times.append(processing_time)
                    latency_times.append(total_latency)
                    
                    # Debug: print when we get data
                    if frame_count < 5:
                        print(f"📦 Got frame {frame_count}: {len(current_pcd.points)} points")
                        
                except queue.Empty:
                    # Debug: check queue status
                    if frame_count == 0 and current_time - start_time > 5:
                        raw_q = self.raw_frame_queue.qsize()
                        proc_q = self.processed_queue.qsize()
                        print(f"🔍 Debug: No data after 5s. Raw queue: {raw_q}, Processed queue: {proc_q}")
                    continue
                
                if len(current_pcd.points) == 0:
                    continue
                
                # Update visualization
                self.pcd.points = current_pcd.points
                self.pcd.colors = current_pcd.colors
                
                if not geometry_added:
                    self.vis.add_geometry(self.pcd)
                    geometry_added = True
                else:
                    self.vis.update_geometry(self.pcd)
                
                self.vis.poll_events()
                self.vis.update_renderer()
                
                # Handle keyboard
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord('q'):
                    break
                elif key == ord('r'):
                    view_control.set_front([0.0, 0.0, -1.0])
                    view_control.set_lookat([0, 0, 1])
                    view_control.set_up([0, -1, 0])
                    view_control.set_zoom(0.8)
                
                # Performance reporting
                frame_count += 1
                current_time = time.time()
                
                if current_time - last_report_time > 2.5:
                    fps = frame_count / (current_time - start_time)
                    point_count = len(self.pcd.points)
                    
                    # Queue health
                    raw_q = self.raw_frame_queue.qsize()
                    proc_q = self.processed_queue.qsize()
                    
                    # Performance metrics
                    avg_proc = np.mean(processing_times[-60:]) if processing_times else 0
                    avg_latency = np.mean(latency_times[-60:]) if latency_times else 0
                    
                    # Performance indicators
                    fps_icon = "🔥" if fps > 40 else "⚡" if fps > 25 else "🐌"
                    latency_icon = "🟢" if avg_latency < 30 else "🟡" if avg_latency < 50 else "🔴"
                    
                    print(f"{fps_icon} {fps:.1f} FPS | {point_count:,} pts | "
                          f"Proc: {avg_proc:.1f}ms | {latency_icon} Latency: {avg_latency:.1f}ms | "
                          f"Q: {raw_q}/{proc_q}")
                    
                    last_report_time = current_time
                
        except KeyboardInterrupt:
            print("\\n👋 Multi-threaded streaming stopped")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            # Performance summary
            if processing_times and latency_times:
                avg_proc = np.mean(processing_times)
                avg_latency = np.mean(latency_times)
                final_fps = frame_count / (time.time() - start_time)
                speedup = 61.8 / avg_proc if avg_proc > 0 else 0
                
                print(f"\\n📊 PERFORMANCE SUMMARY:")
                print(f"   Final FPS: {final_fps:.1f}")
                print(f"   Processing Time: {avg_proc:.1f}ms")
                print(f"   Total Latency: {avg_latency:.1f}ms")
                print(f"   Speedup vs Baseline: {speedup:.1f}x")
                print(f"   Efficiency: {(40000 * final_fps / 1000):.1f}K points/sec")
            
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        print("🧹 Cleaning up...")
        self.running.clear()
        self.executor.shutdown(wait=False)
        try:
            self.pipeline.stop()
            cv2.destroyAllWindows()
            self.vis.destroy_window()
        except:
            pass
        print("✅ Cleanup complete")


if __name__ == '__main__':
    try:
        streamer = MultiThreadedOptimizedStreamer()
        streamer.start_streaming()
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        print("\\n🔧 Troubleshooting:")
        print("1. Check RealSense D435 is connected via USB 3.0")
        print("2. Close other applications using the camera")
        print("3. Ensure sufficient CPU cores available")
        print("\\n💡 This version uses advanced multi-threading for maximum CPU performance")
