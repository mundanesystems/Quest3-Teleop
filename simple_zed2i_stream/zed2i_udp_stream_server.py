
import socket
import time
import cv2
import numpy as np
import pyzed.sl as sl
import threading

# CONFIGURATION
QUEST_IP = '192.168.0.189'  # <-- Quest 3 IP address
QUEST_PORT = 8080            # UDP port to send to
PING_PORT = 8081             # UDP port to listen for pings/acks from Quest
RESOLUTION = sl.RESOLUTION.HD720
FPS = 15
JPEG_QUALITY = 90
CHUNK_SIZE = 8192  # 8 KB per UDP packet (safe for most networks)

# Initialize ZED camera
zed = sl.Camera()
init_params = sl.InitParameters()
init_params.camera_resolution = RESOLUTION
init_params.camera_fps = FPS
init_params.depth_mode = sl.DEPTH_MODE.NONE

if zed.open(init_params) != sl.ERROR_CODE.SUCCESS:
    print('Failed to open ZED2i camera!')
    exit(1)


# TCP socket for video
server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_sock.bind(('0.0.0.0', QUEST_PORT))
server_sock.listen(1)
print(f"📹 Video stream listening for a client at 0.0.0.0:{QUEST_PORT}")

# UDP socket for ping/ack (optional, can be kept for handshake)
ping_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ping_sock.bind(('0.0.0.0', PING_PORT))

encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]

def wait_for_ping():
    print(f'📡 Waiting for initial ping/ack from Quest on UDP port {PING_PORT}...')
    while True:
        data, addr = ping_sock.recvfrom(1024)
        if data:
            print(f'✅ Ping/ack received from Quest at {addr} (data: {data}). Starting video stream!')
            return addr

def ack_listener():
    while True:
        try:
            data, addr = ping_sock.recvfrom(1024)
            if data == b'ack':
                print(f'✅ Frame ack received from {addr}')
        except Exception:
            break

def send_combined_image_tcp(image_bytes, conn):
    # Send 4-byte length header, then image bytes
    length = len(image_bytes)
    conn.sendall(length.to_bytes(4, 'little'))
    conn.sendall(image_bytes)

try:
    # Wait for Quest to send a ping/ack before starting
    quest_addr = wait_for_ping()
    # Start ack listener thread
    ack_thread = threading.Thread(target=ack_listener, daemon=True)
    ack_thread.start()

    print('Waiting for Quest client to connect via TCP...')
    conn, addr = server_sock.accept()
    print(f'✅ Quest client connected from {addr}')
    frame_id = 0
    try:
        while True:
            if zed.grab() == sl.ERROR_CODE.SUCCESS:
                left = sl.Mat()
                right = sl.Mat()
                zed.retrieve_image(left, sl.VIEW.LEFT)
                zed.retrieve_image(right, sl.VIEW.RIGHT)
                left_img = left.get_data()
                right_img = right.get_data()


                # Ensure both images are 3-channel BGR for OpenCV Stitcher
                if left_img.shape[2] == 4:
                    left_img = cv2.cvtColor(left_img, cv2.COLOR_BGRA2BGR)
                if right_img.shape[2] == 4:
                    right_img = cv2.cvtColor(right_img, cv2.COLOR_BGRA2BGR)

                # Fuse left and right images using OpenCV's Stitcher
                fused_img = None
                try:
                    stitcher = cv2.Stitcher_create() if hasattr(cv2, 'Stitcher_create') else cv2.createStitcher()
                    status, pano = stitcher.stitch([left_img, right_img])
                    if status == cv2.Stitcher_OK:
                        fused_img = pano
                    else:
                        print(f"[WARN] Stitcher failed with status {status}, falling back to horizontal stack.")
                        fused_img = np.hstack((left_img, right_img))
                except Exception as e:
                    print(f"[ERROR] Exception during stitching: {e}. Falling back to horizontal stack.")
                    fused_img = np.hstack((left_img, right_img))

                # Encode as JPEG
                _, fused_jpg = cv2.imencode('.jpg', fused_img, encode_param)

                # Send the fused image over TCP
                send_combined_image_tcp(fused_jpg.tobytes(), conn)

                frame_id = (frame_id + 1) % 2**32
                time.sleep(1.0 / FPS)
            else:
                print('Frame grab failed!')
    except (ConnectionResetError, BrokenPipeError):
        print('Quest client disconnected. Waiting for a new connection...')
        conn.close()
        # Optionally, you can loop to accept a new connection
    finally:
        zed.close()
        if conn:
            conn.close()
        if server_sock:
            server_sock.close()
        if ping_sock:
            ping_sock.close()
except KeyboardInterrupt:
    print('Streaming stopped.')
finally:
    try:
        zed.close()
    except:
        pass
    try:
        if 'conn' in locals() and conn:
            conn.close()
    except:
        pass
    try:
        if 'server_sock' in locals() and server_sock:
            server_sock.close()
    except:
        pass
    try:
        if 'ping_sock' in locals() and ping_sock:
            ping_sock.close()
    except:
        pass
