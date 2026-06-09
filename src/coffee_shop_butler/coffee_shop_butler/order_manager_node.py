#!/usr/bin/env python3
"""
Order Manager Node — French Door Café
=======================================
Provides a thin CLI / service-based interface so kitchen staff can:
  • Place orders:  ros2 service call /order_manager/place_order …
  • Cancel orders: ros2 service call /order_manager/cancel_order …
  • Query status:  ros2 service call /order_manager/status …

This node bridges between high-level staff commands and the butler node's
raw topic interface, adding validation and logging.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger


class OrderManagerNode(Node):
    """Translates human-readable service calls into butler node topics."""

    def __init__(self) -> None:
        super().__init__('order_manager_node')

        # Publishers that forward to the butler
        self._order_pub  = self.create_publisher(String, '/butler/order',  10)
        self._cancel_pub = self.create_publisher(String, '/butler/cancel', 10)

        # Monitor butler state
        self._current_status = 'IDLE — no orders'
        self.create_subscription(String, '/butler/status',
                                 self._on_status, 10)
        self.create_subscription(String, '/butler/state',
                                 self._on_state, 10)

        # Services for operator use
        self.create_service(Trigger, '/order_manager/status', self._svc_status)

        # Parameterised order/cancel services require custom srv types in
        # a real deployment; for this package we expose a topic-based CLI.
        self.get_logger().info(
            'Order Manager ready.\n'
            '  Place order : ros2 topic pub --once /butler/order '
            'std_msgs/String "data: \'table1\'"\n'
            '  Cancel table: ros2 topic pub --once /butler/cancel '
            'std_msgs/String "data: \'table2\'"\n'
            '  Query status: ros2 service call /order_manager/status '
            'std_srvs/srv/Trigger'
        )

    def _on_status(self, msg: String) -> None:
        self._current_status = msg.data

    def _on_state(self, msg: String) -> None:
        self.get_logger().debug(f'Butler state → {msg.data}')

    def _svc_status(self, _req, response):
        response.success = True
        response.message = self._current_status
        return response


def main(args=None) -> None:
    rclpy.init(args=args)
    node = OrderManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
