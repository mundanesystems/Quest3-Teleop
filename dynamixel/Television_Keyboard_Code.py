import time
import numpy as np
import keyboard  # Make sure to install this library: pip install keyboard
from dynamixel_robot import DynamixelRobot

# --- Robot Configuration ---
PORT_NAME = "COM4"
# The order is [L/R, U/D_1, U/D_2]
JOINT_IDS = [2, 1, 3]
JOINT_SIGNS = [1, 1, -1] 
BAUDRATE = 57600
LR_STEP_SIZE = 0.25  # Left/Right step size in radians
UD_STEP_SIZE = 0.3  # Up/Down step size in radians

# Limits for Left/Right motion (Joint ID 2, index 0)
LR_LIMITS_RAD = (-3.14 + LR_STEP_SIZE, 3.14 - LR_STEP_SIZE)

# Limits for Motor ID 1 (index 1)
ID1_LIMITS_RAD = (-2.86, -0.31)

# Limits for Motor ID 3 (index 2)
ID3_LIMITS_RAD = (0.37, 2.91)


def main():
    """
    Main function to initialize the robot and handle keyboard control.
    """
    robot = None
    print("Initializing robot...")

    try:
        robot = DynamixelRobot(
            joint_ids=JOINT_IDS,
            joint_signs=JOINT_SIGNS,
            real=True,
            port=PORT_NAME,
            baudrate=BAUDRATE,
        )
    except Exception as e:
        print(f"Error initializing robot on port {PORT_NAME}: {e}")
        return

    print("Robot initialized successfully. Enabling torque...")
    robot.set_torque_mode(True)
    time.sleep(0.2)

    # --- Homing Logic ---
    # Read the initial physical position and set it as our "zero" point.
    home_position = robot.get_joint_state()
    if home_position is not None:
        print(f"Home position captured at: [{home_position[0]:.2f}, {home_position[1]:.2f}, {home_position[2]:.2f}] rad")
    else:
        print("Could not read starting position. Assuming [0,0,0].")
        home_position = np.array([0.0, 0.0, 0.0])

    # --- NEW SAFETY CHECK ---
    # Check if the starting position is outside the absolute limits for each joint.
    safe_start = True
    if not (LR_LIMITS_RAD[0] <= home_position[0] <= LR_LIMITS_RAD[1]):
        print(f"\n--- SAFETY ERROR: Joint ID {JOINT_IDS[0]} (L/R) is out of bounds! ---")
        print(f"Position is {home_position[0]:.2f} rad, but limits are [{LR_LIMITS_RAD[0]:.2f}, {LR_LIMITS_RAD[1]:.2f}] rad.")
        safe_start = False
    
    if not (ID1_LIMITS_RAD[0] <= home_position[1] <= ID1_LIMITS_RAD[1]):
        print(f"\n--- SAFETY ERROR: Joint ID {JOINT_IDS[1]} is out of bounds! ---")
        print(f"Position is {home_position[1]:.2f} rad, but limits are [{ID1_LIMITS_RAD[0]:.2f}, {ID1_LIMITS_RAD[1]:.2f}] rad.")
        safe_start = False

    if not (ID3_LIMITS_RAD[0] <= home_position[2] <= ID3_LIMITS_RAD[1]):
        print(f"\n--- SAFETY ERROR: Joint ID {JOINT_IDS[2]} is out of bounds! ---")
        print(f"Position is {home_position[2]:.2f} rad, but limits are [{ID3_LIMITS_RAD[0]:.2f}, {ID3_LIMITS_RAD[1]:.2f}] rad.")
        safe_start = False

    if not safe_start:
        print("\nPlease manually move the robot within the limits before starting.")
        print("--------------------")
        if robot:
            robot.set_torque_mode(False)
            robot.close()
        return # Exit the script

    print("\n--- Ready for Keyboard Control ---")
    print(f"ID {JOINT_IDS[0]} (L/R) limits: {LR_LIMITS_RAD[0]} to {LR_LIMITS_RAD[1]} radians")
    print(f"ID {JOINT_IDS[1]} limits: {ID1_LIMITS_RAD[0]} to {ID1_LIMITS_RAD[1]} radians")
    print(f"ID {JOINT_IDS[2]} limits: {ID3_LIMITS_RAD[0]} to {ID3_LIMITS_RAD[1]} radians")
    print("Press 'q' to quit.")
    print("------------------------------------")

    try:
        while True:
            moved = False
            
            current_absolute_position = robot.get_joint_state()
            if current_absolute_position is None:
                time.sleep(0.05)
                continue

            next_absolute_position = current_absolute_position.copy()

            if keyboard.is_pressed('right arrow'):
                next_absolute_position[0] += LR_STEP_SIZE
            elif keyboard.is_pressed('left arrow'):
                next_absolute_position[0] -= LR_STEP_SIZE
            
            if keyboard.is_pressed('up arrow'):
                next_absolute_position[1] += UD_STEP_SIZE
                next_absolute_position[2] += UD_STEP_SIZE
            elif keyboard.is_pressed('down arrow'):
                next_absolute_position[1] -= UD_STEP_SIZE
                next_absolute_position[2] -= UD_STEP_SIZE
        

            final_command = current_absolute_position.copy()

            if LR_LIMITS_RAD[0] <= next_absolute_position[0] <= LR_LIMITS_RAD[1]:
                final_command[0] = next_absolute_position[0]
            
            if ID1_LIMITS_RAD[0] <= next_absolute_position[1] <= ID1_LIMITS_RAD[1]:
                final_command[1] = next_absolute_position[1]

            if ID3_LIMITS_RAD[0] <= next_absolute_position[2] <= ID3_LIMITS_RAD[1]:
                final_command[2] = next_absolute_position[2]

            if np.any(final_command != current_absolute_position):
                moved = True

            if keyboard.is_pressed('q'):
                print("\n'q' pressed, exiting.")
                break

            if moved:
                robot.command_joint_state(final_command)
                print(f"Commanding Abs Pos: [{final_command[0]:.2f}, {final_command[1]:.2f}, {final_command[2]:.2f}] | Current Motor Pos: [{current_absolute_position[0]:.2f}, {current_absolute_position[1]:.2f}, {current_absolute_position[2]:.2f}]", end='\r')

            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Exiting.")
    finally:
        print("\nDisabling torque...")
        if robot:
            print("Returning to home position slowly...")
            current_pos = robot.get_joint_state()
            while np.linalg.norm(current_pos - home_position) > UD_STEP_SIZE:
                direction = home_position - current_pos
                step = direction / np.linalg.norm(direction) * UD_STEP_SIZE
                next_pos = current_pos + step
                robot.command_joint_state(next_pos)
                current_pos = robot.get_joint_state()
                print(f"Moving home... at [{current_pos[0]:.2f}, {current_pos[1]:.2f}, {current_pos[2]:.2f}]", end='\r')
                time.sleep(0.02)
            
            robot.command_joint_state(home_position)
            time.sleep(0.5)

            robot.set_torque_mode(False)
            robot.close()
        print("\nDone.")


if __name__ == "__main__":
    main()
