import rclpy
from rclpy.node import Node

from turtlesim.msg import Pose
from geometry_msgs.msg import Twist
from turtlesim.srv import Kill

from std_msgs.msg import String

import math


class TurtleCatcher(Node):

    def __init__(self):
        super().__init__("turtle_catcher")

        self.turtle1_pose = Pose()

        self.target_turtle = None
        self.target_pose = Pose()

        self.publisher = self.create_publisher(
            Twist,
            "/turtle1/cmd_vel",
            10
        )

        self.create_subscription(
            Pose,
            "/turtle1/pose",
            self.turtle1_callback,
            10
        )

        self.create_subscription(
            String,
            "alive_turtles",
            self.new_turtle_callback,
            10
        )

        self.kill_client = self.create_client(Kill, "/kill")

        self.timer = self.create_timer(0.1, self.control_loop)


    def turtle1_callback(self, pose):
        self.turtle1_pose = pose


    def new_turtle_callback(self, msg):

        self.target_turtle = msg.data

        self.create_subscription(
            Pose,
            f"/{self.target_turtle}/pose",
            self.target_pose_callback,
            10
        )

        self.get_logger().info(f"Target: {self.target_turtle}")


    def target_pose_callback(self, pose):
        self.target_pose = pose


    def kill_turtle(self):

        req = Kill.Request()
        req.name = self.target_turtle

        self.kill_client.call_async(req)

        self.get_logger().info(f"{self.target_turtle} killed")

        self.target_turtle = None


    def control_loop(self):

        if self.target_turtle is None:
            return

        msg = Twist()

        dx = self.target_pose.x - self.turtle1_pose.x
        dy = self.target_pose.y - self.turtle1_pose.y

        distance = math.sqrt(dx**2 + dy**2)

        angle = math.atan2(dy, dx)
        error = angle - self.turtle1_pose.theta

        if distance > 0.5:

            msg.linear.x = 5.0
            msg.angular.z = 5 * error

        else:

            msg.linear.x = 0.0
            msg.angular.z = 0.0

            self.kill_turtle()

        self.publisher.publish(msg)


def main():

    rclpy.init()

    node = TurtleCatcher()

    rclpy.spin(node)

    rclpy.shutdown()


if __name__ == "__main__":
    main()