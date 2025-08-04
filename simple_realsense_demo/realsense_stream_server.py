import cv2
import numpy as np
import pyrealsense2 as rs
import socket
import struct
import argparse
import time
import threading

class RealSenseStreamServer:
    def __init__(self, host, port, ping_port):
        self.host = host
        self.port = port
        self.ping_port = ping_port
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        # Configure the stream
        self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
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
        self.pipeline.start(self.config)
        try:
            while True:
                frames = self.pipeline.wait_for_frames()
                color_frame = frames.get_color_frame()
                if not color_frame:
                    continue

                color_image = np.asanyarray(color_frame.get_data())
                
                # Encode to JPEG
                result, frame = cv2.imencode('.jpg', color_image, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
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
            self.pipeline.stop()
            self.conn.close()
            self.server_socket.close()
            self.ping_socket.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Intel RealSense Video Streaming Server")
    parser.add_argument('--host', type=str, default='192.168.0.196', help='Host IP address to bind the server to.')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on for video stream.')
    parser.add_argument('--ping-port', type=int, default=8081, help='Port to listen on for UDP ping.')
    args = parser.parse_args()
    
    server = RealSenseStreamServer(args.host, args.port, args.ping_port)
    server.start_streaming()
