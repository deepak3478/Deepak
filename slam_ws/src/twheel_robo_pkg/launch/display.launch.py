"""
display.launch.py  –  ROS 2 Jazzy
URDF preview only – no Gazebo needed.
Launch: ros2 launch my_robot display.launch.py
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node


def generate_launch_description():

    pkg_share   = get_package_share_directory("my_robot")
    urdf_xacro  = os.path.join(pkg_share, "urdf",  "my_robot.urdf.xacro")
    rviz_config = os.path.join(pkg_share, "config", "robot.rviz")

    use_sim_time = LaunchConfiguration("use_sim_time")

    robot_desc_cmd = Command(["xacro ", urdf_xacro])

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false"),

        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            parameters=[{
                "use_sim_time": use_sim_time,
                "robot_description": robot_desc_cmd,
            }],
        ),

        Node(
            package="joint_state_publisher_gui",
            executable="joint_state_publisher_gui",
            parameters=[{"use_sim_time": use_sim_time}],
        ),

        Node(
            package="rviz2",
            executable="rviz2",
            arguments=["-d", rviz_config],
            parameters=[{"use_sim_time": use_sim_time}],
        ),
    ])
