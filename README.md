# Quest3-Teleop

This project enables real-time streaming of video from a ZED 2i stereo camera to a Meta Quest 3 VR headset. The ZED 2i camera is mounted on a two-degree-of-freedom (2-DOF) robotic neck, which is controlled based on gyroscope sensor readings from the Quest 3 headset. This setup allows the camera to mimic the user's head movements, providing an immersive teleoperation experience.

## Features
- Real-time video streaming from ZED 2i stereo camera to Quest 3
- 2-DOF robotic neck for camera movement
- Head tracking using Quest 3 gyroscope data
- Unity project for VR rendering and control
- Python scripts for camera and robot control

## Project Structure
- `Assets/` - Unity project files
- `dynamixel/` - Python scripts for controlling the neck and camera streaming
- `start_camera_stream.bat` - Batch file to start the camera stream

## Requirements
- Meta Quest 3 VR headset
- ZED 2i stereo camera
- 2-DOF robotic neck (Dynamixel motors recommended)
- Windows PC
- Unity 2022.3.48f1
- Python 3.x
- ZED SDK
- Required Python packages (see `requirements.txt` if available)

## Setup
1. Clone this repository.
2. Set up the ZED 2i camera and install the ZED SDK.
3. Connect the 2-DOF neck to your PC and ensure Dynamixel drivers are installed.
4. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Open the Unity project in Unity Hub (version 2022.3.48f1).
6. Build and deploy the Unity project to the Quest 3 headset.
7. Run the camera streaming script:
   ```
   ./start_camera_stream.bat
   ```
8. Put on the Quest 3 headset and start the app.

## Usage
- Move your head while wearing the Quest 3. The ZED 2i camera will follow your head movements, and the video feed will be streamed to your headset in real time.

## License
MIT License

## Acknowledgments
- Stereolabs ZED SDK
- Meta Quest 3
- Dynamixel motors
