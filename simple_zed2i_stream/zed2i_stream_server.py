import cv2
import numpy as np
import sys
import os

# Try multiple ways to import ZED SDK
try:
    import pyzed.sl as sl
    print("✅ Found pyzed via pip installation")
except ImportError as e:
    print(f"Initial import failed: {e}")
    # Try adding common ZED SDK paths (user confirmed location first)
    possible_paths = [
        r"C:\Program Files (x86)\ZED SDK\lib",  # User confirmed location
        r"C:\Program Files\ZED SDK\lib",
        r"C:\Program Files (x86)\ZED SDK\python",
        r"C:\Program Files\ZED SDK\python"
    ]
    
    zed_found = False
    for path in possible_paths:
        if os.path.exists(path):
            sys.path.append(path)
            try:
                import pyzed.sl as sl
                print(f"✅ Found ZED SDK at: {path}")
                zed_found = True
                break
            except ImportError:
                continue
    
    if not zed_found:
        print("❌ Could not find ZED Python API (pyzed)")
        print("Please try: pip install pyzed")
        print("Or check ZED SDK installation paths:")
        for path in possible_paths:
            print(f"  - {path}")
        exit(1)

import socket
import struct
import argparse
import time
import threading

class ZED2iStreamServer:
    def __init__(self, host, port, ping_port):
        self.host = host
        self.port = port
        self.ping_port = ping_port
        
        # Initialize ZED camera
        self.zed = sl.Camera()
        
        # Create a InitParameters object and set configuration parameters
        self.init_params = sl.InitParameters()
        self.init_params.camera_resolution = sl.RESOLUTION.HD720  # 720p resolution
        self.init_params.camera_fps = 30  # 30 FPS
        self.init_params.depth_mode = sl.DEPTH_MODE.PERFORMANCE  # Use PERFORMANCE depth mode for speed
        
        # Open the camera
        err = self.zed.open(self.init_params)
        if err != sl.ERROR_CODE.SUCCESS:
            print(f"❌ Error opening ZED camera: {err}")
            exit(1)
        
        print("✅ ZED2i camera initialized successfully")
        
        # Create Mat objects to store images
        self.image = sl.Mat()
        self.runtime_parameters = sl.RuntimeParameters()
        
        # Setup TCP socket for video stream
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        print(f"📹 Video stream listening for a client at {self.host}:{self.port}")
        
        # Setup UDP socket for ping
        self.ping_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ping_socket.bind((self.host, self.ping_port))
        print(f"📡 Ping measurement listening on UDP port {self.ping_port}")

        self.conn, self.addr = self.server_socket.accept()
        print(f"✅ Video client connected from {self.addr}")
        
        # Start the ping thread
        self.ping_thread = threading.Thread(target=self.handle_ping)
        self.ping_thread.daemon = True
        self.ping_thread.start()

    def handle_ping(self):
        """Handles sending pings and measuring RTT"""
        ping_client_addr = None
        while True:
            try:
                if ping_client_addr is None:
                    # Wait for the first ping from the client to discover its address
                    print("Waiting for initial ping from client to establish UDP connection...")
                    ping_data, ping_client_addr = self.ping_socket.recvfrom(1024)
                    print(f"✅ Ping client registered from {ping_client_addr}")
                    continue

                # Send a ping with the current timestamp
                timestamp = time.time()
                message = struct.pack('<d', timestamp)
                self.ping_socket.sendto(message, ping_client_addr)

                # Wait for the response
                self.ping_socket.settimeout(1.0) # 1 second timeout
                response, _ = self.ping_socket.recvfrom(1024)
                
                # Calculate RTT
                rtt = (time.time() - timestamp) * 1000
                print(f"🚀 Round-trip latency: {rtt:.2f} ms")

            except socket.timeout:
                print("⚠️ Ping response timed out.")
                ping_client_addr = None # Reset and wait for a new client
            except Exception as e:
                print(f"Error in ping thread: {e}")
                ping_client_addr = None
            
            time.sleep(2) # Ping every 2 seconds

    def start_streaming(self):
        try:
            while True:
                # Grab an image
                if self.zed.grab(self.runtime_parameters) == sl.ERROR_CODE.SUCCESS:
                    # Retrieve the left image
                    self.zed.retrieve_image(self.image, sl.VIEW.LEFT)
                    
                    # Convert to OpenCV format (BGR)
                    image_ocv = self.image.get_data()
                    
                    # Convert from RGBA to BGR (OpenCV format)
                    if image_ocv.shape[2] == 4:  # RGBA
                        image_bgr = cv2.cvtColor(image_ocv, cv2.COLOR_RGBA2BGR)
                    else:  # RGB
                        image_bgr = cv2.cvtColor(image_ocv, cv2.COLOR_RGB2BGR)
                    
                    # Encode to JPEG
                    result, frame = cv2.imencode('.jpg', image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                    if not result:
                        continue
                    
                    data = frame.tobytes()
                    
                    # Pack just the data size
                    header = struct.pack('<I', len(data))

                    # Send header and then data
                    try:
                        self.conn.sendall(header + data)
                    except (ConnectionResetError, ConnectionAbortedError):
                        print("Client disconnected. Waiting for a new connection...")
                        self.conn, self.addr = self.server_socket.accept()
                        print(f"Reconnected to {self.addr}")

        finally:
            # Close the camera
            self.zed.close()
            self.conn.close()
            self.server_socket.close()
            self.ping_socket.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ZED2i Video Streaming Server")
    parser.add_argument('--host', type=str, default='192.168.0.196', help='Host IP address to bind the server to.')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on for video stream.')
    parser.add_argument('--ping-port', type=int, default=8081, help='Port to listen on for UDP ping.')
    args = parser.parse_args()
    
    server = ZED2iStreamServer(args.host, args.port, args.ping_port)
    server.start_streaming()
