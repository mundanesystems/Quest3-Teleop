import pyzed.sl as sl
import argparse
import sys

def main():
    # --- ARGUMENT PARSING ---
    # Setup command-line arguments for easy configuration
    parser = argparse.ArgumentParser(description="ZED Stereoscopic H.264 Streaming Server")
    parser.add_argument('--port', type=int, default=30000, help='Port for the RTSP stream')
    parser.add_argument('--bitrate', type=int, default=8000, help='Streaming bitrate in kbit/s')
    parser.add_argument('--resolution', type=str, default='HD720', choices=['HD1200', 'HD1080', 'HD720', 'SVGA', 'VGA'], help='Camera resolution')
    opt = parser.parse_args()

    # --- ZED CAMERA INITIALIZATION ---
    print("Starting ZED Stereoscopic Streaming Server...")
    init_params = sl.InitParameters()
    init_params.camera_resolution = sl.RESOLUTION[opt.resolution]
    init_params.camera_fps = 60  # Set a high FPS for smooth VR passthrough
    init_params.depth_mode = sl.DEPTH_MODE.NONE
    init_params.sdk_verbose = 1

    cam = sl.Camera()
    status = cam.open(init_params)
    if status != sl.ERROR_CODE.SUCCESS:
        print(f"❌ Camera Open Error: {status}. Exiting.")
        sys.exit(1)

    # --- STREAMING SETUP ---
    # Configure the streaming parameters
    stream_params = sl.StreamingParameters()
    stream_params.codec = sl.STREAMING_CODEC.H264
    stream_params.port = opt.port
    stream_params.bitrate = opt.bitrate * 1000  # Convert kbit/s to bit/s

    # Enable the ZED's built-in streaming server
    status = cam.enable_streaming(stream_params)
    if status != sl.ERROR_CODE.SUCCESS:
        print(f"❌ Streaming Enable Error: {status}. Exiting.")
        cam.close()
        sys.exit(1)

    print(f"✅ Stereoscopic stream enabled.")
    print(f"📡 Listening for clients at: rtsp://<your_pc_ip>:{stream_params.port}/zed")

    # --- MAIN LOOP ---
    # This loop keeps the stream alive. The ZED SDK handles everything in the background.
    runtime = sl.RuntimeParameters()
    # Create a sl.Mat to hold the side-by-side image
    sbs_image = sl.Mat(cam.get_camera_information().camera_configuration.resolution.width * 2, cam.get_camera_information().camera_configuration.resolution.height, sl.MAT_TYPE.U8_C4)

    try:
        while True:
            if cam.grab(runtime) == sl.ERROR_CODE.SUCCESS:
                # By retrieving the side-by-side view, we tell the streaming module
                # to encode this specific view for the stream.
                cam.retrieve_image(sbs_image, sl.VIEW.SIDE_BY_SIDE)
            else:
                # Add a small delay if grabbing fails to prevent a tight error loop
                import time
                time.sleep(0.001)

    except KeyboardInterrupt:
        print("\n🛑 Streaming stopped by user.")

    finally:
        # --- CLEANUP ---
        print("Disabling stream and closing camera...")
        cam.disable_streaming()
        cam.close()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()