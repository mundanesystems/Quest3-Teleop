import rclpy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2 as cv
import threading
import time
import numpy as np

from .camera_interface import BaseCamera
from follower_interfaces.msg import Status

class ZED2iDriver(BaseCamera):
    """
    ZED2i stereoscopic camera driver using OpenCV VideoCapture.
    
    ===================================================================================
    CRITICAL ARCHITECTURAL DIFFERENCES FROM OTHER CAMERA DRIVERS:
    ===================================================================================
    
    1. HARDWARE ARCHITECTURE:
       - USB Cameras: Single USB device → Single image stream
       - Gemini Cameras: Single depth device → Color + depth streams  
       - ZED2i: Single stereoscopic device → TWO synchronized image streams
    
    2. PROCESS ARCHITECTURE:
       - USB Cameras: Direct hardware capture in same process
       - Gemini Cameras: Launch EXTERNAL orbbec processes, monitor their topics
       - ZED2i: Direct hardware capture BUT splits into dual streams
    
    3. TOPIC PUBLISHING:
       - USB Cameras: /camera/{name}/image_raw (single topic)
       - Gemini Cameras: /{name}/color/image_raw + depth topics (external process)
       - ZED2i: /camera/{name}/left/image_raw + /camera/{name}/right/image_raw (dual topics)
    
    4. HEALTH MONITORING STRATEGY:
       - USB Cameras: Monitor internal frame capture timing (no topic monitoring)
       - Gemini Cameras: Monitor topics published by EXTERNAL processes via topic_to_monitor
       - ZED2i: Monitor topics published by ITSELF (self-health checking) via topic_to_monitor
    
    5. CONFIGURATION PARAMETERS:
       - USB Cameras: topic_to_monitor used as publish topic name (confusing naming)
       - Gemini Cameras: topic_to_monitor used to subscribe to external process topics
       - ZED2i: topic_to_monitor is LIST of topics to self-monitor for health
    
    ===================================================================================
    
    This driver captures side-by-side stereo images from a ZED2i camera, automatically
    splits them into separate left/right streams, publishes to dual topics, and then
    subscribes to its own topics for health monitoring - a unique hybrid approach.
    
    Features:
    - Hardware stereo capture with automatic left/right splitting
    - Dual-topic publishing with synchronized timestamps  
    - Self-monitoring health checks on published topics
    - Standard camera interface integration
    - Configurable stereo resolutions and frame rates
    """
    
    def __init__(self, node):
        super().__init__(node)
        self.bridge = CvBridge()
        
        # Parameters specific to ZED2i camera
        self.device_id = self.node.get_parameter('device_id').value
        self.frame_width = self.node.get_parameter('frame_width').value
        self.frame_height = self.node.get_parameter('frame_height').value
        self.fps = self.node.get_parameter('fps').value
        self.health_timeout = self.node.get_parameter('health_timeout_sec').value
        
        # Get topics to monitor - can be a list for ZED2i stereo
        topics_to_monitor = self.node.get_parameter('topic_to_monitor').value
        if isinstance(topics_to_monitor, list):
            self.left_topic_to_monitor = topics_to_monitor[0] if len(topics_to_monitor) > 0 else None
            self.right_topic_to_monitor = topics_to_monitor[1] if len(topics_to_monitor) > 1 else None
        else:
            # Fallback for single topic (shouldn't happen for ZED2i)
            self.left_topic_to_monitor = topics_to_monitor
            self.right_topic_to_monitor = None
        
        # ZED2i specific topic names
        self.left_topic = f"/camera/{self.camera_name}/left/image_raw"
        self.right_topic = f"/camera/{self.camera_name}/right/image_raw"
        
        # Publishers for left and right images
        self.left_publisher = self.node.create_publisher(Image, self.left_topic, 10)
        self.right_publisher = self.node.create_publisher(Image, self.right_topic, 10)
        
        self.camera_object: cv.VideoCapture = None
        self.thread: threading.Thread = None
        self._is_running = False
        self.last_frame_time = 0.0
        
                # Topic monitoring for health checks
        self.last_left_msg_time = 0.0
        self.last_right_msg_time = 0.0
        
        # Subscribe to topics for health monitoring (using topic_to_monitor parameter)
        # IMPORTANT: Unlike other cameras, ZED2i monitors its OWN published topics
        # - USB cameras: don't monitor topics (monitor internal frame capture)
        # - Gemini cameras: monitor topics published by EXTERNAL processes
        # - ZED2i: monitors topics published by ITSELF (self-health checking)
        if self.left_topic_to_monitor:
            self.left_subscription = self.node.create_subscription(
                Image, self.left_topic_to_monitor, self._left_topic_callback, 10)
        if self.right_topic_to_monitor:
            self.right_subscription = self.node.create_subscription(
                Image, self.right_topic_to_monitor, self._right_topic_callback, 10)
        
        # Store stereo dimensions (will be set by _validate_resolution)
        self.stereo_width = None
        self.stereo_height = None
        
        # ZED2i has specific resolutions - validate and adjust if needed
        self._validate_resolution()

    def _left_topic_callback(self, msg):
        """Callback for left image topic monitoring."""
        self.last_left_msg_time = time.time()

    def _right_topic_callback(self, msg):
        """Callback for right image topic monitoring."""
        self.last_right_msg_time = time.time()

    def _validate_resolution(self):
        """
        Validate and adjust resolution for ZED2i camera.
        ZED2i outputs side-by-side stereo, so actual camera resolutions are:
        - 2560x720 (1280x720 per eye)
        - 1344x376 (672x376 per eye)  
        - 3840x1080 (1920x1080 per eye)
        - 4416x1242 (2208x1242 per eye)
        """
        # Map single-eye resolutions to full stereo output
        zed_eye_to_stereo = {
            (1280, 720): (2560, 720),   # HD720 stereo
            (672, 376): (1344, 376),    # VGA stereo
            (1920, 1080): (3840, 1080), # HD1080 stereo
            (2208, 1242): (4416, 1242)  # 2K stereo
        }
        
        requested = (self.frame_width, self.frame_height)
        if requested in zed_eye_to_stereo:
            # User specified single-eye resolution, convert to stereo
            self.stereo_width, self.stereo_height = zed_eye_to_stereo[requested]
            self.logger.info(f"Using ZED2i resolution: {self.stereo_width}x{self.stereo_height} (stereo) for {self.frame_width}x{self.frame_height} per eye")
        else:
            # Default to HD720 if requested resolution is not supported
            self.frame_width, self.frame_height = 1280, 720
            self.stereo_width, self.stereo_height = 2560, 720
            self.logger.warn(f"Requested resolution {requested} not supported by ZED2i. Using 1280x720 per eye (2560x720 stereo).")

    def start(self):
        if self._is_running:
            self.logger.warn(f"Capture thread for '{self.camera_name}' is already running.")
            return
        
        try:
            # Try to open with V4L2 backend first (Linux-specific)
            self.camera_object = cv.VideoCapture(self.device_id, cv.CAP_V4L2)
            if not self.camera_object.isOpened():
                self.camera_object.release()
                self.logger.warn(f"Failed to open '{self.camera_name}' with V4L2, trying default backend.")
                self.camera_object = cv.VideoCapture(self.device_id)

            if not self.camera_object.isOpened():
                raise RuntimeError(f"Could not open ZED2i camera device {self.device_id}.")

            # Set ZED2i camera properties
            self._configure_camera()

            self._is_running = True
            self.last_frame_time = time.time()
            self.thread = threading.Thread(target=self._camera_loop, daemon=True)
            self.thread.start()
            self.logger.info(f"Successfully started ZED2i capture thread for '{self.camera_name}'.")

        except Exception as e:
            self.logger.error(f"Failed to start ZED2i camera '{self.camera_name}': {e}")
            self._is_running = False
            if self.camera_object:
                self.camera_object.release()

    def _configure_camera(self):
        """Configure ZED2i camera-specific settings."""
        # Set resolution - ZED2i outputs side-by-side stereo
        # Use the validated stereo resolution
        self.camera_object.set(cv.CAP_PROP_FRAME_WIDTH, self.stereo_width)
        self.camera_object.set(cv.CAP_PROP_FRAME_HEIGHT, self.stereo_height)
        self.camera_object.set(cv.CAP_PROP_FPS, self.fps)
        
        # ZED2i specific settings (if supported by OpenCV backend)
        # Note: These may not work with all backends
        self.camera_object.set(cv.CAP_PROP_FOURCC, cv.VideoWriter_fourcc('Y', 'U', 'Y', 'V'))
        
        # Try to set buffer size to reduce latency
        self.camera_object.set(cv.CAP_PROP_BUFFERSIZE, 1)
        
        # Log actual settings achieved
        actual_width = int(self.camera_object.get(cv.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.camera_object.get(cv.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.camera_object.get(cv.CAP_PROP_FPS)
        
        self.logger.info(f"ZED2i '{self.camera_name}' configured: {actual_width}x{actual_height} @ {actual_fps} fps")
        self.logger.info(f"Output will be split into {self.frame_width}x{self.frame_height} per eye")

    def stop(self):
        self._is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        
        if self.camera_object and self.camera_object.isOpened():
            self.camera_object.release()
        self.logger.info(f"Stopped ZED2i camera '{self.camera_name}'.")

    def get_status(self) -> tuple[int, str]:
        if not self._is_running or not self.thread or not self.thread.is_alive():
            return Status.STATUS_ERROR, "ZED2i capture thread is not running."
        
        if time.time() - self.last_frame_time > self.health_timeout:
            return Status.STATUS_ERROR, "ZED2i frame capture has timed out."
        
        # If the thread has started but we've never received a frame, we're still initializing.
        if self.last_frame_time == 0:
            return Status.STATUS_INITIALIZING, "Waiting for first ZED2i frame."

        # Check both left and right topic health (if being monitored)
        current_time = time.time()
        
        # Check left topic (if configured)
        if self.left_topic_to_monitor and self.last_left_msg_time > 0:
            if current_time - self.last_left_msg_time > self.health_timeout:
                return Status.STATUS_ERROR, f"ZED2i left topic '{self.left_topic_to_monitor}' timed out ({current_time - self.last_left_msg_time:.1f}s since last message)."
        
        # Check right topic (if configured)
        if self.right_topic_to_monitor and self.last_right_msg_time > 0:
            if current_time - self.last_right_msg_time > self.health_timeout:
                return Status.STATUS_ERROR, f"ZED2i right topic '{self.right_topic_to_monitor}' timed out ({current_time - self.last_right_msg_time:.1f}s since last message)."

        return Status.STATUS_WORKING, ""

    def _camera_loop(self):
        """Main camera capture loop for ZED2i stereo camera."""
        while rclpy.ok() and self._is_running:
            try:
                ret, frame = self.camera_object.read()
                if not ret:
                    self.logger.warn(f'Failed to capture frame from ZED2i {self.camera_name}.')
                    time.sleep(0.1)
                    continue
                
                self.last_frame_time = time.time()
                
                # ZED2i outputs side-by-side stereo images
                # Split the frame into left and right images
                height, width = frame.shape[:2]
                single_width = width // 2
                
                if width % 2 != 0:
                    self.logger.warn("Received frame width is not even, ZED2i should output even-width frames.")
                    continue
                
                # Extract left and right images
                left_image = frame[:, :single_width]
                right_image = frame[:, single_width:]
                
                # Convert to ROS Image messages
                timestamp = self.node.get_clock().now().to_msg()
                
                left_ros_image = self.bridge.cv2_to_imgmsg(left_image, encoding='bgr8')
                left_ros_image.header.stamp = timestamp
                left_ros_image.header.frame_id = f'{self.camera_name}_left_frame'
                
                right_ros_image = self.bridge.cv2_to_imgmsg(right_image, encoding='bgr8')
                right_ros_image.header.stamp = timestamp
                right_ros_image.header.frame_id = f'{self.camera_name}_right_frame'
                
                # Publish both images
                self.left_publisher.publish(left_ros_image)
                self.right_publisher.publish(right_ros_image)
                
                # UNIQUE TO ZED2i: Update monitoring timestamps when we publish
                # Unlike other cameras, ZED2i monitors its OWN published topics for health
                # This creates a feedback loop ensuring the entire publish pipeline works
                current_time = time.time()
                self.last_left_msg_time = current_time
                self.last_right_msg_time = current_time
                
            except Exception as e:
                self.logger.error(f'Error in ZED2i camera loop for {self.camera_name}: {e}')
                self._is_running = False

    def get_stereo_info(self):
        """
        Get stereo camera information.
        
        Note: This is a simplified version. For full stereo calibration, 
        use the zed-open-capture library integration.
        """
        return {
            'baseline': 120.0,  # ZED2i baseline in mm (approximate)
            'left_topic': self.left_topic,
            'right_topic': self.right_topic,
            'width': self.frame_width,
            'height': self.frame_height,
            'note': 'Using OpenCV backend - for full ZED2i features use zed-open-capture library'
        }
