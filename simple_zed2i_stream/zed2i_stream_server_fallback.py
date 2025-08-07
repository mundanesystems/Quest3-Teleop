import cv2
import numpy as np
import socket
import struct
import argparse
import time
import threading

class ZED2iStreamServerFallback:
    """
    Fallback ZED2i streaming server using OpenCV instead of ZED SDK.
    This treats the ZED2i as a regular USB camera.
    """
    def __init__(self, host, port, ping_port, camera_index=0):
        self.host = host
        self.port = port
        self.ping_port = ping_port
        
        # Initialize camera using OpenCV
        self.cap = cv2.VideoCapture(camera_index)
        
        # Set camera properties - VR-friendly resolution with high quality
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)   # 720p width (VR-friendly)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)   # 720p height (VR-friendly)
        self.cap.set(cv2.CAP_PROP_FPS, 30)             # 30 FPS
        
        if not self.cap.isOpened():
            print(f"❌ Error: Could not open camera {camera_index}")
            # Try to find any available camera
            for i in range(5):
                test_cap = cv2.VideoCapture(i)
                if test_cap.isOpened():
                    print(f"📹 Found camera at index {i}")
                    test_cap.release()
                else:
                    print(f"❌ No camera at index {i}")
            exit(1)
        
        # Get actual camera properties
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        print(f"✅ ZED2i camera (OpenCV fallback) initialized successfully")
        print(f"   Resolution: {width}x{height}")
        print(f"   FPS: {fps}")
        
        # Setup TCP socket for video stream
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
                # Capture frame from camera
                ret, frame = self.cap.read()
                if not ret:
                    print("❌ Failed to capture frame")
                    continue
                
                # For ZED cameras, we typically get a side-by-side stereo image
                # We'll take the left half (left eye view)
                height, width = frame.shape[:2]
                if width > height * 1.5:  # Likely stereo image
                    frame = frame[:, :width//2]  # Take left half
                
                # Encode to JPEG with maximum quality
                result, encoded_frame = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                if not result:
                    continue
                
                data = encoded_frame.tobytes()
                
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
            # Clean up
            self.cap.release()
            self.conn.close()
            self.server_socket.close()
            self.ping_socket.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ZED2i Video Streaming Server (OpenCV Fallback)")
    parser.add_argument('--host', type=str, default='192.168.0.196', help='Host IP address to bind the server to.')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on for video stream.')
    parser.add_argument('--ping-port', type=int, default=8081, help='Port to listen on for UDP ping.')
    parser.add_argument('--camera', type=int, default=0, help='Camera index (0, 1, 2, etc.)')
    args = parser.parse_args()
    
    print("🔄 Using OpenCV fallback mode (ZED SDK not available)")
    print("   This treats the ZED2i as a regular USB camera")
    
    server = ZED2iStreamServerFallback(args.host, args.port, args.ping_port, args.camera)
    server.start_streaming()
