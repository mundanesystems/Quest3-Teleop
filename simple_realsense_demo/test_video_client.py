#!/usr/bin/env python3
"""
Simple test client to verify video streaming server connectivity
"""

import socket
import struct
import time

def test_video_connection():
    """Test connection to video streaming server"""
    server_host = "192.168.0.196"
    server_port = 8080
    
    print(f"🧪 Testing connection to video server at {server_host}:{server_port}")
    
    try:
        # Create socket and connect
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(5.0)  # 5 second timeout
        
        print("🔄 Attempting to connect...")
        client_socket.connect((server_host, server_port))
        print("✅ Connected successfully!")
        
        # Try to receive some data
        print("📥 Waiting for frame data...")
        
        # Read frame size (4 bytes)
        size_data = client_socket.recv(4)
        if len(size_data) == 4:
            frame_size = struct.unpack('<L', size_data)[0]
            print(f"📦 Received frame size: {frame_size} bytes")
            
            # Read a small portion of the frame data
            received_data = 0
            max_to_read = min(1024, frame_size)  # Read max 1KB for test
            
            while received_data < max_to_read:
                chunk = client_socket.recv(min(512, max_to_read - received_data))
                if not chunk:
                    break
                received_data += len(chunk)
            
            print(f"📊 Successfully received {received_data} bytes of frame data")
            print("🎉 Video streaming server is working correctly!")
            
        else:
            print("❌ Did not receive frame size data")
            
    except socket.timeout:
        print("⏰ Connection timed out - server may not be running")
    except ConnectionRefusedError:
        print("❌ Connection refused - server is not listening on this port")
    except Exception as e:
        print(f"❌ Connection error: {e}")
    finally:
        try:
            client_socket.close()
        except:
            pass

if __name__ == "__main__":
    test_video_connection()
