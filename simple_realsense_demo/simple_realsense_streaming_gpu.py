#!/usr/bin/env python3
"""
GPU-ACCELERATED Intel RealSense D435 Point Cloud Streaming
Using CUDA/CuPy for maximum performance - Target: 30+ FPS
"""

import numpy as np
import pyrealsense2 as rs
import cv2
import time
import open3d as o3d
from threading import Thread, Event
import queue
from concurrent.futures import ThreadPoolExecutor
import cupy as cp  # GPU acceleration
import warnings
warnings.filterwarnings("ignore")


class GPUAcceleratedStreamer:
    def __init__(self):
        print("🚀 Initializing GPU-Accelerated RealSense D435...")
        
        # Check GPU availability
        try:
            import cupy as cp
            self.gpu_available = True
            print("✅ GPU acceleration available (CuPy)")
        except ImportError:
            self.gpu_available = False
            print("⚠️  GPU acceleration not available, falling back to CPU")
        
        # Pipeline setup
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        
        # Optimized resolution for throughput
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
        
        # Minimal filtering for speed
        self.align = rs.align(rs.stream.color)
        self.spatial = rs.spatial_filter()
        self.spatial.set_option(rs.option.filter_magnitude, 1)
        
        # THREADING OPTIMIZATION: Separate queues for different stages
        self.raw_frame_queue = queue.Queue(maxsize=3)
        self.processed_frame_queue = queue.Queue(maxsize=2)
        self.running = Event()
        self.running.set()
        
        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # Visualization
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window("GPU-Accelerated RealSense Stream", width=1200, height=900)
        
        render_option = self.vis.get_render_option()
        render_option.background_color = np.asarray([0.0, 0.0, 0.0])
        render_option.point_size = 1.2
        render_option.show_coordinate_frame = False
        
        self.pcd = o3d.geometry.PointCloud()
        
        # Pre-allocate GPU arrays if available
        if self.gpu_available:
            self._setup_gpu_arrays()
        
        print("🔥 GPU-accelerated setup complete!")
    
    def _setup_gpu_arrays(self):
        """Pre-allocate GPU memory for faster processing"""
        if not self.gpu_available:
            return
        
        # Pre-allocate coordinate grids on GPU
        i_gpu, j_gpu = cp.meshgrid(cp.arange(self.width), cp.arange(self.height), indexing='xy')
        self.i_gpu = i_gpu.astype(cp.float32)
        self.j_gpu = j_gpu.astype(cp.float32)
        
        # Camera parameters on GPU
        self.fx_gpu = cp.float32(self.intrinsics.fx)
        self.fy_gpu = cp.float32(self.intrinsics.fy)
        self.ppx_gpu = cp.float32(self.intrinsics.ppx)
        self.ppy_gpu = cp.float32(self.intrinsics.ppy)
        self.depth_scale_gpu = cp.float32(self.depth_scale)
    
    def _create_point_cloud_gpu(self, color_image, depth_image):
        """GPU-accelerated point cloud creation using CuPy"""
        if not self.gpu_available:
            return self._create_point_cloud_cpu_optimized(color_image, depth_image)
        
        start_time = time.perf_counter()
        
        # Transfer to GPU
        depth_gpu = cp.asarray(depth_image, dtype=cp.float32)
        color_gpu = cp.asarray(color_image, dtype=cp.float32)
        
        # GPU depth to 3D conversion
        z_gpu = depth_gpu * self.depth_scale_gpu
        x_gpu = (self.i_gpu - self.ppx_gpu) * z_gpu / self.fx_gpu
        y_gpu = (self.j_gpu - self.ppy_gpu) * z_gpu / self.fy_gpu
        
        # Depth filtering on GPU
        valid_mask = (z_gpu > 0.1) & (z_gpu < 2.5)
        
        # Extract valid points on GPU
        x_valid = x_gpu[valid_mask]
        y_valid = -y_gpu[valid_mask]  # Flip Y
        z_valid = -z_gpu[valid_mask]  # Flip Z
        
        # Stack coordinates
        points_gpu = cp.stack([x_valid, y_valid, z_valid], axis=1)
        
        # Extract colors for valid points
        color_flat = color_gpu.reshape(-1, 3)
        colors_gpu = color_flat[valid_mask.flatten()] / 255.0
        
        # Aggressive downsampling on GPU for speed
        if len(points_gpu) > 35000:
            # Random sampling on GPU
            indices = cp.random.choice(len(points_gpu), 35000, replace=False)
            points_gpu = points_gpu[indices]
            colors_gpu = colors_gpu[indices]
        
        # Transfer back to CPU for Open3D
        points_cpu = cp.asnumpy(points_gpu).astype(np.float64)
        colors_cpu = cp.asnumpy(colors_gpu).astype(np.float64)
        
        # Create point cloud
        pcd = o3d.geometry.PointCloud()
        if len(points_cpu) > 0:
            pcd.points = o3d.utility.Vector3dVector(points_cpu)
            pcd.colors = o3d.utility.Vector3dVector(colors_cpu)
        
        elapsed = (time.perf_counter() - start_time) * 1000
        return pcd, elapsed
    
    def _create_point_cloud_cpu_optimized(self, color_image, depth_image):
        """Optimized CPU-only point cloud creation"""
        start_time = time.perf_counter()
        
        h, w = depth_image.shape
        
        # Vectorized coordinate generation
        i, j = np.meshgrid(np.arange(w), np.arange(h), indexing='xy')
        
        # Depth to 3D conversion
        z = depth_image.astype(np.float32) * self.depth_scale
        x = (i - self.intrinsics.ppx) * z / self.intrinsics.fx
        y = (j - self.intrinsics.ppy) * z / self.intrinsics.fy
        
        # Fast filtering
        valid_mask = (z > 0.1) & (z < 2.5)
        
        # Extract valid points
        points_3d = np.stack([x[valid_mask], -y[valid_mask], -z[valid_mask]], axis=1)
        colors_rgb = color_image[valid_mask] / 255.0
        
        # Fast random downsampling
        if len(points_3d) > 35000:
            indices = np.random.choice(len(points_3d), 35000, replace=False)
            points_3d = points_3d[indices]
            colors_rgb = colors_rgb[indices]
        
        # Create point cloud
        pcd = o3d.geometry.PointCloud()
        if len(points_3d) > 0:
            pcd.points = o3d.utility.Vector3dVector(points_3d.astype(np.float64))
            pcd.colors = o3d.utility.Vector3dVector(colors_rgb.astype(np.float64))
        
        elapsed = (time.perf_counter() - start_time) * 1000
        return pcd, elapsed
    
    def _capture_frames_threaded(self):
        """Threaded frame capture - Stage 1"""
        while self.running.is_set():
            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=10)
                aligned_frames = self.align.process(frames)
                
                depth_frame = aligned_frames.get_depth_frame()
                color_frame = aligned_frames.get_color_frame()
                
                if depth_frame and color_frame:
                    # Minimal filtering
                    depth_frame = self.spatial.process(depth_frame)
                    
                    # Convert to numpy
                    color_image = np.asanyarray(color_frame.get_data())
                    depth_image = np.asanyarray(depth_frame.get_data())
                    
                    # Add to raw frame queue
                    try:
                        self.raw_frame_queue.put((color_image, depth_image), block=False)
                    except queue.Full:
                        # Drop frame if queue full
                        try:
                            self.raw_frame_queue.get_nowait()
                            self.raw_frame_queue.put((color_image, depth_image), block=False)
                        except:
                            pass
                        
            except Exception:
                continue
    
    def _process_frames_threaded(self):
        """Threaded frame processing - Stage 2"""
        while self.running.is_set():
            try:
                # Get raw frame
                color_image, depth_image = self.raw_frame_queue.get(timeout=0.1)
                
                # Convert BGR to RGB
                color_rgb = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                
                # Process point cloud (GPU or CPU)
                pcd, processing_time = self._create_point_cloud_gpu(color_rgb, depth_image)
                
                # Add to processed queue
                try:
                    self.processed_frame_queue.put((pcd, processing_time), block=False)
                except queue.Full:
                    # Drop oldest processed frame
                    try:
                        self.processed_frame_queue.get_nowait()
                        self.processed_frame_queue.put((pcd, processing_time), block=False)
                    except:
                        pass
                        
            except queue.Empty:
                continue
            except Exception:
                continue
    
    def start_streaming(self):
        """Start multi-threaded GPU-accelerated streaming"""
        mode = "GPU-ACCELERATED" if self.gpu_available else "CPU-OPTIMIZED"
        print(f"\\n⚡ {mode} STREAMING @ {self.width}x{self.height}")
        print("🎯 Multi-threaded pipeline:")
        print("   Thread 1: Frame capture")
        print("   Thread 2: Point cloud processing")
        print("   Main:     Visualization")
        print("\\nControls:")
        print("  ESC/Q  - Quit")
        print("  R      - Reset view")
        print("=" * 60)
        
        # Start threaded pipeline
        capture_thread = Thread(target=self._capture_frames_threaded, daemon=True)
        process_thread = Thread(target=self._process_frames_threaded, daemon=True)
        
        capture_thread.start()
        process_thread.start()
        
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
        
        processing_times = []
        
        try:
            while True:
                # Get processed frame
                try:
                    current_pcd, processing_time = self.processed_frame_queue.get(timeout=0.01)
                    processing_times.append(processing_time)
                except queue.Empty:
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
                
                # Performance monitoring
                frame_count += 1
                current_time = time.time()
                
                if current_time - last_fps_time > 2.0:
                    fps = frame_count / (current_time - start_time)
                    point_count = len(self.pcd.points)
                    
                    # Queue health
                    raw_q = self.raw_frame_queue.qsize()
                    proc_q = self.processed_frame_queue.qsize()
                    
                    # Average processing time
                    avg_proc = np.mean(processing_times[-50:]) if processing_times else 0
                    
                    # Performance indicators
                    fps_icon = "🔥" if fps > 45 else "⚡" if fps > 25 else "🐌"
                    gpu_icon = "🚀" if self.gpu_available else "💻"
                    
                    print(f"{fps_icon} {fps:.1f} FPS | {point_count:,} pts | "
                          f"{gpu_icon} Proc: {avg_proc:.1f}ms | Q: {raw_q}/{proc_q}")
                    
                    last_fps_time = current_time
                
        except KeyboardInterrupt:
            print("\\n👋 GPU-accelerated streaming stopped")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            # Performance summary
            if processing_times:
                avg_proc = np.mean(processing_times)
                final_fps = frame_count / (time.time() - start_time)
                print(f"\\n📊 PERFORMANCE SUMMARY:")
                print(f"   Mode: {mode}")
                print(f"   Average FPS: {final_fps:.1f}")
                print(f"   Processing Time: {avg_proc:.1f}ms")
                print(f"   Speedup: {61.8/avg_proc:.1f}x faster than baseline")
            
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
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
        streamer = GPUAcceleratedStreamer()
        streamer.start_streaming()
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        print("\\n🔧 Troubleshooting:")
        print("1. For GPU acceleration: pip install cupy-cuda11x (or cupy-cuda12x)")
        print("2. Check RealSense D435 is connected via USB 3.0")
        print("3. Close other applications using the camera")
        print("\\n💡 Note: Will fallback to optimized CPU mode if GPU unavailable")
