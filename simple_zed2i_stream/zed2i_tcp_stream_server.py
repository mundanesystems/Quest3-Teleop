import socket
import time
import cv2
import numpy as np
import pyzed.sl as sl
import struct # Used to pack the timestamp

# CONFIGURATION
LISTEN_IP = '0.0.0.0'
TCP_PORT = 8080
RESOLUTION = sl.RESOLUTION.HD720
FPS = 60
JPEG_QUALITY = 85

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

    cam_info = zed.get_camera_information()
    calib_params = cam_info.camera_configuration.calibration_parameters
    h_fov = calib_params.left_cam.h_fov
    v_fov = calib_params.left_cam.v_fov
    fov_message = f"{h_fov},{v_fov}".encode('utf-8')
    fov_header = len(fov_message).to_bytes(4, 'little')

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((LISTEN_IP, TCP_PORT))
    server_sock.listen(1)
    print(f"📹 Passthrough Server listening at {LISTEN_IP}:{TCP_PORT}")

    conn, addr = server_sock.accept()
    print(f'✅ Client connected from {addr}')

    print(f"Sending FOV data: HFOV={h_fov}, VFOV={v_fov}")
    conn.sendall(fov_header + fov_message)

    try:
        left_image, right_image = sl.Mat(), sl.Mat()
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]

        while True:
            if zed.grab() == sl.ERROR_CODE.SUCCESS:
                zed.retrieve_image(left_image, sl.VIEW.LEFT)
                zed.retrieve_image(right_image, sl.VIEW.RIGHT)
                sbs_image = np.concatenate((left_image.get_data(), right_image.get_data()), axis=1)
                result, frame_jpeg = cv2.imencode('.jpg', sbs_image, encode_param)
                if not result: continue

                # --- TIMESTAMPING ---
                # Get current time as a high-precision float (seconds since epoch)
                timestamp = time.time()
                # Pack the timestamp into 8 bytes (a 'double')
                timestamp_bytes = struct.pack('<d', timestamp)
                
                frame_data = frame_jpeg.tobytes()
                size_header = len(frame_data).to_bytes(4, 'little')

                # Send all parts: timestamp + size + frame data
                conn.sendall(timestamp_bytes + size_header + frame_data)
                
    except (ConnectionResetError, BrokenPipeError):
        print('❌ Client disconnected.')
    finally:
        print("Cleaning up...")
        conn.close()
        server_sock.close()
        zed.close()

if __name__ == "__main__":
    main()