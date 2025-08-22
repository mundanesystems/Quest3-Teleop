import asyncio
import json
import logging
import time
import fractions
import cv2
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCRtpReceiver
from av import VideoFrame

class CameraSimulationTrack(VideoStreamTrack):
    """
    Simulates a real camera stream with realistic content at 60fps
    """
    def __init__(self):
        super().__init__()
        self._start_time = time.time()
        self._frame_count = 0
        self._last_log_time = time.time()
        
        # Camera-like settings
        self.width, self.height = 1280, 720  # Full HD like real camera
        self.target_fps = 60
        self._frame_duration = 1.0 / self.target_fps  # 16.67ms per frame
        self._next_frame_time = time.time()
        
        # Create realistic background scene
        self._background = self._create_realistic_scene()
        
        # Moving objects to simulate activity
        self._objects = [
            {"x": 100, "y": 200, "vx": 5, "vy": 2, "color": (0, 255, 0), "size": 30},
            {"x": 300, "y": 400, "vx": -3, "vy": 3, "color": (255, 0, 0), "size": 20},
            {"x": 600, "y": 300, "vx": 2, "vy": -4, "color": (0, 0, 255), "size": 25},
        ]

    def _create_realistic_scene(self):
        """Create a realistic background scene like a room/office"""
        scene = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Floor gradient (like concrete/carpet)
        for y in range(self.height // 2, self.height):
            intensity = 40 + int((y - self.height // 2) * 30 / (self.height // 2))
            scene[y, :] = [intensity, intensity, intensity]
        
        # Wall gradient
        for y in range(0, self.height // 2):
            intensity = 80 + int(y * 40 / (self.height // 2))
            scene[y, :] = [intensity + 10, intensity + 5, intensity]
        
        # Add some "furniture" rectangles
        cv2.rectangle(scene, (50, 400), (200, 600), (101, 67, 33), -1)  # Table
        cv2.rectangle(scene, (900, 300), (1200, 700), (139, 69, 19), -1)  # Cabinet
        cv2.rectangle(scene, (400, 500), (500, 700), (60, 60, 60), -1)   # Chair leg
        
        # Add some texture/noise for realism
        noise = np.random.randint(-10, 10, (self.height, self.width, 3))
        scene = np.clip(scene.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        return scene

    async def recv(self):
        # Control frame timing for true 60fps
        current_time = time.time()
        if current_time < self._next_frame_time:
            await asyncio.sleep(self._next_frame_time - current_time)
        
        frame_start = time.time()
        
        # Calculate proper PTS for 60fps
        pts = int(self._frame_count * 90000 // self.target_fps)  # 90kHz clock
        time_base = fractions.Fraction(1, 90000)

        # Start with background
        frame_data = self._background.copy()
        
        # Update and draw moving objects (simulate people/robots moving)
        for obj in self._objects:
            # Update position
            obj["x"] += obj["vx"]
            obj["y"] += obj["vy"]
            
            # Bounce off walls
            if obj["x"] <= obj["size"] or obj["x"] >= self.width - obj["size"]:
                obj["vx"] *= -1
            if obj["y"] <= obj["size"] or obj["y"] >= self.height - obj["size"]:
                obj["vy"] *= -1
            
            # Keep in bounds
            obj["x"] = max(obj["size"], min(self.width - obj["size"], obj["x"]))
            obj["y"] = max(obj["size"], min(self.height - obj["size"], obj["y"]))
            
            # Draw object (simulate moving person/robot)
            cv2.circle(frame_data, (int(obj["x"]), int(obj["y"])), obj["size"], obj["color"], -1)
            # Add "shadow"
            cv2.circle(frame_data, (int(obj["x"] + 3), int(obj["y"] + 3)), obj["size"], (0, 0, 0), -1)

        # Add camera-like effects
        
        # Simulate slight camera shake (realistic for handheld/robot cam)
        shake_x = int(1 * np.sin(frame_start * 8))
        shake_y = int(1 * np.cos(frame_start * 12))
        
        # Add timestamp overlay (like security camera)
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(frame_start))
        milliseconds = int((frame_start % 1) * 1000)
        full_timestamp = f"{timestamp_str}.{milliseconds:03d}"
        cv2.putText(frame_data, full_timestamp, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame_data, full_timestamp, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)  # Outline
        
        # Add performance metrics
        elapsed = frame_start - self._start_time
        fps = self._frame_count / elapsed if elapsed > 0 else 0
        frame_gen_time = (time.time() - frame_start) * 1000
        
        cv2.putText(frame_data, f"CAM-01  Frame: {self._frame_count}", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame_data, f"FPS: {fps:.1f} | Target: 60.0", (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame_data, f"Gen: {frame_gen_time:.1f}ms", (10, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Add subtle noise every few frames (like real camera sensor)
        if self._frame_count % 10 == 0:  # Every 10 frames to save CPU
            noise = np.random.randint(-2, 2, (self.height, self.width, 3))
            frame_data = np.clip(frame_data.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # Create VideoFrame with proper timing
        frame = VideoFrame.from_ndarray(frame_data, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        
        # Update timing for next frame
        self._next_frame_time += self._frame_duration
        
        # Log performance every 120 frames (2 seconds at 60fps)
        if self._frame_count % 120 == 0 and frame_start - self._last_log_time > 1:
            actual_fps = 120 / (frame_start - self._last_log_time) if self._last_log_time > 0 else 0
            print(f"🎥 Camera Frame {self._frame_count}: Target=60fps, Actual={actual_fps:.1f}fps, Gen={frame_gen_time:.1f}ms")
            self._last_log_time = frame_start
        
        self._frame_count += 1
        return frame


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

    # Create camera simulation track
    video_track = CameraSimulationTrack()
    
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


pcs = set()

async def on_shutdown(app):
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

    print("🎥 Starting CAMERA SIMULATION WebRTC server on http://0.0.0.0:8080")
    print("📡 60fps Full HD simulation with realistic camera content")
    print("🚀 Optimized for low latency streaming")
    web.run_app(app, host="0.0.0.0", port=8080, access_log=None)
