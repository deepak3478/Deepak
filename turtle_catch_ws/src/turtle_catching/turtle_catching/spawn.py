import rclpy
from rclpy.node import Node
from turtlesim.srv import Spawn
from std_msgs.msg import String
import random


class TurtleSpawn(Node):

    def __init__(self):
        super().__init__("turtle_spawn")

        # create spawn service client
        self.spawn_client = self.create_client(Spawn, "/spawn")

        # wait until spawn service is available
        while not self.spawn_client.wait_for_service(timeout_sec=3.0):
            self.get_logger().info("Waiting for /spawn service...")

        # publisher to tell catcher which turtle spawned
        self.publisher = self.create_publisher(String,"alive_turtles",10)

        # spawn every 3 seconds
        self.timer = self.create_timer(3.0, self.spawn_turtle)

        # counter for turtle names
        self.counter = 2


    def spawn_turtle(self):

        # random coordinates
        x = random.uniform(1.0, 10.0)
        y = random.uniform(1.0, 10.0)

        name = "turtle" + str(self.counter)

        # create spawn request
        req = Spawn.Request()
        req.x = x
        req.y = y
        req.theta = 0.0
        req.name = name

        # call spawn service
        self.spawn_client.call_async(req)

        # publish turtle name
        msg = String()
        msg.data = name
        self.publisher.publish(msg)

        self.get_logger().info(f"Spawned {name}")

        self.counter += 1


def main():

    rclpy.init()

    node = TurtleSpawn()

    rclpy.spin(node)

    node.destroy_node()
    
    rclpy.shutdown()


if __name__ == "__main__":
    main()