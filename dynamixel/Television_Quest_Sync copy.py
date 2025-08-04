import time
import numpy as np
import socket
from select import select # Used to check for data without blocking
from dynamixel_robot import DynamixelRobot

# --- Configuration ---
PORT_NAME = "COM4"
JOINT_IDS = [2, 1, 3]
JOINT_SIGNS = [1, 1, -1]
BAUDRATE = 57600
LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 9050
YAW_SENSITIVITY = 1.0
PITCH_SENSITIVITY = -1.0

# --- Joint Limits ---
LR_LIMITS_RAD = (-2.9, 2.9)
ID1_LIMITS_RAD = (-2.86, -0.31)
ID3_LIMITS_RAD = (0.37, 2.91)

def main():
    robot = None
    try:
        robot = DynamixelRobot(
            joint_ids=JOINT_IDS, joint_signs=JOINT_SIGNS, real=True,
            port=PORT_NAME, baudrate=BAUDRATE
        )
        robot.set_torque_mode(True)
        time.sleep(0.2)
        robot_zero_pos = robot.get_joint_state()
        if robot_zero_pos is None:
            raise ConnectionError("Could not read robot's starting position.")
        print(f"Robot zero position captured at: {np.rad2deg(robot_zero_pos).round(1)} deg")
        print("This will be used as the reference position for all movements.")
    except Exception as e:
        print(f"Error initializing robot: {e}")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    sock.setblocking(False) # Make the socket non-blocking
    print("\n--- Listening for Quest data ---")
    print("Keep head still to establish Quest zero point...")

    # --- Establish Quest Zero Point ---
    quest_zero_pitch, quest_zero_yaw = 0, 0
    start_time = time.time()
    initial_data_found = False
    while time.time() - start_time < 5: # Try for 5 seconds
        ready_sockets, _, _ = select([sock], [], [], 0.1)
        if ready_sockets:
            data, addr = sock.recvfrom(1024)
            try:
                values = data.decode('utf-8').split(',')
                quest_zero_pitch = float(values[0])
                quest_zero_yaw = float(values[1])
                print(f"Quest zero established at Pitch: {quest_zero_pitch:.1f}, Yaw: {quest_zero_yaw:.1f}")
                initial_data_found = True
                break
            except (ValueError, IndexError):
                continue # Ignore corrupted packet
    
    if not initial_data_found:
        print("Error: Could not establish zero point from Quest.")
        if robot: robot.close()
        sock.close()
        return
        
    print("Ready. Move your head to control the robot. Press Ctrl+C to quit.")
    print(f"Robot will move relative to zero position: {np.rad2deg(robot_zero_pos).round(1)} deg")

    try:
        while True:
            latest_data = None
            
            # --- Empty the UDP buffer and keep only the last packet ---
            while True:
                ready_sockets, _, _ = select([sock], [], [], 0)
                if not ready_sockets:
                    break # Buffer is empty, stop reading
                
                # Read the waiting packet
                data, addr = sock.recvfrom(1024)
                # Store it, overwriting any previous one from this cycle
                latest_data = data

            if latest_data is None:
                time.sleep(0.01) # No new data, pause briefly
                continue

            # --- Process the most recent valid packet ---
            try:
                values = latest_data.decode('utf-8').split(',')
                current_pitch_raw = float(values[0])
                current_yaw_raw = float(values[1])
            except (ValueError, IndexError):
                continue # Skip corrupted packet

            yaw_offset_deg = current_yaw_raw - quest_zero_yaw
            if yaw_offset_deg > 180: yaw_offset_deg -= 360
            if yaw_offset_deg < -180: yaw_offset_deg += 360

            pitch_offset_deg = current_pitch_raw - quest_zero_pitch
            if pitch_offset_deg > 180: pitch_offset_deg -= 360
            if pitch_offset_deg < -180: pitch_offset_deg += 360

            yaw_offset_rad = np.deg2rad(yaw_offset_deg) * YAW_SENSITIVITY
            pitch_offset_rad = np.deg2rad(pitch_offset_deg) * PITCH_SENSITIVITY

            target_pos = robot_zero_pos.copy()
            target_pos[0] -= yaw_offset_rad
            target_pos[1] += pitch_offset_rad
            target_pos[2] += pitch_offset_rad

            final_command = np.clip(target_pos,
                [LR_LIMITS_RAD[0], ID1_LIMITS_RAD[0], ID3_LIMITS_RAD[0]],
                [LR_LIMITS_RAD[1], ID1_LIMITS_RAD[1], ID3_LIMITS_RAD[1]]
            )
            
            robot.command_joint_state(final_command)
            # Use a standard print() so each message is on a new line
            print(f"Yaw Offset: {yaw_offset_deg:+.1f} deg | Pitch Offset: {pitch_offset_deg:+.1f} deg")

    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        print("\nReturning robot to zero position...")
        if robot:
            robot.command_joint_state(robot_zero_pos)
            time.sleep(1)
            robot.set_torque_mode(False)
            robot.close()
        sock.close()
        print("Done.")

if __name__ == "__main__":
    main()