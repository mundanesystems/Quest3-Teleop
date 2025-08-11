import pyzed.sl as sl
import argparse
import sys
import time

def main():
    parser = argparse.ArgumentParser(description="ZED Simple H.264 Streaming Test")
    parser.add_argument('--port', type=int, default=30000, help='Port for the RTSP stream')
    opt = parser.parse_args()

    print("Starting ZED Simple Streaming Test...")
    init_params = sl.InitParameters()
    init_params.camera_resolution = sl.RESOLUTION.HD720
    init_params.camera_fps = 30
    init_params.depth_mode = sl.DEPTH_MODE.NONE

    cam = sl.Camera()
    status = cam.open(init_params)
    if status != sl.ERROR_CODE.SUCCESS:
        print(f"❌ Camera Open Error: {status}. Exiting.")
        sys.exit(1)

    stream_params = sl.StreamingParameters()
    stream_params.codec = sl.STREAMING_CODEC.H264
    stream_params.port = opt.port

    status = cam.enable_streaming(stream_params)
    if status != sl.ERROR_CODE.SUCCESS:
        print(f"❌ Streaming Enable Error: {status}. Exiting.")
        cam.close()
        sys.exit(1)

    print(f"✅ Simple stream enabled at: rtsp://127.0.0.1:{stream_params.port}/zed")
    
    try:
        while True:
            if cam.grab() == sl.ERROR_CODE.SUCCESS:
                # In this simple script, we do nothing. The SDK handles it.
                time.sleep(0.01) # Keep the script alive

    except KeyboardInterrupt:
        print("\n🛑 Streaming stopped.")
    finally:
        cam.disable_streaming()
        cam.close()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()