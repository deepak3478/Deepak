#!/usr/bin/env python3
"""
order_table2.py
===============
Order node for Table 2.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class OrderTable2(Node):
    def __init__(self):
        super().__init__('order_table2')
        self._order_pub   = self.create_publisher(String, '/butler/order',   10)
        self._confirm_pub = self.create_publisher(String, '/butler/confirm',  10)
        self._cancel_pub  = self.create_publisher(String, '/butler/cancel',   10)
        self.get_logger().info("Order node for TABLE 2 ready.")

    def send(self, scenario: int, tables: str):
        msg = String()
        msg.data = f"{scenario}:{tables}"
        self._order_pub.publish(msg)
        self.get_logger().info(f"[SEND] Order sent -> {msg.data}")

    def confirm(self, source: str = 'table'):
        self._confirm_pub.publish(String(data=source))
        self.get_logger().info(f"[SUCCESS] Confirmation sent: {source}")

    def cancel(self, target: str = 'all'):
        self._cancel_pub.publish(String(data=target))
        self.get_logger().info(f"[CANCEL] Cancel sent: {target}")

MENU = """
========================================
  Cafe Butler - Table 2 Order Console
========================================
 [1] Scenario 1 -> TABLE2 (simple delivery)
 [2] Scenario 2 -> TABLE2 (kitchen + table confirm)
 [3] Scenario 3 -> TABLE2 (kitchen confirm; table timeout -> kitchen)
 [4] Scenario 4 -> TABLE2 (cancel-aware delivery)
 [5] Scenario 5 -> TABLE1, TABLE2, TABLE3 (multi-table, no confirm)
 [6] Scenario 6 -> TABLE1, TABLE2, TABLE3 (multi-table, skip on timeout)
 [7] Scenario 7 -> TABLE1, TABLE2, TABLE3 (multi-table, cancel aware)

 [c] Send TABLE Confirmation
 [k] Send KITCHEN Confirmation
 [x] Cancel TABLE2
 [q] Cancel ALL
========================================
"""

def main(args=None):
    rclpy.init(args=args)
    node = OrderTable2()
    
    import threading
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    while rclpy.ok():
        print(MENU)
        try:
            choice = input("Enter choice: ").strip().lower()
        except EOFError:
            break

        if choice == '1': node.send(1, "TABLE2")
        elif choice == '2': node.send(2, "TABLE2")
        elif choice == '3': node.send(3, "TABLE2")
        elif choice == '4': node.send(4, "TABLE2")
        elif choice == '5': node.send(5, "TABLE1,TABLE2,TABLE3")
        elif choice == '6': node.send(6, "TABLE1,TABLE2,TABLE3")
        elif choice == '7': node.send(7, "TABLE1,TABLE2,TABLE3")
        elif choice == 'c': node.confirm('table')
        elif choice == 'k': node.confirm('kitchen')
        elif choice == 'x': node.cancel('TABLE2')
        elif choice == 'q': node.cancel('all')
        else: print("  [WARNING] Unknown option.")

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
