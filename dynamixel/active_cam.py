
# This script defines configuration and agent logic for controlling a Dynamixel-based robot (e.g., a camera mount)
# using a specified serial port. It provides a configuration dataclass, a mapping for different robot setups,
# and an agent class that wraps robot control and state retrieval. The main block demonstrates a simple
# sweep of a joint through a range of angles, printing both commanded and actual joint positions.

import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple
import numpy as np
from .agent import Agent
from .dynamixel_robot import DynamixelRobot
# from agent import Agent
# from dynamixel_robot import DynamixelRobot



# Configuration dataclass for a Dynamixel robot.
# Stores joint IDs, offsets, sign directions, and (optionally) gripper configuration.
@dataclass
class DynamixelRobotConfig:
    joint_ids: Sequence[int]
    """The joint ids of dynamixel robot. Usually (1, 2, 3 ...)."""

    joint_offsets: Sequence[float]
    """The joint offsets of robot. There needs to be a joint offset for each joint_id and should be a multiple of pi/2."""

    joint_signs: Sequence[int]
    """The joint signs is -1 for all dynamixel. Used to flip direction if needed."""

    gripper_config: Tuple[int, int, int]
    """Reserved for later work (not used in this file)."""

    # Post-initialization check to ensure config consistency
    def __post_init__(self):
        assert len(self.joint_ids) == len(self.joint_offsets)
        assert len(self.joint_ids) == len(self.joint_signs)

    def make_robot(
        self, port: str = "COM4", start_joints: Optional[np.ndarray] = None
    ) -> DynamixelRobot:
        """
        Factory method to create a DynamixelRobot instance using this config.
        """
        return DynamixelRobot(
            joint_ids=self.joint_ids,
            joint_offsets=list(self.joint_offsets),
            real=True,
            joint_signs=list(self.joint_signs),
            port=port,
            gripper_config=self.gripper_config,
            start_joints=start_joints,
        )


# Mapping from serial port path to robot configuration.
# This allows supporting multiple robots with different calibration/configs.
# Add new entries for each robot/port as needed.
PORT_CONFIG_MAP: Dict[str, DynamixelRobotConfig] = {
    #! Example config for a camera mount robot
    "COM4": DynamixelRobotConfig(
        joint_ids=(2, 3),
        joint_offsets=(
            2*np.pi/2, 
            2*np.pi/2, 
        ),
        joint_signs=(-1, -1),
        gripper_config=None,  # No gripper for this robot
    ), 
}


# Agent class that wraps a DynamixelRobot and provides a simple interface for action/state.
# The agent can be initialized with a config or will look up the config based on the port.
class DynamixelAgent(Agent):
    def __init__(
        self,
        port: str,
        dynamixel_config: Optional[DynamixelRobotConfig] = None,
        start_joints: Optional[np.ndarray] = None,
        cap_num: int = 42,
    ):
        # Initialize the Dynamixel robot using the provided config or by looking up the port in the config map.
        if dynamixel_config is not None:
            self._robot = dynamixel_config.make_robot(
                port=port, start_joints=start_joints
            )
        else:
            # If no config is provided, ensure the port exists and is in the config map.
            assert os.path.exists(port), port
            assert port in PORT_CONFIG_MAP, f"Port {port} not in config map"

            # Retrieve config for this port and create the robot instance.
            config = PORT_CONFIG_MAP[port]
            self._robot = config.make_robot(port=port, start_joints=start_joints)

    def act(self, obs: Dict[str, np.ndarray]) -> np.ndarray: 
        """
        Returns the current joint state of the robot. Ignores the observation input.
        """
        return self._robot.get_joint_state()


# Example usage: sweep the second joint from min to max radians, printing commanded and true values.
if __name__ == "__main__":
    # Initialize agent for a specific robot/port (update port as needed)
    agent = DynamixelAgent(port="COM4")

    # Enable torque mode for the robot (required for movement)
    agent._robot.set_torque_mode(True)

    min_radians = -1.57  # Minimum joint angle (radians)
    max_radians = 1.57   # Maximum joint angle (radians)
    interval = 0.1       # Step size (radians)

    current_radian = 0
    while current_radian <= max_radians:
        # Get current joint state (for logging)
        action = agent.act(1)
        print("now action                     : ", [f"{x:.3f}" for x in action])
        command = [0, 0]
        # Command the robot to move the second joint to current_radian
        agent._robot.command_joint_state([0, current_radian])
        time.sleep(0.1) 
        # Read back the true joint values from the hardware
        true_value = agent._robot._driver.get_joints()    
        print("true value                 : ", [f"{x:.3f}" for x in true_value])
        current_radian += interval
