import asyncio
import json
import logging
import time
import cv2
import numpy as np
import pyzed.sl as sl
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame

# --- CONFIGURATION MAPPINGS ---
MODES = {
    "high_res": {
        "resolution": sl.RESOLUTION.HD2K,
        "fps": 15,
    },
    "high_fps": {
        "resolution": sl.RESOLUTION.VGA,
        "fps": 100,
    },
    "balanced": {
        "resolution": sl.RESOLUTION.HD720,
        "fps": 60,
    }
}

class ZEDVideoStreamTrack(VideoStreamTrack):
    """
    A video track that streams video from a ZED camera.
    """
    def __init__(self, zed, mode):
        super().__init__()
        self.zed = zed
        self.mode = mode
        self.left_image = sl.Mat()
        self.right_image = sl.Mat()
        self._start_time = time.time()
        self._frame_count = 0

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        if self.zed.grab() == sl.ERROR_CODE.SUCCESS:
            self.zed.retrieve_image(self.left_image, sl.VIEW.LEFT)
            self.zed.retrieve_image(self.right_image, sl.VIEW.RIGHT)

            # Create side-by-side stereo image
            sbs_image_rgba = np.concatenate((self.left_image.get_data(), self.right_image.get_data()), axis=1)
            
            # Convert RGBA to BGR for OpenCV processing
            sbs_image_bgr = cv2.cvtColor(sbs_image_rgba, cv2.COLOR_RGBA2BGR)

            # Create a VideoFrame from the numpy array
            frame = VideoFrame.from_ndarray(sbs_image_bgr, format="bgr24")
            frame.pts = pts
            frame.time_base = time_base
            
            self._frame_count += 1
            return frame
        return None


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    # Open the ZED camera
    zed = sl.Camera()
    init_params = sl.InitParameters()
    config = MODES["balanced"] # You can change the mode here
    init_params.camera_resolution = config["resolution"]
    init_params.camera_fps = config["fps"]
    init_params.depth_mode = sl.DEPTH_MODE.NONE

    if zed.open(init_params) != sl.ERROR_CODE.SUCCESS:
        print("Failed to open ZED camera!")
        return

    video_track = ZEDVideoStreamTrack(zed, "balanced")
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
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from aiohttp import web
    
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_post("/offer", offer)

    web.run_app(app, host="0.0.0.0", port=8080)
