import asyncio
import json
import logging
import time
import fractions
import cv2
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCRtpReceiver
from av import VideoFrame
import pyzed.sl as sl

class ZEDStereoStreamTrack(VideoStreamTrack):
    """
    Captures live ZED2i stereo camera feed at 60fps and streams side-by-side
    """
    def __init__(self):
        super().__init__()
        self._start_time = time.time()
        self._frame_count = 0
        self._last_log_time = time.time()
        
        # ZED Camera settings for 60fps 1280x720
        self.width, self.height = 1280, 720
        self.target_fps = 60
        self._frame_duration = 1.0 / self.target_fps  # 16.67ms per frame
        self._next_frame_time = time.time()
        
        # Initialize ZED Camera
        self.zed = sl.Camera()
        self._setup_zed_camera()
        
        # Create ZED image containers
        self.left_image = sl.Mat()
        self.right_image = sl.Mat()
        
        print("🎥 ZED2i camera initialized for 60fps stereo streaming")

    def _setup_zed_camera(self):
        """Configure ZED camera for optimal 60fps performance - minimal setup like UDP version"""
        init_params = sl.InitParameters()
        
        # Camera resolution and FPS (same as working UDP version)
        init_params.camera_resolution = sl.RESOLUTION.HD720  # 1280x720
        init_params.camera_fps = 60
        
        # Disable depth processing for maximum performance (same as UDP)
        init_params.depth_mode = sl.DEPTH_MODE.NONE
        
        # Open camera (minimal setup like UDP version)
        err = self.zed.open(init_params)
        if err != sl.ERROR_CODE.SUCCESS:
            print(f"❌ Failed to open ZED camera: {err}")
            raise RuntimeError(f"ZED Camera failed to open: {err}")
        
        print("✅ ZED2i camera configured for 60fps stereo capture (minimal setup)")

    async def recv(self):
        # Control frame timing for true 60fps
        current_time = time.time()
        if current_time < self._next_frame_time:
            await asyncio.sleep(self._next_frame_time - current_time)
        
        frame_start = time.time()
        
        # Calculate proper PTS for 60fps
        pts = int(self._frame_count * 90000 // self.target_fps)  # 90kHz clock
        time_base = fractions.Fraction(1, 90000)

        # Capture from ZED camera
        if self.zed.grab() == sl.ERROR_CODE.SUCCESS:
            # Retrieve left and right images
            self.zed.retrieve_image(self.left_image, sl.VIEW.LEFT)
            self.zed.retrieve_image(self.right_image, sl.VIEW.RIGHT)
            
            # Convert to numpy arrays (ZED gives RGBA, convert to BGR for OpenCV)
            left_bgr = cv2.cvtColor(self.left_image.get_data(), cv2.COLOR_RGBA2BGR)
            right_bgr = cv2.cvtColor(self.right_image.get_data(), cv2.COLOR_RGBA2BGR)
            
            # Create side-by-side stereo image (2560x720 total)
            stereo_frame = np.concatenate((left_bgr, right_bgr), axis=1)
            
        else:
            # Fallback if camera capture fails
            print("⚠️ ZED capture failed, using black frame")
            stereo_frame = np.zeros((self.height, self.width * 2, 3), dtype=np.uint8)
            cv2.putText(stereo_frame, "ZED CAMERA ERROR", (self.width // 2, self.height // 2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)

        # Add overlay information
        current_time = time.time()
        
        # Add timestamp overlay
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(frame_start))
        milliseconds = int((frame_start % 1) * 1000)
        full_timestamp = f"{timestamp_str}.{milliseconds:03d}"
        
        # Left camera overlay
        cv2.putText(stereo_frame, f"LEFT - {full_timestamp}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(stereo_frame, f"LEFT - {full_timestamp}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        
        # Right camera overlay
        cv2.putText(stereo_frame, f"RIGHT - {full_timestamp}", (self.width + 10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(stereo_frame, f"RIGHT - {full_timestamp}", (self.width + 10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        
        # Add performance metrics
        elapsed = frame_start - self._start_time
        fps = self._frame_count / elapsed if elapsed > 0 else 0
        frame_gen_time = (time.time() - frame_start) * 1000
        
        # Performance overlay on left side
        cv2.putText(stereo_frame, f"ZED2i STEREO  Frame: {self._frame_count}", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        cv2.putText(stereo_frame, f"FPS: {fps:.1f} / 60.0 | Gen: {frame_gen_time:.1f}ms", (10, 85), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        
        # Separator line between cameras
        cv2.line(stereo_frame, (self.width, 0), (self.width, self.height), (255, 255, 255), 2)

        # Create VideoFrame with proper timing
        frame = VideoFrame.from_ndarray(stereo_frame, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        
        # Update timing for next frame
        self._next_frame_time += self._frame_duration
        
        # Log performance every 120 frames (2 seconds at 60fps)
        if self._frame_count % 120 == 0 and frame_start - self._last_log_time > 1:
            actual_fps = 120 / (frame_start - self._last_log_time) if self._last_log_time > 0 else 0
            print(f"🎥 ZED2i Frame {self._frame_count}: Target=60fps, Actual={actual_fps:.1f}fps, Gen={frame_gen_time:.1f}ms")
            self._last_log_time = frame_start
        
        self._frame_count += 1
        return frame

    def __del__(self):
        """Clean up ZED camera resources"""
        if hasattr(self, 'zed'):
            self.zed.close()
            print("🔒 ZED camera closed")


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # Configure for low latency
    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"🔗 Connection state: {pc.connectionState}")
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    # Create ZED stereo track
    try:
        video_track = ZEDStereoStreamTrack()
        
        # Configure video transceiver for low latency
        transceiver = pc.addTransceiver(video_track, direction="sendonly")
        
        # Set codec preferences for low latency (prefer H.264)
        if hasattr(transceiver, 'setCodecPreferences'):
            try:
                capabilities = RTCRtpReceiver.getCapabilities("video")
                codecs = [codec for codec in capabilities.codecs if codec.mimeType == "video/H264"]
                if codecs:
                    transceiver.setCodecPreferences(codecs)
            except:
                pass  # Fallback to default

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
            ),
        )
    
    except Exception as e:
        print(f"❌ Error creating ZED stream: {e}")
        return web.Response(
            status=500,
            content_type="application/json",
            text=json.dumps({"error": str(e)})
        )


pcs = set()

async def on_shutdown(app):
    print("🛑 Shutting down ZED WebRTC server...")
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    from aiohttp import web
    
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    
    # CORS middleware
    @web.middleware
    async def cors_handler(request, handler):
        if request.method == "OPTIONS":
            return web.Response(headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST',
                'Access-Control-Allow-Headers': 'Content-Type'
            })
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    
    app.middlewares.append(cors_handler)
    app.router.add_post("/offer", offer)

    print("🎥 Starting ZED2i STEREO WebRTC server on http://0.0.0.0:8080")
    print("📡 60fps HD720 stereo streaming (side-by-side)")
    print("🚀 Optimized for low latency real-time streaming")
    print("🔍 Make sure ZED2i camera is connected!")
    web.run_app(app, host="0.0.0.0", port=8080, access_log=None)
