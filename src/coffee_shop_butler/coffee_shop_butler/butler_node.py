#!/usr/bin/env python3
"""
Butler Robot Node — Coffee Shop
================================
Delivery sequence (fixed cycle, no confirmation topics required):

  Every 10 seconds the robot wakes up, goes to the kitchen to collect
  the order, then delivers to Table 1, waits 5 s, delivers to Table 2,
  waits 5 s, delivers to Table 3, waits 5 s, then returns home.

State machine
-------------
  IDLE              — waiting for the 10-second collect timer to fire
  GOING_KITCHEN     — navigating to kitchen
  AT_KITCHEN        — collecting order (instant, no confirmation)
  GOING_TABLE       — navigating to next table
  AT_TABLE          — 5-second wait at each table for pick-up
  GOING_KITCHEN_RETURN — revisit kitchen (cancelled order food return)
  RETURNING_HOME    — heading back to home pose
  FAULT             — unrecoverable navigation error

Topics published
----------------
  /butler/status  (std_msgs/String) — human-readable log line
  /butler/state   (std_msgs/String) — current state enum name

Topics subscribed
-----------------
  /butler/cancel  (std_msgs/String) — "table1" | "table2" | "table3"
"""

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String


# ── Timing constants ────────────────────────────────────────────────────────
ORDER_COLLECT_INTERVAL_S = 10.0   # how long to wait before heading to kitchen
TABLE_WAIT_S             = 5.0    # dwell time at each table
NAV_TIMEOUT_S            = 60.0   # max time allowed for a single nav goal


# ── Enumerations ─────────────────────────────────────────────────────────────
class RobotState(Enum):
    IDLE                 = auto()
    GOING_KITCHEN        = auto()
    AT_KITCHEN           = auto()
    GOING_TABLE          = auto()
    AT_TABLE             = auto()
    GOING_KITCHEN_RETURN = auto()
    RETURNING_HOME       = auto()
    FAULT                = auto()


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class Order:
    table_id: str
    cancelled: bool = False
    delivered: bool = False


@dataclass
class Waypoint:
    name: str
    pose: PoseStamped


# ── Helper: build a PoseStamped ───────────────────────────────────────────────
def _make_pose(x: float, y: float, yaw: float = 0.0) -> PoseStamped:
    p = PoseStamped()
    p.header.frame_id = "map"
    p.pose.position.x = x
    p.pose.position.y = y
    p.pose.position.z = 0.0
    p.pose.orientation.z = math.sin(yaw / 2.0)
    p.pose.orientation.w = math.cos(yaw / 2.0)
    return p


# ── Butler Node ───────────────────────────────────────────────────────────────
class ButlerNode(Node):
    """
    Coffee shop butler robot.

    On startup the node waits 10 seconds (ORDER_COLLECT_INTERVAL_S), then
    automatically sends the robot to the kitchen, collects the order and
    delivers to Table 1 → Table 2 → Table 3, spending TABLE_WAIT_S at each
    table, before returning home.  The cycle restarts immediately after the
    robot is back at home.
    """

    # ── Init ──────────────────────────────────────────────────────────────────
    def __init__(self) -> None:
        super().__init__("butler_node")

        # State
        self._state: RobotState = RobotState.IDLE
        self._lock = threading.Lock()
        self._cancelled_tables: set = set()

        # Fixed delivery sequence
        self._table_sequence: List[str] = ["table1", "table2", "table3"]

        # Waypoints
        self._waypoints: Dict[str, Waypoint] = {
            "home":    Waypoint("home",    _make_pose(-2.0,  0.0, 0.0)),
            "kitchen": Waypoint("kitchen", _make_pose( 2.5,  0.0, math.pi)),
            "table1":  Waypoint("table1",  _make_pose( 0.0,  3.0, -math.pi / 2)),
            "table2":  Waypoint("table2",  _make_pose( 0.0,  0.0, 0.0)),
            "table3":  Waypoint("table3",  _make_pose( 0.0, -3.0,  math.pi / 2)),
        }

        # Nav2 action client
        self._nav_cb_group = MutuallyExclusiveCallbackGroup()
        self._nav_client = ActionClient(
            self,
            NavigateToPose,
            "navigate_to_pose",
            callback_group=self._nav_cb_group,
        )

        # Publishers
        self._status_pub = self.create_publisher(String, "/butler/status", 10)
        self._state_pub  = self.create_publisher(String, "/butler/state",  10)

        # Subscriptions
        self.create_subscription(
            String, "/butler/cancel", self._on_cancel, 10
        )

        # Heartbeat timer (publishes state every second)
        self.create_timer(1.0, self._publish_state)

        # Main worker thread
        self._worker = threading.Thread(
            target=self._delivery_loop, daemon=True
        )
        self._worker.start()

        self._log(
            f"Butler node ready. "
            f"First kitchen run in {ORDER_COLLECT_INTERVAL_S:.0f} s."
        )

    # ── Subscription callbacks ────────────────────────────────────────────────
    def _on_cancel(self, msg: String) -> None:
        tid = msg.data.strip().lower()
        if tid in self._waypoints:
            with self._lock:
                self._cancelled_tables.add(tid)
            self._log(f"Cancel received for {tid}.")
        else:
            self.get_logger().warn(f'Unknown cancel target "{tid}" — ignored.')

    # ── Main delivery loop ────────────────────────────────────────────────────
    def _delivery_loop(self) -> None:
        """
        Infinite loop running in a daemon thread.

        Cycle:
          [IDLE] ─ wait ORDER_COLLECT_INTERVAL_S ──►
          [GOING_KITCHEN] ──► [AT_KITCHEN] (collect) ──►
          for each table:
            [GOING_TABLE] ──► [AT_TABLE] (wait TABLE_WAIT_S) ──►
          [RETURNING_HOME] ──► [IDLE] ──► repeat
        """
        while rclpy.ok():
            # ── 1. Wait before collecting ──────────────────────────────────
            self._set_state(RobotState.IDLE)
            self._log(
                f"Idle. Next collection run in {ORDER_COLLECT_INTERVAL_S:.0f} s."
            )
            self._interruptible_sleep(ORDER_COLLECT_INTERVAL_S)

            if not rclpy.ok():
                break

            # Reset cancellations for this fresh run
            with self._lock:
                self._cancelled_tables.clear()

            # ── 2. Go to kitchen ───────────────────────────────────────────
            self._set_state(RobotState.GOING_KITCHEN)
            self._log("Heading to kitchen to collect orders.")
            if not self._navigate("kitchen"):
                self._log("Navigation to kitchen failed — returning home.")
                self._return_home()
                continue

            # ── 3. Collect order at kitchen ────────────────────────────────
            self._set_state(RobotState.AT_KITCHEN)
            self._log("At kitchen — order collected. Starting deliveries.")

            # ── 4. Deliver to each table ───────────────────────────────────
            undelivered_food = False   # flag: food not handed over → revisit kitchen

            for table in self._table_sequence:
                with self._lock:
                    is_cancelled = table in self._cancelled_tables

                if is_cancelled:
                    self._log(f"Order for {table} was cancelled — skipping.")
                    undelivered_food = True
                    continue

                # Navigate to table
                self._set_state(RobotState.GOING_TABLE)
                self._log(f"Navigating to {table}.")
                if not self._navigate(table):
                    self._log(f"Navigation to {table} failed — skipping.")
                    undelivered_food = True
                    continue

                # Dwell at table
                self._set_state(RobotState.AT_TABLE)
                self._log(
                    f"At {table} — waiting {TABLE_WAIT_S:.0f} s for customer pick-up."
                )
                self._interruptible_sleep(TABLE_WAIT_S)

                # Check if cancelled while waiting
                with self._lock:
                    still_cancelled = table in self._cancelled_tables
                if still_cancelled:
                    self._log(f"Order for {table} cancelled during wait — food not delivered.")
                    undelivered_food = True
                else:
                    self._log(f"Delivery to {table} complete. ✓")

            # ── 5. Revisit kitchen if food not fully delivered ─────────────
            if undelivered_food:
                self._set_state(RobotState.GOING_KITCHEN_RETURN)
                self._log("Returning undelivered food to kitchen.")
                self._navigate("kitchen")
                self._log("Food returned to kitchen.")

            # ── 6. Return home ─────────────────────────────────────────────
            self._return_home()

    # ── Navigation helper ─────────────────────────────────────────────────────
    def _navigate(self, location: str) -> bool:
        """
        Send a NavigateToPose goal; block until success or failure.
        Returns True on success, False otherwise.
        """
        wp = self._waypoints.get(location)
        if wp is None:
            self.get_logger().error(f"Unknown waypoint: {location}")
            return False

        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 action server not available.")
            return False

        goal = NavigateToPose.Goal()
        goal.pose = wp.pose
        goal.pose.header.stamp = self.get_clock().now().to_msg()

        send_future = self._nav_client.send_goal_async(goal)

        # Wait for goal acceptance
        deadline = time.time() + 10.0
        while not send_future.done():
            if not rclpy.ok() or time.time() > deadline:
                return False
            time.sleep(0.05)

        goal_handle = send_future.result()
        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error(f"Goal to {location} rejected.")
            return False

        result_future = goal_handle.get_result_async()

        # Wait for navigation result
        deadline = time.time() + NAV_TIMEOUT_S
        while not result_future.done():
            if not rclpy.ok():
                return False
            if time.time() > deadline:
                self.get_logger().error(
                    f"Navigation to {location} timed out — cancelling goal."
                )
                goal_handle.cancel_goal_async()
                return False
            time.sleep(0.05)

        status = result_future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(f"Arrived at {location}.")
            return True

        self.get_logger().warn(
            f"Navigation to {location} ended with status={status}."
        )
        return False

    # ── Utilities ─────────────────────────────────────────────────────────────
    def _return_home(self) -> None:
        self._set_state(RobotState.RETURNING_HOME)
        self._log("Returning to home position.")
        self._navigate("home")
        self._set_state(RobotState.IDLE)
        self._log("Back at home. Ready for next cycle.")

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep in short chunks so we stay responsive to rclpy.ok()."""
        end = time.time() + seconds
        while time.time() < end and rclpy.ok():
            time.sleep(0.1)

    def _set_state(self, state: RobotState) -> None:
        self._state = state
        self._publish_state()

    def _publish_state(self) -> None:
        msg = String()
        msg.data = self._state.name
        self._state_pub.publish(msg)

    def _log(self, text: str) -> None:
        self.get_logger().info(text)
        msg = String()
        msg.data = f"[{self._state.name}] {text}"
        self._status_pub.publish(msg)


# ── Entry point ───────────────────────────────────────────────────────────────
def main(args=None) -> None:
    rclpy.init(args=args)
    node = ButlerNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
