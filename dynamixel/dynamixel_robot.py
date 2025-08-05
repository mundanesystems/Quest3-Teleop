"""
dynamixel_robot.py
------------------
Defines the DynamixelRobot class, which adapts the generic Robot protocol to work with Dynamixel servos using a driver.
This is a simplified version that works with absolute, wrapped angles.
"""

from typing import Dict, Optional, Sequence
import numpy as np
from robot import Robot
from driver import DynamixelDriver, DynamixelDriverProtocol, FakeDynamixelDriver
import time

def wrap_to_pi(radians_array: np.ndarray) -> np.ndarray:
    """Wraps an angle in radians to the range [-pi, pi]."""
    return (radians_array + np.pi) % (2 * np.pi) - np.pi

class DynamixelRobot(Robot):
    """A class representing a Dynamixel-based robot."""

    def __init__(
        self,
        joint_ids: Sequence[int],
        joint_offsets: Optional[Sequence[float]] = None,
        joint_signs: Optional[Sequence[int]] = None,
        real: bool = False,
        port: str = "COM4",
        baudrate: int = 57600,
    ):
        print(f"attempting to connect to port: {port}")
        self._joint_ids = joint_ids
        self._driver: DynamixelDriverProtocol

        if joint_offsets is None:
            self._joint_offsets = np.zeros(len(joint_ids))
        else:
            self._joint_offsets = np.array(joint_offsets)

        if joint_signs is None:
            self._joint_signs = np.ones(len(joint_ids))
        else:
            self._joint_signs = np.array(joint_signs)

        if real:
            self._driver = DynamixelDriver(joint_ids, port=port, baudrate=baudrate)
        else:
            self._driver = FakeDynamixelDriver(joint_ids)
        
        self._torque_on = False

    def num_dofs(self) -> int:
        return len(self._joint_ids)

    def get_joint_state(self) -> np.ndarray:
        """
        Return the current joint state, wrapped to [-pi, pi].
        This function simply reads the motor's state.
        """
        pos_from_driver = self._driver.get_joints()
        pos = (pos_from_driver - self._joint_offsets) * self._joint_signs
        return wrap_to_pi(pos)

    def command_joint_state(self, joint_state: np.ndarray) -> None:
        """
        Command the robot to a given joint state.
        The angle is wrapped to the [-pi, pi] range here, just before
        being sent to the driver.
        """
        set_value = (joint_state * self._joint_signs) + self._joint_offsets
        set_value = wrap_to_pi(set_value)
        self._driver.set_joints(set_value)

    def command_and_get_rtt(self, joint_state: np.ndarray):
        """
        Sends a command and then immediately reads the robot's state,
        measuring the round-trip time for the hardware communication.
        """
        start_time = time.perf_counter()
        self.command_joint_state(joint_state)
        actual_pos = self.get_joint_state()
        end_time = time.perf_counter()
        
        rtt_ms = (end_time - start_time) * 1000
        return actual_pos, rtt_ms

    def set_torque_mode(self, mode: bool):
        if mode == self._torque_on:
            return
        self._driver.set_torque_mode(mode)
        self._torque_on = mode

    def get_observations(self) -> Dict[str, np.ndarray]:
        return {"joint_state": self.get_joint_state()}
        
    def close(self):
        """Closes the connection to the robot by calling the driver's close method."""
        if self._driver:
            self._driver.close()