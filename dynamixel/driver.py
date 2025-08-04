"""
driver.py
---------
Implements the low-level driver logic for communicating with Dynamixel servos using the dynamixel_sdk.
This version uses individual writes for responsiveness with fast keyboard polling.
"""

import time
from threading import Event, Lock, Thread
from typing import Protocol, Sequence
import numpy as np
# dynamixel_sdk imports for hardware communication
from dynamixel_sdk.group_sync_read import GroupSyncRead
from dynamixel_sdk.packet_handler import PacketHandler
from dynamixel_sdk.port_handler import PortHandler
from dynamixel_sdk.robotis_def import (
    COMM_SUCCESS,
)

# Corrected memory addresses for the Dynamixel motors.
ADDR_TORQUE_ENABLE = 64
ADDR_GOAL_POSITION = 116
LEN_GOAL_POSITION = 4
ADDR_PRESENT_POSITION = 132
LEN_PRESENT_POSITION = 4
TORQUE_ENABLE = 1
TORQUE_DISABLE = 0



# Protocol for any Dynamixel driver (real or fake)
class DynamixelDriverProtocol(Protocol):
    def set_joints(self, joint_angles: Sequence[float]): ...
    def torque_enabled(self) -> bool: ...
    def set_torque_mode(self, enable: bool): ...
    def get_joints(self) -> np.ndarray: ...
    def close(self): ...



# Fake driver for testing without hardware
class FakeDynamixelDriver(DynamixelDriverProtocol):
    def __init__(self, ids: Sequence[int]):
        self._ids = ids
        self._joint_angles = np.zeros(len(ids), dtype=int)
        self._torque_enabled = False
    def set_joints(self, joint_angles: Sequence[float]):
        self._joint_angles = np.array(joint_angles)
    def torque_enabled(self) -> bool:
        return self._torque_enabled
    def set_torque_mode(self, enable: bool):
        self._torque_enabled = enable
    def get_joints(self) -> np.ndarray:
        return self._joint_angles.copy()
    def close(self):
        pass



# Real driver for hardware control of Dynamixel servos
class DynamixelDriver(DynamixelDriverProtocol):
    def __init__(
        self, ids: Sequence[int], port: str = "/dev/ttyUSB0", baudrate: int = 57600
    ):
        self._ids = ids
        self._joint_angles = np.zeros(len(ids), dtype=int)
        self._port_lock = Lock()

        self._portHandler = PortHandler(port)
        self._packetHandler = PacketHandler(2.0)

        self._groupSyncRead = GroupSyncRead(
            self._portHandler,
            self._packetHandler,
            ADDR_PRESENT_POSITION,
            LEN_PRESENT_POSITION,
        )

        if not self._portHandler.openPort():
            raise RuntimeError(f"Failed to open the port: {port}")

        if not self._portHandler.setBaudRate(baudrate):
            raise RuntimeError(f"Failed to change the baudrate to {baudrate}")

        for dxl_id in self._ids:
            if not self._groupSyncRead.addParam(dxl_id):
                raise RuntimeError(
                    f"Failed to add read parameter for Dynamixel with ID {dxl_id}"
                )

        self._torque_enabled = False
        self._stop_thread = Event()
        self._start_reading_thread()

    def set_joints(self, joint_angles: Sequence[float]):
        """Commands the servos using individual write commands for responsiveness."""
        if not self._torque_enabled:
            return

        with self._port_lock:
            for dxl_id, angle in zip(self._ids, joint_angles):
                position_value = int((angle * 2048 / np.pi) + 2048)
                position_value = max(0, min(4095, position_value))
                
                self._packetHandler.write4ByteTxRx(self._portHandler, dxl_id, ADDR_GOAL_POSITION, position_value)

    def torque_enabled(self) -> bool:
        return self._torque_enabled

    def set_torque_mode(self, enable: bool):
        """Enable or disable torque for all servos individually."""
        torque_value = TORQUE_ENABLE if enable else TORQUE_DISABLE
        with self._port_lock:
            for dxl_id in self._ids:
                self._packetHandler.write1ByteTxRx(self._portHandler, dxl_id, ADDR_TORQUE_ENABLE, torque_value)
        self._torque_enabled = enable

    def _start_reading_thread(self):
        """Start a background thread to read joint angles."""
        self._reading_thread = Thread(target=self._read_joint_angles)
        self._reading_thread.daemon = True
        self._reading_thread.start()

    def _read_joint_angles(self):
        """Background thread function to continuously read joint angles from hardware."""
        while not self._stop_thread.is_set():
            with self._port_lock:
                dxl_comm_result = self._groupSyncRead.txRxPacket()
                if dxl_comm_result == COMM_SUCCESS:
                    temp_angles = self._joint_angles.copy()
                    read_success = True
                    for i, dxl_id in enumerate(self._ids):
                        if self._groupSyncRead.isAvailable(dxl_id, ADDR_PRESENT_POSITION, LEN_PRESENT_POSITION):
                            angle = self._groupSyncRead.getData(dxl_id, ADDR_PRESENT_POSITION, LEN_PRESENT_POSITION)
                            temp_angles[i] = np.int32(np.uint32(angle))
                        else:
                            read_success = False
                            break
                    
                    if read_success:
                        self._joint_angles = temp_angles
            time.sleep(0.02)

    def get_joints(self) -> np.ndarray:
        """Return the current joint angles (in radians) as read from hardware."""
        with self._port_lock:
             _j = self._joint_angles.copy()
        return (_j - 2048.0) * np.pi / 2048.0

    def close(self):
        """Clean up and close the hardware connection."""
        print("Closing port and stopping thread...")
        self._stop_thread.set()
        if self._reading_thread.is_alive():
            self._reading_thread.join(timeout=1.0)
        try:
            self.set_torque_mode(False)
        except Exception as e:
            print(f"Could not disable torque on close: {e}")
        self._portHandler.closePort()
