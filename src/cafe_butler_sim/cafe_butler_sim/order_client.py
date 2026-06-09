import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class CafeOrderClient(Node):
    def __init__(self):
        super().__init__('cafe_order_client')
        self.order_pub = self.create_publisher(String, '/butler/order', 10)
        self.confirm_pub = self.create_publisher(String, '/butler/confirm', 10)
        self.cancel_pub = self.create_publisher(String, '/butler/cancel', 10)
        
    def send_order(self, scenario, tables_str):
        msg = String()
        msg.data = f"{scenario}:{tables_str}"
        self.order_pub.publish(msg)
        self.get_logger().info(f"Dispatched sequence setup payload: {msg.data}")

    def send_confirmation(self, source='table'):
        msg = String()
        msg.data = source
        self.confirm_pub.publish(msg)
        self.get_logger().info(f"Dispatched {source} confirmation.")

    def trigger_cancel(self, target='all'):
        msg = String()
        msg.data = target
        self.cancel_pub.publish(msg)
        self.get_logger().warn(f"Dispatched cancellation trigger: {target}")

def main():
    rclpy.init()
    client = CafeOrderClient()
    
    print("\n--- Cafe Butler Bot Testing Console ---")
    print("Commands:")
    print("  order <scenario_id> <tables_separated_by_comma> (e.g., 'order 1 TABLE1' or 'order 5 TABLE1,TABLE2')")
    print("  confirm [kitchen|table]")
    print("  cancel [TABLE1|TABLE2|TABLE3|all]")
    print("----------------------------------------\n")
    
    while rclpy.ok():
        try:
            user_input = input("Enter command: ").strip().split(' ', 1)
            if not user_input or user_input[0] == '':
                continue
                
            cmd = user_input[0].lower()
            if cmd == 'order':
                if len(user_input) < 2:
                    print("Usage: order <scenario_id> <tables_separated_by_comma>")
                    continue
                args = user_input[1].split(' ', 1)
                if len(args) < 2:
                    print("Usage: order <scenario_id> <tables_separated_by_comma>")
                    continue
                client.send_order(args[0], args[1])
            elif cmd == 'confirm':
                source = user_input[1].strip().lower() if len(user_input) > 1 else 'table'
                client.send_confirmation(source)
            elif cmd == 'cancel':
                target = user_input[1].strip() if len(user_input) > 1 else 'all'
                client.trigger_cancel(target)
        except KeyboardInterrupt:
            break
            
    client.destroy_node()
    rclpy.shutdown()
