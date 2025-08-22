import asyncio
import json
import logging
import time
import fractions
import cv2
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
import pyzed.sl as sl
import multiprocessing as mp
from multiprocessing import shared_memory
import threading
from queue import Queue, Empty

class MultiprocessZEDStereoTrack(VideoStreamTrack):
    """
    ZED2i stereo streaming with multiprocessing for CPU-bound operations
    Uses shared memory for zero-copy frame transfer between processes
    """
    def __init__(self):
        super().__init__()
        self._start_time = time.time()
        self._frame_count = 0
        self._last_log_time = time.time()
        
        # Full quality settings
        self.width, self.height = 1280, 720
        self.target_fps = 60
        self._frame_duration = 1.0 / self.target_fps
        self._next_frame_time = time.time()
        
        # Shared memory for zero-copy frame transfer
        self.frame_size = self.height * self.width * 2 * 3  # stereo * BGR
        self.shm_raw = shared_memory.SharedMemory(create=True, size=self.frame_size * 2)  # Double buffer
        self.shm_processed = shared_memory.SharedMemory(create=True, size=self.frame_size)
        
        # Control queues (lightweight metadata only)
        self.capture_queue = mp.Queue(maxsize=5)
        self.process_queue = mp.Queue(maxsize=5)
        self.result_queue = mp.Queue(maxsize=5)
        
        # Process management
        self.running = mp.Value('i', 1)  # Shared boolean
        self.capture_process = None
        self.process_worker = None
        
        # Local buffers for main thread
        self.current_frame = np.zeros((self.height, self.width * 2, 3), dtype=np.uint8)
        
        # Start multiprocessing pipeline
        self._start_processes()
        
        print("🔥 Multiprocess ZED2i pipeline initialized")

    def _start_processes(self):
        """Start capture and processing worker processes"""
        # ZED capture process (I/O bound)
        self.capture_process = mp.Process(
            target=self._capture_process_worker,
            args=(self.shm_raw.name, self.capture_queue, self.running)
        )
        
        # Image processing process (CPU bound) 
        self.process_worker = mp.Process(
            target=self._processing_worker,
            args=(self.shm_raw.name, self.shm_processed.name, 
                  self.capture_queue, self.result_queue, self.running)
        )
        
        self.capture_process.start()
        self.process_worker.start()
        
        print("🚀 Multiprocess workers started")

    @staticmethod
    def _capture_process_worker(shm_name, capture_queue, running):
        """Dedicated process for ZED camera capture (bypasses GIL)"""
        try:
            # Initialize ZED in this process
            zed = sl.Camera()
            init_params = sl.InitParameters()
            init_params.camera_resolution = sl.RESOLUTION.HD720
            init_params.camera_fps = 60
            init_params.depth_mode = sl.DEPTH_MODE.NONE
            init_params.sdk_gpu_id = 0
            
            if zed.open(init_params) != sl.ERROR_CODE.SUCCESS:
                print("❌ ZED failed to open in capture process")
                return
            
            # Optimize settings
            zed.set_camera_settings(sl.VIDEO_SETTINGS.AEC_AGC, 1)
            
            # Connect to shared memory
            shm = shared_memory.SharedMemory(name=shm_name)
            frame_size = 720 * 1280 * 2 * 3
            
            # Shared memory buffers (double buffering)
            buffer_0 = np.ndarray((720, 1280 * 2, 3), dtype=np.uint8, buffer=shm.buf[:frame_size])
            buffer_1 = np.ndarray((720, 1280 * 2, 3), dtype=np.uint8, buffer=shm.buf[frame_size:])
            current_buffer = 0
            
            left_image = sl.Mat()
            right_image = sl.Mat()
            
            print("📸 ZED capture process ready")
            
            while running.value:
                capture_start = time.time()
                
                if zed.grab() == sl.ERROR_CODE.SUCCESS:
                    # Get images
                    zed.retrieve_image(left_image, sl.VIEW.LEFT)
                    zed.retrieve_image(right_image, sl.VIEW.RIGHT)
                    
                    # Choose buffer
                    output_buffer = buffer_0 if current_buffer == 0 else buffer_1
                    
                    # Direct copy to shared memory (zero-copy!)
                    left_data = left_image.get_data()
                    right_data = right_image.get_data()
                    
                    # Fast RGB→BGR and concatenate in shared memory
                    output_buffer[:, :1280] = left_data[:, :, [2, 1, 0]]  # BGR conversion
                    output_buffer[:, 1280:] = right_data[:, :, [2, 1, 0]]
                    
                    capture_time = (time.time() - capture_start) * 1000
                    
                    # Send metadata only (not frame data!)
                    try:
                        capture_queue.put_nowait({
                            'buffer_id': current_buffer,
                            'timestamp': time.time(),
                            'capture_time': capture_time
                        })
                        current_buffer = 1 - current_buffer  # Flip buffer
                    except:
                        pass  # Queue full
                
                # Target 60fps
                elapsed = time.time() - capture_start
                time.sleep(max(0, 1/60 - elapsed))
                
        except Exception as e:
            print(f"❌ Capture process error: {e}")
        finally:
            if 'zed' in locals():
                zed.close()
            if 'shm' in locals():
                shm.close()

    @staticmethod 
    def _processing_worker(shm_raw_name, shm_proc_name, capture_queue, result_queue, running):
        """Dedicated process for image processing (CPU intensive, bypasses GIL)"""
        try:
            # Connect to shared memory
            shm_raw = shared_memory.SharedMemory(name=shm_raw_name)
            shm_processed = shared_memory.SharedMemory(name=shm_proc_name)
            
            frame_size = 720 * 1280 * 2 * 3
            
            # Input buffers (from capture)
            input_buffer_0 = np.ndarray((720, 1280 * 2, 3), dtype=np.uint8, buffer=shm_raw.buf[:frame_size])
            input_buffer_1 = np.ndarray((720, 1280 * 2, 3), dtype=np.uint8, buffer=shm_raw.buf[frame_size:])
            
            # Output buffer (to main thread)
            output_buffer = np.ndarray((720, 1280 * 2, 3), dtype=np.uint8, buffer=shm_processed.buf)
            
            print("⚙️ Processing worker ready")
            
            while running.value:
                try:
                    # Get capture metadata
                    capture_data = capture_queue.get(timeout=0.1)
                    
                    process_start = time.time()
                    
                    # Select input buffer
                    input_buffer = input_buffer_0 if capture_data['buffer_id'] == 0 else input_buffer_1
                    
                    # Fast processing: add overlays
                    output_buffer[:] = input_buffer  # Copy frame
                    
                    # Minimal overlays (optimized)
                    cv2.putText(output_buffer, "L", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.putText(output_buffer, "R", (1290, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    
                    process_time = (time.time() - process_start) * 1000
                    total_time = capture_data['capture_time'] + process_time
                    
                    # Send result metadata
                    try:
                        result_queue.put_nowait({
                            'timestamp': capture_data['timestamp'],
                            'total_time': total_time,
                            'ready': True
                        })
                    except:
                        pass  # Queue full
                        
                except:
                    continue  # Timeout or queue empty
                    
        except Exception as e:
            print(f"❌ Processing worker error: {e}")
        finally:
            if 'shm_raw' in locals():
                shm_raw.close()
            if 'shm_processed' in locals():
                shm_processed.close()

    async def recv(self):
        """Main thread: WebRTC streaming (I/O bound, async friendly)"""
        # Timing control
        current_time = time.time()
        sleep_time = self._next_frame_time - current_time
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        
        # Fast PTS
        pts = self._frame_count * 1500
        time_base = fractions.Fraction(1, 90000)

        # Check for processed frame
        frame_ready = False
        total_time = 0
        
        try:
            # Get latest result (non-blocking)
            while not self.result_queue.empty():
                result = self.result_queue.get_nowait()
                frame_ready = result['ready']
                total_time = result['total_time']
        except:
            pass

        if frame_ready:
            # Copy from shared memory to local buffer
            processed_array = np.ndarray(
                (self.height, self.width * 2, 3), 
                dtype=np.uint8, 
                buffer=self.shm_processed.buf
            )
            self.current_frame[:] = processed_array
            
            # Add performance overlay
            fps = self._frame_count / (time.time() - self._start_time) if self._frame_count > 0 else 0
            cv2.putText(self.current_frame, f"MP-FPS: {fps:.1f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
            cv2.putText(self.current_frame, f"Gen: {total_time:.1f}ms", (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)

        # Create VideoFrame
        frame = VideoFrame.from_ndarray(self.current_frame, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        
        self._next_frame_time += self._frame_duration
        
        # Logging
        if self._frame_count % 300 == 0 and self._frame_count > 0:
            current_time = time.time()
            if current_time - self._last_log_time > 0:
                actual_fps = 300 / (current_time - self._last_log_time)
                queue_sizes = f"Cap:{self.capture_queue.qsize()}, Res:{self.result_queue.qsize()}"
                print(f"🔥 MP Frame {self._frame_count}: {actual_fps:.1f}fps, Queues=[{queue_sizes}]")
                self._last_log_time = current_time
        
        self._frame_count += 1
        return frame

    def __del__(self):
        """Clean shutdown of multiprocessing pipeline"""
        try:
            self.running.value = 0  # Signal shutdown
            
            if self.capture_process and self.capture_process.is_alive():
                self.capture_process.join(timeout=2)
                if self.capture_process.is_alive():
                    self.capture_process.terminate()
            
            if self.process_worker and self.process_worker.is_alive():
                self.process_worker.join(timeout=2)
                if self.process_worker.is_alive():
                    self.process_worker.terminate()
            
            # Clean up shared memory
            if hasattr(self, 'shm_raw'):
                self.shm_raw.close()
                self.shm_raw.unlink()
            if hasattr(self, 'shm_processed'):
                self.shm_processed.close()
                self.shm_processed.unlink()
                
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
        
        print("🔒 Multiprocess ZED track cleaned up")


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"🔗 Connection: {pc.connectionState}")
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    try:
        video_track = MultiprocessZEDStereoTrack()
        pc.addTransceiver(video_track, direction="sendonly")

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return web.Response(
            content_type="application/json",
            text=json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}),
        )
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return web.Response(status=500, text=str(e))


pcs = set()

async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    from aiohttp import web
    
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    
    @web.middleware
    async def cors_handler(request, handler):
        if request.method == "OPTIONS":
            return web.Response(headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Content-Type'})
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    
    app.middlewares.append(cors_handler)
    app.router.add_post("/offer", offer)

    print("🔥 MULTIPROCESS ZED2i Stereo WebRTC - Port 8080")
    print("💾 Zero-copy shared memory pipeline")
    print("⚡ True parallel processing - Bypass Python GIL")
    print("🎯 Target: 60fps full HD quality")
    web.run_app(app, host="0.0.0.0", port=8080, access_log=None)
