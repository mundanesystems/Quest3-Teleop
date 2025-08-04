import cv2
import numpy as np
import pyrealsense2 as rs
import socket
import struct
import argparse

class RealSenseStreamServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        # Configure the stream
        self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        print(f"Listening for a client at {self.host}:{self.port}")
        self.conn, self.addr = self.server_socket.accept()
        print(f"Connected by {self.addr}")

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
                
                # Send data size and then data
                try:
                    self.conn.sendall(struct.pack('<L', len(data)) + data)
                except (ConnectionResetError, ConnectionAbortedError):
                    print("Client disconnected. Waiting for a new connection...")
                    self.conn, self.addr = self.server_socket.accept()
                    print(f"Reconnected to {self.addr}")


        finally:
            self.pipeline.stop()
            self.conn.close()
            self.server_socket.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Intel RealSense Video Streaming Server")
    parser.add_argument('--host', type=str, default='192.168.0.196', help='Host IP address to bind the server to.')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on.')
    args = parser.parse_args()
    
    server = RealSenseStreamServer(args.host, args.port)
    server.start_streaming()
