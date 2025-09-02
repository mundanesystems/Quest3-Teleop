#!/usr/bin/env python3
"""
ZED2i OpenCV-based streaming server.

This streaming server uses OpenCV VideoCapture (like the ZED2i driver) instead of 
the ZED SDK. It captures side-by-side stereo images from a ZED2i camera using OpenCV,
splits them into left/right streams, and serves them over HTTP or UDP.

Features:
- OpenCV-based capture (no ZED SDK dependency)
- Side-by-side stereo splitting
- Multiple streaming protocols (HTTP/UDP)
- Configurable quality and frame rates
- Real-time performance monitoring
"""

import socket
import time
import cv2 as cv
import numpy as np
import struct
import threading
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import json

# CONFIGURATION
DEVICE_ID = 0  # ZED2i camera device ID
LISTEN_IP = '0.0.0.0'
UDP_PORT = 8082
HTTP_PORT = 8080
FRAME_WIDTH = 2560  # Full stereo width (1280x720 per eye)
FRAME_HEIGHT = 720
FPS = 60
JPEG_QUALITY = 90
CHUNK_SIZE = 60000  # 60 KB for UDP chunks

class ZED2iOpenCVStreamer:
    """
    ZED2i streaming server using OpenCV VideoCapture.
    Similar architecture to the ZED2i driver but for streaming instead of ROS publishing.
    """
    
    def __init__(self, device_id=DEVICE_ID, width=FRAME_WIDTH, height=FRAME_HEIGHT, fps=FPS):
        self.device_id = device_id
        self.frame_width = width
        self.frame_height = height
        self.fps = fps
        self.camera = None
        self.is_running = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.last_frame_time = 0.0
        
        # Performance tracking
        self.frame_count = 0
        self.fps_start_time = time.perf_counter()
        self.fps_frame_count = 0
        
        # Validate and adjust resolution for ZED2i
        self._validate_resolution()
    
    def _validate_resolution(self):
        """
        Validate and adjust resolution for ZED2i camera.
        ZED2i outputs side-by-side stereo, so actual camera resolutions are:
        - 2560x720 (1280x720 per eye)
        - 1344x376 (672x376 per eye)  
        - 3840x1080 (1920x1080 per eye)
        - 4416x1242 (2208x1242 per eye)
        """
        # Map single-eye resolutions to full stereo output
        zed_eye_to_stereo = {
            (1280, 720): (2560, 720),   # HD720 stereo
            (672, 376): (1344, 376),    # VGA stereo
            (1920, 1080): (3840, 1080), # HD1080 stereo
            (2208, 1242): (4416, 1242)  # 2K stereo
        }
        
        # Check if current resolution is already stereo
        if (self.frame_width, self.frame_height) in zed_eye_to_stereo.values():
            print(f"Using ZED2i stereo resolution: {self.frame_width}x{self.frame_height}")
            return
        
        # Check if it's a single-eye resolution that needs conversion
        requested = (self.frame_width, self.frame_height)
        if requested in zed_eye_to_stereo:
            self.frame_width, self.frame_height = zed_eye_to_stereo[requested]
            print(f"Converted to ZED2i stereo resolution: {self.frame_width}x{self.frame_height} for {requested} per eye")
        else:
            # Default to HD720 if requested resolution is not supported
            self.frame_width, self.frame_height = 2560, 720
            print(f"Requested resolution {requested} not supported by ZED2i. Using 2560x720 stereo (1280x720 per eye).")
    
    def start_camera(self):
        """Initialize and start the ZED2i camera using OpenCV."""
        # Try multiple device IDs in case ZED2i is not on device 0
        device_ids_to_try = [self.device_id, 1, 2, 3] if self.device_id == 0 else [self.device_id, 0, 1, 2, 3]
        
        for device_id in device_ids_to_try:
            try:
                print(f"Trying to open camera device {device_id}...")
                
                # Try to open with V4L2 backend first (Linux-specific)
                self.camera = cv.VideoCapture(device_id, cv.CAP_V4L2)
                if not self.camera.isOpened():
                    self.camera.release()
                    print(f"Failed to open device {device_id} with V4L2, trying default backend.")
                    self.camera = cv.VideoCapture(device_id)

                if self.camera.isOpened():
                    # Test if we can read a frame
                    ret, test_frame = self.camera.read()
                    if ret and test_frame is not None:
                        print(f"✅ Successfully opened camera device {device_id}")
                        print(f"Test frame shape: {test_frame.shape}")
                        
                        # Update the device_id to the working one
                        self.device_id = device_id
                        
                        # Configure camera settings
                        self._configure_camera()
                        
                        self.is_running = True
                        self.last_frame_time = time.time()
                        print(f"✅ Successfully started ZED2i camera capture on device {device_id}.")
                        return True
                    else:
                        print(f"Device {device_id} opened but couldn't read frame")
                        self.camera.release()
                else:
                    print(f"Could not open camera device {device_id}")

            except Exception as e:
                print(f"Error trying device {device_id}: {e}")
                if self.camera:
                    self.camera.release()
                continue
        
        print(f"❌ Failed to open any camera device. Tried devices: {device_ids_to_try}")
        return False
    
    def _configure_camera(self):
        """Configure ZED2i camera-specific settings."""
        # Set resolution - ZED2i outputs side-by-side stereo
        self.camera.set(cv.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.camera.set(cv.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        self.camera.set(cv.CAP_PROP_FPS, self.fps)
        
        # ZED2i specific settings (if supported by OpenCV backend)
        self.camera.set(cv.CAP_PROP_FOURCC, cv.VideoWriter_fourcc('Y', 'U', 'Y', 'V'))
        
        # Try to set buffer size to reduce latency
        self.camera.set(cv.CAP_PROP_BUFFERSIZE, 1)
        
        # Log actual settings achieved
        actual_width = int(self.camera.get(cv.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.camera.get(cv.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.camera.get(cv.CAP_PROP_FPS)
        
        print(f"ZED2i configured: {actual_width}x{actual_height} @ {actual_fps} fps")
        print(f"Output will be split into {actual_width//2}x{actual_height} per eye")
    
    def capture_frame(self):
        """Capture a single frame and split into left/right images."""
        if not self.camera or not self.is_running:
            return None, None, None
        
        ret, frame = self.camera.read()
        if not ret:
            print("Failed to capture frame from ZED2i")
            return None, None, None
        
        self.last_frame_time = time.time()
        
        # ZED2i outputs side-by-side stereo images
        # Split the frame into left and right images
        height, width = frame.shape[:2]
        single_width = width // 2
        
        if width % 2 != 0:
            print("Warning: Received frame width is not even")
            return None, None, None
        
        # Extract left and right images
        left_image = frame[:, :single_width]
        right_image = frame[:, single_width:]
        
        return frame, left_image, right_image
    
    def start_capture_loop(self):
        """Start the continuous capture loop in a separate thread."""
        def capture_loop():
            encode_param = [int(cv.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
            
            while self.is_running:
                try:
                    t0 = time.perf_counter()
                    
                    # Capture frame
                    stereo_frame, left_frame, right_frame = self.capture_frame()
                    if stereo_frame is None:
                        time.sleep(0.01)
                        continue
                    
                    t1 = time.perf_counter()
                    
                    # Encode to JPEG
                    result, frame_jpeg = cv.imencode('.jpg', stereo_frame, encode_param)
                    if not result:
                        continue
                    
                    t2 = time.perf_counter()
                    
                    # Update current frame for streaming
                    with self.frame_lock:
                        self.current_frame = frame_jpeg.tobytes()
                    
                    # Performance tracking
                    self.frame_count += 1
                    
                    self.fps_frame_count += 1
                    
                    # Log performance every 60 frames
                    if self.frame_count % 60 == 0:
                        fps_end_time = time.perf_counter()
                        fps = self.fps_frame_count / (fps_end_time - self.fps_start_time)
                        
                        capture_latency = (t1 - t0) * 1000
                        encode_latency = (t2 - t1) * 1000
                        total_latency = (t2 - t0) * 1000
                        
                        print("--- OpenCV Streamer Performance ---")
                        print(f"  FPS        : {fps:.1f}")
                        print(f"  Capture    : {capture_latency:.2f} ms")
                        print(f"  JPEG Encode: {encode_latency:.2f} ms")
                        print(f"  Total      : {total_latency:.2f} ms\n")
                        
                        # Reset FPS tracking
                        self.fps_start_time = time.perf_counter()
                        self.fps_frame_count = 0
                
                except Exception as e:
                    print(f"Error in capture loop: {e}")
                    break
        
        capture_thread = threading.Thread(target=capture_loop, daemon=True)
        capture_thread.start()
        return capture_thread
    
    def stop_camera(self):
        """Stop the camera and cleanup."""
        self.is_running = False
        if self.camera and self.camera.isOpened():
            self.camera.release()
        print("🛑 Stopped ZED2i camera.")


class HTTPStreamHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for streaming ZED2i frames."""
    
    def do_GET(self):
        """Handle HTTP GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/stream':
            self.stream_mjpeg()
        elif parsed_path.path == '/frame':
            self.serve_single_frame()
        elif parsed_path.path == '/status':
            self.serve_status()
        elif parsed_path.path == '/':
            self.serve_viewer()
        else:
            self.send_error(404)
    
    def stream_mjpeg(self):
        """Stream MJPEG video."""
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        
        try:
            while True:
                with streamer.frame_lock:
                    if streamer.current_frame is not None:
                        frame_data = streamer.current_frame
                    else:
                        continue
                
                self.wfile.write(b'--frame\r\n')
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(frame_data)))
                self.end_headers()
                self.wfile.write(frame_data)
                self.wfile.write(b'\r\n')
                
                time.sleep(1.0 / FPS)  # Control frame rate
        except Exception as e:
            print(f"Streaming error: {e}")
    
    def serve_single_frame(self):
        """Serve a single JPEG frame."""
        with streamer.frame_lock:
            if streamer.current_frame is not None:
                frame_data = streamer.current_frame
            else:
                self.send_error(503, "No frame available")
                return
        
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(frame_data)))
        self.end_headers()
        self.wfile.write(frame_data)
    
    def serve_status(self):
        """Serve status information as JSON."""
        status = {
            'running': streamer.is_running,
            'frame_count': streamer.frame_count,
            'last_frame_time': streamer.last_frame_time,
            'resolution': f"{streamer.frame_width}x{streamer.frame_height}",
            'fps_target': streamer.fps
        }
        
        response = json.dumps(status, indent=2)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response.encode())
    
    def serve_viewer(self):
        """Serve a simple HTML viewer."""
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>ZED2i OpenCV Stream</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; }
        img { max-width: 100%; border: 1px solid #ccc; }
        .controls { margin: 20px; }
        button { padding: 10px 20px; margin: 5px; }
    </style>
</head>
<body>
    <h1>ZED2i OpenCV Stream</h1>
    <img id="stream" src="/stream" alt="ZED2i Stream">
    <div class="controls">
        <button onclick="location.reload()">Refresh</button>
        <button onclick="window.open('/frame', '_blank')">Single Frame</button>
        <button onclick="window.open('/status', '_blank')">Status</button>
    </div>
    <p>Stream URL: <code>/stream</code> | Single frame: <code>/frame</code> | Status: <code>/status</code></p>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(html)))
        self.end_headers()
        self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass


def start_udp_server(streamer):
    """Start UDP streaming server."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, UDP_PORT))
    print(f"📹 UDP Server listening at {LISTEN_IP}:{UDP_PORT}")
    
    # Wait for client ping
    print("Waiting for UDP client ping...")
    data, client_address = sock.recvfrom(1024)
    print(f"✅ UDP Client connected from {client_address}")
    
    try:
        frame_id = 0
        while streamer.is_running:
            with streamer.frame_lock:
                if streamer.current_frame is not None:
                    frame_data = streamer.current_frame
                else:
                    time.sleep(0.01)
                    continue
            
            # Send frame in chunks
            total_size = len(frame_data)
            num_chunks = (total_size + CHUNK_SIZE - 1) // CHUNK_SIZE
            
            for i in range(num_chunks):
                start = i * CHUNK_SIZE
                end = start + CHUNK_SIZE
                chunk = frame_data[start:end]
                
                # Create header: [frame_id (4 bytes), chunk_index (1 byte), total_chunks (1 byte)]
                header = struct.pack('<IBB', frame_id, i, num_chunks)
                
                # Send header + chunk data
                sock.sendto(header + chunk, client_address)
            
            frame_id = (frame_id + 1) % 4294967295
            time.sleep(1.0 / FPS)  # Control frame rate
            
    except Exception as e:
        print(f"UDP streaming error: {e}")
    finally:
        sock.close()


def start_http_server():
    """Start HTTP streaming server."""
    with socketserver.TCPServer((LISTEN_IP, HTTP_PORT), HTTPStreamHandler) as httpd:
        print(f"🌐 HTTP Server listening at http://{LISTEN_IP}:{HTTP_PORT}")
        httpd.serve_forever()


def detect_cameras():
    """Detect available cameras and their properties."""
    print("🔍 Detecting available cameras...")
    available_cameras = []
    
    for i in range(10):  # Check first 10 device indices
        try:
            cap = cv.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv.CAP_PROP_FPS)
                    print(f"  Device {i}: {width}x{height} @ {fps} fps (Frame shape: {frame.shape})")
                    available_cameras.append(i)
                else:
                    print(f"  Device {i}: Opened but no frame available")
                cap.release()
            else:
                # Don't print for devices that don't exist
                pass
        except Exception as e:
            pass
    
    if not available_cameras:
        print("  ❌ No working cameras detected")
    else:
        print(f"  ✅ Found {len(available_cameras)} working camera(s): {available_cameras}")
    
    return available_cameras


def main():
    global streamer
    
    print("=== ZED2i OpenCV Streaming Server ===")
    print("Similar to ZED2i driver but for streaming instead of ROS")
    print()
    
    # Detect available cameras first
    available_cameras = detect_cameras()
    print()
    
    # Initialize streamer
    streamer = ZED2iOpenCVStreamer(
        device_id=DEVICE_ID,
        width=FRAME_WIDTH,
        height=FRAME_HEIGHT,
        fps=FPS
    )
    
    # Start camera
    if not streamer.start_camera():
        print("❌ Failed to start camera. Exiting.")
        return
    
    # Start capture loop
    capture_thread = streamer.start_capture_loop()
    
    try:
        # Start servers in separate threads
        udp_thread = threading.Thread(target=start_udp_server, args=(streamer,), daemon=True)
        http_thread = threading.Thread(target=start_http_server, daemon=True)
        
        udp_thread.start()
        http_thread.start()
        
        print()
        print("=== Streaming Started ===")
        print(f"HTTP Stream: http://localhost:{HTTP_PORT}/")
        print(f"MJPEG Stream: http://localhost:{HTTP_PORT}/stream")
        print(f"Single Frame: http://localhost:{HTTP_PORT}/frame")
        print(f"Status: http://localhost:{HTTP_PORT}/status")
        print(f"UDP Stream: {LISTEN_IP}:{UDP_PORT}")
        print()
        print("Press Ctrl+C to stop...")
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print('\n🛑 Streaming stopped by user.')
    finally:
        print("Cleaning up...")
        streamer.stop_camera()


if __name__ == "__main__":
    main()
