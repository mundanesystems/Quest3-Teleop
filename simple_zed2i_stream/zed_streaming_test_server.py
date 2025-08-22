
import socket
import time
import cv2
import numpy as np
import pyzed.sl as sl
import struct
import argparse

# --- CONFIGURATION MAPPINGS ---
# Defines settings for each performance mode
MODES = {
    "high_res": {
        "resolution": sl.RESOLUTION.HD2K,
        "fps": 15,
        "jpeg_quality": 90
    },
    "high_fps": {
        "resolution": sl.RESOLUTION.VGA,
        "fps": 100,
        "jpeg_quality": 90
    },
    "balanced": {
        "resolution": sl.RESOLUTION.HD720,
        "fps": 60,
        "jpeg_quality": 90
    }
}

# --- H.264 ENCODING (ADVANCED) ---
# IMPORTANT: To use H.264, you need a dedicated library with Python bindings 
# for hardware-accelerated encoding, such as python-ffmpeg or GStreamer.
# The code below remains with JPEG for compatibility, but the ideal implementation
# would replace the cv2.imencode call with an H.264 encoder.
#
# Example with a hypothetical H.264 encoder library:
# h264_encoder = H264Encoder(width, height, bitrate)
# ... in the loop ...
# encoded_frame_data = h264_encoder.encode(sbs_image)

def main(mode):
    # --- Get configuration for the selected mode ---
    config = MODES[mode]
    RESOLUTION = config["resolution"]
    FPS = config["fps"]
    JPEG_QUALITY = config["jpeg_quality"]
    
    # Network settings
    LISTEN_IP = '0.0.0.0'
    UDP_PORT = 8080
    CHUNK_SIZE = 60000  # 60 KB, safely below the 64KB UDP limit

    print(f"--- Starting Server in '{mode}' mode ---")
    print(f"Resolution: {RESOLUTION}, FPS: {FPS}, JPEG Quality: {JPEG_QUALITY}")

    # --- Initialize ZED Camera ---
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

    # --- Handshake: Wait for a ping from the client ---
    print("Waiting for a ping from the client...")
    data, client_address = sock.recvfrom(1024)
    print(f"✅ Client connected from {client_address}")

    try:
        left_image, right_image = sl.Mat(), sl.Mat()
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        frame_id = 0
        fps_start_time = time.perf_counter()
        fps_frame_count = 0

        while True:
            if zed.grab() == sl.ERROR_CODE.SUCCESS:
                zed.retrieve_image(left_image, sl.VIEW.LEFT)
                zed.retrieve_image(right_image, sl.VIEW.RIGHT)

                # Create side-by-side stereo image
                sbs_image = np.concatenate((left_image.get_data(), right_image.get_data()), axis=1)

                # --- Encode the frame ---
                # Replace this with your H.264 encoder for better performance
                result, frame_jpeg = cv2.imencode('.jpg', sbs_image, encode_param)
                if not result:
                    continue

                frame_data = frame_jpeg.tobytes()
                total_size = len(frame_data)
                num_chunks = (total_size + CHUNK_SIZE - 1) // CHUNK_SIZE
                
                # --- Send the frame in chunks ---
                for i in range(num_chunks):
                    start = i * CHUNK_SIZE
                    end = start + CHUNK_SIZE
                    chunk = frame_data[start:end]
                    
                    # Header: [frame_id (4 bytes), chunk_index (1 byte), total_chunks (1 byte)]
                    header = struct.pack('<IBB', frame_id, i, num_chunks)
                    sock.sendto(header + chunk, client_address)

                frame_id = (frame_id + 1) % 4294967295
                
                # --- FPS Calculation ---
                fps_frame_count += 1
                if time.perf_counter() - fps_start_time >= 1.0:
                    fps = fps_frame_count / (time.perf_counter() - fps_start_time)
                    print(f"Server FPS: {fps:.1f}", end='\r')
                    fps_start_time = time.perf_counter()
                    fps_frame_count = 0
                
    except KeyboardInterrupt:
        print('\n🛑 Streaming stopped by user.')
    finally:
        print("Cleaning up...")
        sock.close()
        zed.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZED Camera UDP Streaming Server")
    parser.add_argument('--mode', type=str, required=True, choices=MODES.keys(),
                        help="Streaming mode.")
    args = parser.parse_args()
    main(args.mode)
