import socket
import time
import cv2
import numpy as np
import pyzed.sl as sl
import struct

# CONFIGURATION
LISTEN_IP = '0.0.0.0'
UDP_PORT = 8080
RESOLUTION = sl.RESOLUTION.HD720
FPS = 60 # A more reasonable target for UDP streaming
JPEG_QUALITY = 60 # Lower quality = smaller packets = less chance of loss
CHUNK_SIZE = 60000 # 60 KB, safely below the 64KB UDP limit

def main():
    print("Initializing ZED camera...")
    zed = sl.Camera()
    init_params = sl.InitParameters()
    init_params.camera_resolution = RESOLUTION
    init_params.camera_fps = FPS
    init_params.depth_mode = sl.DEPTH_MODE.NONE
    if zed.open(init_params) != sl.ERROR_CODE.SUCCESS:
        print('❌ Failed to open ZED camera!')
        exit(1)

    # --- Create UDP Socket ---
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, UDP_PORT))
    print(f"📹 UDP Server listening at {LISTEN_IP}:{UDP_PORT}")

    # --- Handshake: Wait for a ping from the client to get its address ---
    print("Waiting for a ping from the client...")
    data, client_address = sock.recvfrom(1024)
    print(f"✅ Client connected from {client_address}")

    try:
        left_image, right_image = sl.Mat(), sl.Mat()
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        frame_id = 0

        # Latency check variables
        frame_count = 0
        LOG_INTERVAL = 60 # Print a report every 60 frames
        
        # FPS tracking variables
        fps_start_time = time.perf_counter()
        fps_frame_count = 0

        while True:
            t0 = time.perf_counter()
            if zed.grab() == sl.ERROR_CODE.SUCCESS:
                t1 = time.perf_counter() # time after grab

                zed.retrieve_image(left_image, sl.VIEW.LEFT)
                zed.retrieve_image(right_image, sl.VIEW.RIGHT)
                t2 = time.perf_counter() # time after retrieve

                sbs_image = np.concatenate((left_image.get_data(), right_image.get_data()), axis=1)
                t3 = time.perf_counter() # time after stitch

                result, frame_jpeg = cv2.imencode('.jpg', sbs_image, encode_param)
                if not result: continue
                t4 = time.perf_counter() # time after encode

                frame_data = frame_jpeg.tobytes()
                total_size = len(frame_data)
                num_chunks = (total_size + CHUNK_SIZE - 1) // CHUNK_SIZE
                
                # --- Send the frame in chunks ---
                for i in range(num_chunks):
                    t5 = time.perf_counter() # time before send
                    start = i * CHUNK_SIZE
                    end = start + CHUNK_SIZE
                    chunk = frame_data[start:end]
                    
                    # Create a header: [frame_id (4 bytes), chunk_index (1 byte), total_chunks (1 byte)]
                    header = struct.pack('<IBB', frame_id, i, num_chunks)
                    
                    # Send header + chunk data
                    sock.sendto(header + chunk, client_address)
                    t6 = time.perf_counter() # time after send chunk
                t7 = time.perf_counter() # time after send

                frame_id = (frame_id + 1) % 4294967295 # Loop frame_id
                # --- Log latency values periodically ---
                frame_count += 1
                fps_frame_count += 1
                
                if frame_count % LOG_INTERVAL == 0:
                    # Calculate FPS
                    fps_end_time = time.perf_counter()
                    fps = fps_frame_count / (fps_end_time - fps_start_time)
                    
                    grab_latency = (t1 - t0) * 1000
                    retrieve_latency = (t2 - t1) * 1000
                    stitch_latency = (t3 - t2) * 1000
                    encode_latency = (t4 - t3) * 1000
                    chunk_send_latency = (t6 - t5) * 1000
                    send_latency = (t7 - t4) * 1000
                    total_latency = (t7 - t0) * 1000

                    print("--- Server Performance Report ---")
                    print(f"  FPS        : {fps:.1f}")
                    print(f"  Grab       : {grab_latency:.2f} ms")
                    print(f" Retrieve   : {retrieve_latency:.2f} ms")
                    print(f"  Stitching  : {stitch_latency:.2f} ms")
                    print(f"  JPEG Encode: {encode_latency:.2f} ms")
                    print(f"  Chunk Send : {chunk_send_latency:.2f} ms")
                    print(f"  Send       : {send_latency:.2f} ms")
                    print(f"  ---------------------------")
                    print(f"  Total Server : {total_latency:.2f} ms\n")
                    
                    # Reset FPS tracking
                    fps_start_time = time.perf_counter()
                    fps_frame_count = 0
                
    except KeyboardInterrupt:
        print('\n🛑 Streaming stopped by user.')
    finally:
        print("Cleaning up...")
        sock.close()
        zed.close()

if __name__ == "__main__":
    main()