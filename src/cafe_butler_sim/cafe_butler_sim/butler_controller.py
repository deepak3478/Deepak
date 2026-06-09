#!/usr/bin/env python3
"""
butler_controller.py
====================
Interactive keyboard controller for the Cafe Butler Robot.

Key Bindings
------------
  1  ->  Scenario 1: Home -> Kitchen (collect) -> Table1 -> Home (no confirmation)
  2  ->  Scenario 2: Home -> Kitchen (wait confirm|timeout->Home)
                          -> Table1 (wait confirm|timeout->Home) -> Home
  3  ->  Scenario 3: Home -> Kitchen (wait confirm|timeout->Home)
                          -> Table1 (wait confirm|table-timeout->Kitchen->Home) -> Home
  4  ->  Scenario 4: Home -> Kitchen -> Table1 -> Home  [cancel-aware]
                     cancel@kitchen -> Home | cancel@table -> Kitchen -> Home
  5  ->  Scenario 5: Home -> Kitchen (collect all) -> Table1,2,3 -> Home [no confirm]
  6  ->  Scenario 6: Home -> Kitchen (collect all) -> Table1,2,3
                     (per-table: timeout=skip next) -> unconfirmed? Kitchen -> Home
  7  ->  Scenario 7: Home -> Kitchen (collect all) -> Table1,2,3
                     (skip cancelled table) -> skipped? Kitchen -> Home

  k  ->  Send KITCHEN staff confirmation  (Scenarios 2, 3)
  c  ->  Send CUSTOMER (table) confirmation  (Scenarios 2, 3, 6)

  x  ->  Skip / cancel TABLE1  (Scenarios 4 & 7)
  y  ->  Skip / cancel TABLE2  (Scenario 7)
  z  ->  Skip / cancel TABLE3  (Scenario 7)
  q  ->  KEY Q (Quit): stop all tasks, navigate to Home

Topics published
----------------
  /butler/order   (std_msgs/String) -> "SCENARIO:TABLE1,TABLE2,..."
  /butler/confirm (std_msgs/String) -> "kitchen" | "table"
  /butler/cancel  (std_msgs/String) -> "TABLE1" | "TABLE2" | "TABLE3" | "all"

Topic subscribed
-----------------
  /butler/status  (std_msgs/String) -> displays robot status in terminal
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import threading
import sys


MENU = """\
============================================================
   CAFE BUTLER ROBOT - Keyboard Controller
============================================================
  [1]  Sc 1  Home -> Kitchen -> Table1 -> Home
             (Autonomous, no confirmation needed)

  [2]  Sc 2  Home -> Kitchen (wait confirm | timeout->Home)
             -> Table1 (wait confirm | timeout->Home) -> Home

  [3]  Sc 3  Home -> Kitchen (wait confirm | timeout->Home)
             -> Table1 (wait confirm | timeout->Kitchen->Home) -> Home

  [4]  Sc 4  Home -> Kitchen -> Table1 -> Home  [Cancel-Aware]
             cancel@kitchen -> Home  |  cancel@table -> Kitchen -> Home

  [5]  Sc 5  Home -> Kitchen -> Table1,2,3 -> Home
             (Multi-table autonomous, no confirmation)

  [6]  Sc 6  Home -> Kitchen -> Table1,2,3
             (Per-table: no confirm=skip; unconfirmed->Kitchen->Home)

  [7]  Sc 7  Home -> Kitchen -> Table1,2,3
             (Skip cancelled table; skipped->Kitchen->Home)
------------------------------------------------------------
  [k]  Send KITCHEN confirmation    (Scenarios 2, 3)
  [c]  Send CUSTOMER confirmation   (Scenarios 2, 3, 6)
------------------------------------------------------------
  [x]  Cancel/Skip TABLE1  (Scenarios 4 & 7)
  [y]  Cancel/Skip TABLE2  (Scenario 7)
  [z]  Cancel/Skip TABLE3  (Scenario 7)
  [q]  QUIT: stop all tasks, navigate to Home
============================================================
Enter key: """


class ButlerController(Node):
    """Keyboard-driven controller node for the Cafe Butler Robot."""

    def __init__(self):
        super().__init__('butler_controller')

        self._order_pub   = self.create_publisher(String, '/butler/order',   10)
        self._confirm_pub = self.create_publisher(String, '/butler/confirm', 10)
        self._cancel_pub  = self.create_publisher(String, '/butler/cancel',  10)

        # Subscribe to status topic so operator sees robot feedback
        self.create_subscription(
            String, '/butler/status', self._status_cb, 20)

        self.get_logger().info("[CTRL] Butler Controller ready. See terminal for menu.")

    # ──────────────────────────────────────────────────────────────────────
    #  Status display
    # ──────────────────────────────────────────────────────────────────────

    def _status_cb(self, msg: String):
        """Print robot status messages to the terminal in real time."""
        text = msg.data.strip()
        if text:
            print(f"\r  [ROBOT] {text}", flush=True)

    # ──────────────────────────────────────────────────────────────────────
    #  Command publishers
    # ──────────────────────────────────────────────────────────────────────

    def _send_order(self, scenario: int, tables: str):
        """Publish an order: 'SCENARIO:TABLE1,TABLE2,...'"""
        payload = f"{scenario}:{tables}"
        self._order_pub.publish(String(data=payload))
        self.get_logger().info(f"[CTRL] Order sent -> {payload}")

    def _send_confirm(self, source: str):
        """Publish a confirmation (kitchen or table)."""
        self._confirm_pub.publish(String(data=source))
        self.get_logger().info(f"[CTRL] Confirmation sent -> {source}")

    def _send_cancel(self, target: str):
        """Publish a cancel/skip/quit command."""
        self._cancel_pub.publish(String(data=target))
        self.get_logger().info(f"[CTRL] Cancel/Skip sent -> {target}")


def main(args=None):
    rclpy.init(args=args)
    node = ButlerController()

    # Spin the node in a background thread so callbacks fire while we wait
    # for keyboard input in the main thread.
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

            # ── Scenarios ──────────────────────────────────────────────────
            if key == '1':
                print("\n[KEY-1] Sc 1: Home -> Kitchen -> Table1 -> Home (autonomous)")
                node._send_order(1, 'TABLE1')

            elif key == '2':
                print("\n[KEY-2] Sc 2: Confirmation-based (kitchen + table confirm, timeout->Home)")
                print("         Press [k] for kitchen confirm, [c] for customer confirm.")
                node._send_order(2, 'TABLE1')

            elif key == '3':
                print("\n[KEY-3] Sc 3: Kitchen confirm; table timeout -> Kitchen -> Home")
                print("         Press [k] for kitchen confirm, [c] for customer confirm.")
                node._send_order(3, 'TABLE1')

            elif key == '4':
                print("\n[KEY-4] Sc 4: Cancel-aware single-table delivery")
                print("         Press [x] to cancel at any point.")
                print("         cancel@kitchen -> Home | cancel@table -> Kitchen -> Home")
                node._send_order(4, 'TABLE1')

            elif key == '5':
                print("\n[KEY-5] Sc 5: Multi-table autonomous delivery (Table1, Table2, Table3) -> Home")
                node._send_order(5, 'TABLE1,TABLE2,TABLE3')

            elif key == '6':
                print("\n[KEY-6] Sc 6: Multi-table customer confirmation (per-table timeout=skip)")
                print("         Press [c] when robot arrives at each table.")
                print("         Unconfirmed tables -> visit Kitchen before Home.")
                node._send_order(6, 'TABLE1,TABLE2,TABLE3')

            elif key == '7':
                print("\n[KEY-7] Sc 7: Multi-table skip-aware delivery")
                print("         Press [x]/[y]/[z] to cancel TABLE1/TABLE2/TABLE3.")
                print("         Skipped tables -> visit Kitchen before Home.")
                node._send_order(7, 'TABLE1,TABLE2,TABLE3')

            # ── Confirmations ──────────────────────────────────────────────
            elif key == 'k':
                print("\n[KEY-k] Sending KITCHEN staff confirmation...")
                node._send_confirm('kitchen')

            elif key == 'c':
                print("\n[KEY-c] Sending CUSTOMER (table) confirmation...")
                node._send_confirm('table')

            # ── Cancel / Skip ──────────────────────────────────────────────
            elif key == 'x':
                print("\n[KEY-x] Cancelling/Skipping TABLE1...")
                node._send_cancel('TABLE1')

            elif key == 'y':
                print("\n[KEY-y] Cancelling/Skipping TABLE2...")
                node._send_cancel('TABLE2')

            elif key == 'z':
                print("\n[KEY-z] Cancelling/Skipping TABLE3...")
                node._send_cancel('TABLE3')

            elif key == 'q':
                print("\n[KEY-Q] QUIT — stopping all tasks and returning to Home...")
                node._send_cancel('all')
                break

            elif key in ('', '\n'):
                continue

            else:
                print(f"\n  [WARNING] Unknown key: '{key}'. "
                      "Use 1-7 / k / c / x / y / z / q")

    finally:
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)


if __name__ == '__main__':
    main()
