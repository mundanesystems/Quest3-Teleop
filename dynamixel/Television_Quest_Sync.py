import time
import numpy as np
import socket
from select import select

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

# --- Joint Limits (in radians) ---
LR_LIMITS_RAD = (-2.9, 2.9)
ID1_LIMITS_RAD = (-2.86, -0.31)
ID3_LIMITS_RAD = (0.37, 2.91)

# --- Robustness Settings ---
STALE_DATA_TIMEOUT = 1.0  # Seconds before data is considered stale
MIN_COMMAND_CHANGE = 0.005  # Radians (about 0.3 degrees) - prevents motor jitter

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
        print(f"✅ Robot zero position captured: {np.rad2deg(robot_zero_pos).round(1)} deg")
        
        # Test robot movement capability
        print("🔧 Testing robot movement...")
        test_pos = robot_zero_pos.copy()
        test_pos[0] += 0.1  # Small test movement on joint 0
        robot.command_joint_state(test_pos)
        time.sleep(0.5)
        
        actual_test_pos = robot.get_joint_state()
        if actual_test_pos is not None:
            movement_detected = np.linalg.norm(actual_test_pos - robot_zero_pos) > 0.05
            if movement_detected:
                print("✅ Robot movement test passed")
                robot.command_joint_state(robot_zero_pos)  # Return to zero
                time.sleep(0.5)
            else:
                print("❌ Robot movement test failed - robot not responding to commands")
                print("   Check: power, torque enable, cable connections")
        else:
            print("❌ Cannot read robot position during test")
            
    except Exception as e:
        print(f"❌ Error initializing robot: {e}")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    sock.setblocking(False)
    print("\n--- Listening for Quest data ---")
    print("Keep head still to establish Quest zero point...")

    # --- Establish Quest Zero Point ---
    quest_zero_pitch, quest_zero_yaw = 0, 0
    initial_data_found = False
    for _ in range(50):  # Try for 5 seconds (50 * 0.1s)
        ready, _, _ = select([sock], [], [], 0.1)
        if ready:
            try:
                data, _ = sock.recvfrom(1024)
                values = data.decode('utf-8').split(',')
                quest_zero_pitch = float(values[0])
                quest_zero_yaw = float(values[1])
                print(f"✅ Quest zero established at Pitch: {quest_zero_pitch:.1f}, Yaw: {quest_zero_yaw:.1f}")
                initial_data_found = True
                break
            except (ValueError, IndexError):
                continue
    
    if not initial_data_found:
        print("❌ Error: Could not establish zero point from Quest.")
        if robot: robot.close()
        sock.close()
        return
        
    print("\n✅ Ready. Move your head to control the robot. Press Ctrl+C to quit.")

    last_command_time = time.time()
    last_sent_command = robot_zero_pos.copy()

    try:
        while True:
            latest_data = None
            while True:
                ready, _, _ = select([sock], [], [], 0)
                if not ready: break
                latest_data, _ = sock.recvfrom(1024)

            if latest_data:
                last_command_time = time.time()
                try:
                    values = latest_data.decode('utf-8').split(',')
                    current_pitch_raw = float(values[0])
                    current_yaw_raw = float(values[1])
                except (ValueError, IndexError):
                    continue

                yaw_offset_deg = current_yaw_raw - quest_zero_yaw
                yaw_offset_deg = (yaw_offset_deg + 180) % 360 - 180

                pitch_offset_deg = current_pitch_raw - quest_zero_pitch
                pitch_offset_deg = (pitch_offset_deg + 180) % 360 - 180

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
                
                # --- Only send command if it has changed enough ---
                if np.linalg.norm(final_command - last_sent_command) > MIN_COMMAND_CHANGE:
                    try:
                        robot.command_joint_state(final_command)
                        last_sent_command = final_command
                        
                        # Read actual robot position after command
                        time.sleep(0.05)  # Small delay to let robot respond
                        actual_pos = robot.get_joint_state()
                        
                        if actual_pos is not None:
                            target_deg = np.rad2deg(final_command).round(1)
                            actual_deg = np.rad2deg(actual_pos).round(1)
                            print(f"Yaw: {yaw_offset_deg:+.1f}° | Pitch: {pitch_offset_deg:+.1f}° | Target: {target_deg} | Actual: {actual_deg}")
                            
                            # Check if robot actually moved
                            position_diff = np.linalg.norm(actual_pos - robot_zero_pos)
                            if position_diff < 0.01:  # Less than ~0.6 degrees total movement
                                print("⚠️  Robot not moving! Check:")
                                print("   - Power supply to motors")
                                print("   - Motor torque enable")
                                print("   - Cable connections")
                        else:
                            print(f"Yaw: {yaw_offset_deg:+.1f}° | Pitch: {pitch_offset_deg:+.1f}° | Command Sent | ❌ Can't read position")
                            
                    except Exception as e:
                        print(f"⚠️ Error sending command to robot: {e}")
                else:
                    # Uncomment this line if you want to see when commands are skipped due to small changes
                    # print(f"Yaw: {yaw_offset_deg:+.1f} deg | Pitch: {pitch_offset_deg:+.1f} deg | Change too small")
                    pass

            elif time.time() - last_command_time > STALE_DATA_TIMEOUT:
                print("🕒 Stale data, returning robot to zero...")
                robot.command_joint_state(robot_zero_pos)
                last_sent_command = robot_zero_pos.copy()
                last_command_time = time.time() # Reset timer to avoid repeated messages

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        print("\nReturning robot to zero position...")
        if robot:
            try:
                robot.command_joint_state(robot_zero_pos)
                time.sleep(1)
                robot.set_torque_mode(False)
                robot.close()
            except Exception as e:
                print(f"⚠️ Error during robot cleanup: {e}")
        sock.close()
        print("✅ Done.")

if __name__ == "__main__":
    main()