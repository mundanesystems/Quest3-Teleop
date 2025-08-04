#!/usr/bin/env python3
"""
ULTRA-FAST THREADED Intel RealSense D435 Point Cloud Streaming
Combining Numba JIT + Advanced Multi-threading for Maximum Performance
Target: 30 FPS with rock-solid stability
"""

import numpy as np
import pyrealsense2 as rs
import cv2
import time
import open3d as o3d
from threading import Thread, Event, Lock
import queue
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp
try:
    from numba import jit
    NUMBA_AVAILABLE = True
    print("✅ Numba JIT available for maximum speed")
except ImportError:
    NUMBA_AVAILABLE = False
    print("⚠️  Numba not available, using optimized NumPy")


if NUMBA_AVAILABLE:
    @jit(nopython=True, parallel=True, fastmath=True)
    def jit_depth_to_points(depth_array, fx, fy, ppx, ppy, depth_scale, min_depth=0.1, max_depth=2.5):
        """Ultra-fast JIT-compiled depth to 3D points conversion"""
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


class UltraFastThreadedStreamer:
    def __init__(self):
        print("🚀 Initializing ULTRA-FAST THREADED RealSense D435...")
        
        # Pipeline setup
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        
        # Optimized resolution for best throughput
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
        
        # Ultra-minimal filtering for max speed
        self.align = rs.align(rs.stream.color)
        self.spatial = rs.spatial_filter()
        self.spatial.set_option(rs.option.filter_magnitude, 2)
        self.spatial.set_option(rs.option.filter_smooth_alpha, 0.5)
        
        # ADVANCED THREADING SETUP
        cpu_count = mp.cpu_count()
        self.num_workers = min(3, cpu_count - 1)  # Leave one core for main thread
        print(f"✅ Using {self.num_workers} worker threads on {cpu_count} CPU cores")
        
        # Multi-stage queues for maximum throughput
        self.raw_frame_queue = queue.Queue(maxsize=6)
        self.processing_queue = queue.Queue(maxsize=4)
        self.ready_queue = queue.Queue(maxsize=2)
        
        self.running = Event()
        self.running.set()
        
        # Thread pool for parallel point cloud processing
        self.executor = ThreadPoolExecutor(max_workers=self.num_workers)
        
        # Pre-compute coordinate grids for vectorized processing
        self._setup_coordinate_grids()
        
        # Visualization setup
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window("ULTRA-FAST Threaded RealSense Stream", width=1200, height=900)
        
        # Ultra-performance render settings
        render_option = self.vis.get_render_option()
        render_option.background_color = np.asarray([0.0, 0.0, 0.0])
        render_option.point_size = 1.0
        render_option.show_coordinate_frame = False
        render_option.light_on = False
        render_option.mesh_show_wireframe = False
        
        self.pcd = o3d.geometry.PointCloud()
        
        # Performance tracking
        self.perf_lock = Lock()
        self.frame_times = []
        self.processing_times = []
        
        # Pre-allocate buffers
        self.max_points = 50000
        
        print("🔥 ULTRA-FAST THREADED setup complete!")
    
    def _setup_coordinate_grids(self):
        """Pre-compute coordinate grids for vectorized operations"""
        print("🔧 Pre-computing coordinate grids for maximum speed...")
        
        # Create coordinate meshgrid
        i, j = np.meshgrid(np.arange(self.width), np.arange(self.height), indexing='xy')
        
        # Store as float32 for speed
        self.i_coords = i.astype(np.float32)
        self.j_coords = j.astype(np.float32)
        
        # Camera parameters as float32
        self.fx = np.float32(self.intrinsics.fx)
        self.fy = np.float32(self.intrinsics.fy)
        self.ppx = np.float32(self.intrinsics.ppx)
        self.ppy = np.float32(self.intrinsics.ppy)
        self.depth_scale_f32 = np.float32(self.depth_scale)
        
        print("✅ Coordinate grids ready")
    
    def _vectorized_depth_to_points(self, depth_image, color_image):
        """Ultra-optimized vectorized point cloud creation"""
        if NUMBA_AVAILABLE:
            # Use JIT-compiled version for maximum speed
            points_3d, valid_mask = jit_depth_to_points(
                depth_image, self.fx, self.fy, self.ppx, self.ppy, self.depth_scale
            )
            valid_points = points_3d[valid_mask]
            color_flat = color_image.reshape(-1, 3)[valid_mask] / 255.0
        else:
            # Fallback to vectorized NumPy
            depth_f32 = depth_image.astype(np.float32)
            z = depth_f32 * self.depth_scale_f32
            x = (self.i_coords - self.ppx) * z / self.fx
            y = (self.j_coords - self.ppy) * z / self.fy
            
            valid_mask = (z > 0.1) & (z < 2.5)
            valid_points = np.column_stack([x[valid_mask], -y[valid_mask], -z[valid_mask]])
            color_flat = color_image[valid_mask].astype(np.float32) / 255.0
        
        # Aggressive but smart downsampling
        if len(valid_points) > self.max_points:
            # Use systematic sampling for better distribution
            step = len(valid_points) // self.max_points
            indices = np.arange(0, len(valid_points), step)[:self.max_points]
            valid_points = valid_points[indices]
            color_flat = color_flat[indices]
        
        return valid_points, color_flat
    
    def _capture_worker(self):
        """Ultra-fast frame capture worker"""
        print("🎬 CAPTURE worker started")
        
        while self.running.is_set():
            try:
                # Fast frame capture
                frames = self.pipeline.wait_for_frames(timeout_ms=8)
                aligned_frames = self.align.process(frames)
                
                depth_frame = aligned_frames.get_depth_frame()
                color_frame = aligned_frames.get_color_frame()
                
                if depth_frame and color_frame:
                    # Minimal filtering
                    depth_frame = self.spatial.process(depth_frame)
                    
                    # Convert to numpy
                    color_image = np.asanyarray(color_frame.get_data())
                    depth_image = np.asanyarray(depth_frame.get_data())
                    
                    # Add timestamp for performance tracking
                    timestamp = time.perf_counter()
                    
                    # Add to processing queue
                    try:
                        self.raw_frame_queue.put((color_image, depth_image, timestamp), block=False)
                    except queue.Full:
                        # Drop oldest frame to prevent backlog
                        try:
                            self.raw_frame_queue.get_nowait()
                            self.raw_frame_queue.put((color_image, depth_image, timestamp), block=False)
                        except:
                            pass
                        
            except Exception:
                continue
    
    def _processing_worker(self, worker_id):
        """Ultra-fast point cloud processing worker"""
        print(f"🔧 PROCESS-{worker_id} worker started")
        
        while self.running.is_set():
            try:
                # Get frame data with longer timeout
                color_image, depth_image, capture_time = self.raw_frame_queue.get(timeout=0.2)
                
                # Start processing timer
                process_start = time.perf_counter()
                
                # Convert BGR to RGB
                color_rgb = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                
                # Ultra-fast point cloud creation
                points_3d, colors_rgb = self._vectorized_depth_to_points(depth_image, color_rgb)
                
                # Calculate processing time
                processing_time = (time.perf_counter() - process_start) * 1000
                total_latency = (time.perf_counter() - capture_time) * 1000
                
                # Debug: Print processing info
                if worker_id == 1 and len(points_3d) > 0:
                    print(f"🔧 Worker {worker_id}: Processed {len(points_3d)} points in {processing_time:.1f}ms")
                
                # Only proceed if we have valid points
                if len(points_3d) > 0:
                    # Create Open3D point cloud
                    pcd = o3d.geometry.PointCloud()
                    pcd.points = o3d.utility.Vector3dVector(points_3d.astype(np.float64))
                    pcd.colors = o3d.utility.Vector3dVector(colors_rgb.astype(np.float64))
                    
                    # Add to ready queue
                    try:
                        self.ready_queue.put((pcd, processing_time, total_latency), block=False)
                    except queue.Full:
                        # Drop oldest result
                        try:
                            self.ready_queue.get_nowait()
                            self.ready_queue.put((pcd, processing_time, total_latency), block=False)
                        except:
                            pass
                else:
                    print(f"⚠️  Worker {worker_id}: No valid points generated")
                        
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ Processing error in worker {worker_id}: {e}")
                continue
    
    def start_streaming(self):
        """Start ultra-fast threaded streaming"""
        jit_mode = "JIT + THREADING" if NUMBA_AVAILABLE else "VECTORIZED + THREADING"
        print(f"\\n⚡ ULTRA-FAST {jit_mode} MODE")
        print(f"📐 Resolution: {self.width}x{self.height} @ {self.fps}fps")
        print("🎯 Target: 30 FPS with advanced threading")
        print("🎯 Advanced Pipeline:")
        print("   Thread 1: Ultra-fast frame capture")
        print(f"   Threads 2-{self.num_workers+1}: Parallel point cloud processing")
        print("   Main Thread: Visualization")
        print("\\nControls:")
        print("  ESC/Q  - Quit")
        print("  R      - Reset view")
        print("  P      - Performance report")
        print("=" * 70)
        
        # Start worker threads
        capture_thread = Thread(target=self._capture_worker, daemon=True)
        
        # Start multiple processing workers
        process_threads = []
        for i in range(self.num_workers):
            thread = Thread(target=self._processing_worker, args=(i+1,), daemon=True)
            process_threads.append(thread)
        
        # Start all threads
        capture_thread.start()
        for thread in process_threads:
            thread.start()
        
        # Give threads time to start
        time.sleep(0.5)
        print("✅ All threads started, entering visualization loop...")
        
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
                # Get ready point cloud with longer timeout for debugging
                try:
                    current_pcd, processing_time, total_latency = self.ready_queue.get(timeout=0.1)
                    processing_times.append(processing_time)
                    latency_times.append(total_latency)
                    
                    # Debug first few frames
                    if frame_count < 5:
                        print(f"📦 Frame {frame_count}: {len(current_pcd.points)} points, "
                              f"proc: {processing_time:.1f}ms, latency: {total_latency:.1f}ms")
                        
                except queue.Empty:
                    # Debug: check what's happening
                    if frame_count == 0:
                        raw_q = self.raw_frame_queue.qsize()
                        ready_q = self.ready_queue.qsize()
                        current_time = time.time()
                        if current_time - start_time > 3:
                            print(f"🔍 Debug: No frames after 3s. Raw queue: {raw_q}, Ready queue: {ready_q}")
                            print("🔍 Checking if threads are running...")
                    continue
                
                if len(current_pcd.points) == 0:
                    continue
                
                # Ultra-fast visualization update
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
                elif key == ord('p'):
                    self._print_performance_report(processing_times, latency_times, frame_count, start_time)
                
                # Performance monitoring
                frame_count += 1
                current_time = time.time()
                
                if current_time - last_report_time > 2.0:
                    fps = frame_count / (current_time - start_time)
                    point_count = len(self.pcd.points)
                    
                    # Queue health check
                    raw_q = self.raw_frame_queue.qsize()
                    ready_q = self.ready_queue.qsize()
                    
                    # Performance metrics
                    avg_proc = np.mean(processing_times[-60:]) if processing_times else 0
                    avg_latency = np.mean(latency_times[-60:]) if latency_times else 0
                    
                    # Performance indicators
                    fps_icon = "🔥" if fps > 25 else "⚡" if fps > 20 else "🐌"
                    latency_icon = "🟢" if avg_latency < 25 else "🟡" if avg_latency < 50 else "🔴"
                    mode_icon = "🚀" if NUMBA_AVAILABLE else "💻"
                    
                    print(f"{fps_icon} {fps:.1f} FPS | {point_count:,} pts | "
                          f"{mode_icon} Proc: {avg_proc:.1f}ms | {latency_icon} Lat: {avg_latency:.1f}ms | "
                          f"Q: {raw_q}/{ready_q}")
                    
                    last_report_time = current_time
                
        except KeyboardInterrupt:
            print("\\n👋 Ultra-fast threaded streaming stopped")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            # Final performance report
            self._print_final_performance_report(processing_times, latency_times, frame_count, start_time)
            self.cleanup()
    
    def _print_performance_report(self, processing_times, latency_times, frame_count, start_time):
        """Print detailed performance analysis"""
        if not processing_times:
            return
            
        print("\\n" + "="*60)
        print("📊 REAL-TIME PERFORMANCE ANALYSIS")
        print("="*60)
        
        avg_proc = np.mean(processing_times[-100:])
        avg_latency = np.mean(latency_times[-100:])
        current_fps = frame_count / (time.time() - start_time)
        
        print(f"Current FPS: {current_fps:.1f}")
        print(f"Processing Time: {avg_proc:.1f}ms (avg of last 100 frames)")
        print(f"Total Latency: {avg_latency:.1f}ms")
        print(f"Theoretical Max FPS: {1000/avg_proc:.1f}")
        print(f"Mode: {'Numba JIT + Threading' if NUMBA_AVAILABLE else 'Vectorized + Threading'}")
        print(f"Workers: {self.num_workers} processing threads")
        print("="*60)
    
    def _print_final_performance_report(self, processing_times, latency_times, frame_count, start_time):
        """Print final performance summary"""
        if not processing_times:
            return
            
        avg_proc = np.mean(processing_times)
        avg_latency = np.mean(latency_times)
        final_fps = frame_count / (time.time() - start_time)
        
        # Calculate speedup vs baseline
        baseline_time = 61.8  # From our earlier analysis
        speedup = baseline_time / avg_proc if avg_proc > 0 else 0
        
        print(f"\\n📊 FINAL PERFORMANCE SUMMARY:")
        print(f"   Mode: {'Numba JIT + Threading' if NUMBA_AVAILABLE else 'Vectorized + Threading'}")
        print(f"   Workers: {self.num_workers} processing threads")
        print(f"   Final FPS: {final_fps:.1f}")
        print(f"   Processing Time: {avg_proc:.1f}ms")
        print(f"   Total Latency: {avg_latency:.1f}ms")
        print(f"   Speedup vs Baseline: {speedup:.1f}x")
        print(f"   Throughput: {(self.max_points * final_fps / 1000):.1f}K points/sec")
    
    def cleanup(self):
        """Clean up resources"""
        print("🧹 Cleaning up ultra-fast threaded streamer...")
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
        streamer = UltraFastThreadedStreamer()
        streamer.start_streaming()
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        print("\\n🔧 Troubleshooting:")
        print("1. Check RealSense D435 is connected via USB 3.0")
        print("2. For maximum speed: pip install numba")
        print("3. Close other applications using the camera")
        print("4. Ensure sufficient CPU cores available")
        print("\\n💡 This version combines JIT compilation with advanced threading")
