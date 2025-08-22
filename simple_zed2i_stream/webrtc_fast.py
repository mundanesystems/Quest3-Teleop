import asyncio
import json
import logging
import time
import cv2
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame

class HighPerformanceVideoTrack(VideoStreamTrack):
    """
    Optimized video track for low latency
    """
    def __init__(self):
        super().__init__()
        self._start_time = time.time()
        self._frame_count = 0
        self._last_log_time = time.time()
        
        # Pre-generate smaller test image for better performance
        self.width, self.height = 640, 360  # Reduced resolution
        self._base_frame = self._create_base_frame()

    def _create_base_frame(self):
        """Pre-create base frame to reduce per-frame computation"""
        frame_data = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Create a simple gradient that's fast to compute
        for y in range(self.height):
            for x in range(self.width):
                frame_data[y, x] = [
                    (x * 255) // self.width,  # Blue gradient
                    (y * 255) // self.height, # Green gradient
                    128  # Fixed red
                ]
        return frame_data

    async def recv(self):
        frame_start = time.time()
        pts, time_base = await self.next_timestamp()

        # Use pre-created frame and just add moving elements
        frame_data = self._base_frame.copy()
        
        # Add simple moving rectangle instead of complex sin calculations
        t = self._frame_count * 2  # Simple animation
        rect_x = (t % (self.width - 50))
        rect_y = (t // 4) % (self.height - 30)
        
        cv2.rectangle(frame_data, (rect_x, rect_y), (rect_x + 50, rect_y + 30), (255, 255, 255), -1)

        # Add minimal timing info
        current_time = time.time()
        fps = self._frame_count / (current_time - self._start_time) if current_time > self._start_time else 0
        frame_gen_time = (current_time - frame_start) * 1000
        
        cv2.putText(frame_data, f"F:{self._frame_count} FPS:{fps:.1f}", (10, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(frame_data, f"Gen:{frame_gen_time:.1f}ms", (10, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # Create VideoFrame
        frame = VideoFrame.from_ndarray(frame_data, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        
        # Log timing every 60 frames
        if self._frame_count % 60 == 0 and current_time - self._last_log_time > 2:
            print(f"Server: Frame {self._frame_count}, FPS={fps:.1f}, Gen={frame_gen_time:.1f}ms")
            self._last_log_time = current_time
        
        self._frame_count += 1
        return frame


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # Configure peer connection for low latency
    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    # Create optimized video track
    video_track = HighPerformanceVideoTrack()
    pc.addTrack(video_track)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


pcs = set()

async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)  # Reduce logging noise
    from aiohttp import web
    
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    
    # Minimal CORS support
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

    print("Starting HIGH PERFORMANCE WebRTC server on http://0.0.0.0:8080")
    print("Optimized for low latency - reduced resolution and processing")
    web.run_app(app, host="0.0.0.0", port=8080, access_log=None)  # Disable access logging
