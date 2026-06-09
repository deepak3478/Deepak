#!/usr/bin/env python3
"""
table1_controller.py
====================
Interactive keyboard controller for the Cafe Butler Robot.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import threading
import sys

MENU = """\
============================================================
   TABLE 1 CONTROLLER - Cafe Butler Robot
============================================================
  [1] Scenario 1  Home -> Kitchen -> Table1 -> Home (No Confirmation)
  [2] Scenario 2  Home -> Kitchen/Table1 (wait confirm) -> Home (Timeout -> Home)
  [3] Scenario 3  Home -> Kitchen/Table1 (wait confirm) -> Home (Table Timeout -> Kitchen -> Home)
  [4] Scenario 4  Home -> Kitchen/Table1 (Cancel going to Table -> Kitchen -> Home)
  [5] Scenario 5  Home -> Kitchen -> Multiple Tables -> Home (No Confirmation)
  [6] Scenario 6  Home -> Kitchen -> Multiple Tables (Unconfirmed -> Kitchen -> Home)
  [7] Scenario 7  Home -> Kitchen -> Multiple Tables (Skip Table2 -> Kitchen -> Home)
------------------------------------------------------------
  [k] Send KITCHEN staff confirmation
  [c] Send CUSTOMER / table confirmation
------------------------------------------------------------
  [x] Skip TABLE1   [y] Skip TABLE2   [z] Skip TABLE3
  [q] QUIT / CANCEL: stop active task, navigate to Home
============================================================
Enter key: """


class Table1Controller(Node):
    """Keyboard-driven controller node for Cafe Butler Robot."""

    def __init__(self):
        super().__init__('table1_controller')

        self._order_pub   = self.create_publisher(String, '/butler/order',   10)
        self._confirm_pub = self.create_publisher(String, '/butler/confirm', 10)
        self._cancel_pub  = self.create_publisher(String, '/butler/cancel',  10)

        self.create_subscription(
            String, '/butler/status', self._status_cb, 20)

        self.get_logger().info("[CTRL] TABLE 1 Controller ready.")

    def _status_cb(self, msg: String):
        text = msg.data.strip()
        if text:
            print(f"\r  [ROBOT] {text}", flush=True)

    def _send_order(self, scenario: int, tables: str):
        payload = f"{scenario}:{tables}"
        self._order_pub.publish(String(data=payload))
        self.get_logger().info(f"[CTRL] Order sent -> {payload}")

    def _send_confirm(self, source: str):
        self._confirm_pub.publish(String(data=source))
        self.get_logger().info(f"[CTRL] Confirmation sent -> {source}")

    def _send_cancel(self, target: str):
        self._cancel_pub.publish(String(data=target))
        self.get_logger().info(f"[CTRL] Cancel/Skip sent -> {target}")


def main(args=None):
    rclpy.init(args=args)
    node = Table1Controller()

    spin_thread = threading.Thread(
        target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    try:
        while rclpy.ok():
            try:
                key = input(MENU).strip().lower()
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n[CTRL] KeyboardInterrupt — sending Quit...")
                node._send_cancel('all')
                break

            if key == '1':
                print("\n[KEY-1] Dispatching Scenario 1: Home -> Kitchen -> Table1 -> Home")
                node._send_order(1, 'TABLE1')

            elif key == '2':
                print("\n[KEY-2] Dispatching Scenario 2: Home -> Kitchen/Table1 -> Home (Timeout -> Home)")
                node._send_order(2, 'TABLE1')

            elif key == '3':
                print("\n[KEY-3] Dispatching Scenario 3: Home -> Kitchen/Table1 -> Home (Table Timeout -> Kitchen -> Home)")
                node._send_order(3, 'TABLE1')

            elif key == '4':
                print("\n[KEY-4] Dispatching Scenario 4: Home -> Kitchen/Table1 -> Home (Cancel going to Table -> Kitchen -> Home)")
                node._send_order(4, 'TABLE1')

            elif key == '5':
                print("\n[KEY-5] Dispatching Scenario 5: Home -> Kitchen -> Table1,2,3 -> Home")
                node._send_order(5, 'TABLE1,TABLE2,TABLE3')

            elif key == '6':
                print("\n[KEY-6] Dispatching Scenario 6: Home -> Kitchen -> Table1,2,3 -> Home (Unconfirmed -> Kitchen -> Home)")
                node._send_order(6, 'TABLE1,TABLE2,TABLE3')

            elif key == '7':
                print("\n[KEY-7] Dispatching Scenario 7: Home -> Kitchen -> Table1,2,3 -> Home (Skip Table -> Kitchen -> Home)")
                node._send_order(7, 'TABLE1,TABLE2,TABLE3')

            elif key == 'k':
                print("\n[KEY-k] Sending KITCHEN staff confirmation...")
                node._send_confirm('kitchen')

            elif key == 'c':
                print("\n[KEY-c] Sending CUSTOMER (table) confirmation...")
                node._send_confirm('table')

            elif key == 'x':
                print("\n[KEY-X] Skipping TABLE1...")
                node._send_cancel('TABLE1')

            elif key == 'y':
                print("\n[KEY-Y] Skipping TABLE2...")
                node._send_cancel('TABLE2')

            elif key == 'z':
                print("\n[KEY-Z] Skipping TABLE3...")
                node._send_cancel('TABLE3')

            elif key == 'q':
                print("\n[KEY-Q] QUIT / CANCEL — stopping task and returning to Home...")
                node._send_cancel('all')

            elif key in ('', '\n'):
                continue

            else:
                print(f"\n  [WARNING] Unknown key: '{key}'. "
                      "Use 1 / 2 / 3 / 4 / 5 / 6 / 7 / k / c / x / y / z / q")

    finally:
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)


if __name__ == '__main__':
    main()
