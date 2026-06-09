import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use Gazebo simulation clock'
    )

    use_sim_time = LaunchConfiguration('use_sim_time')

    # TABLE 1 Controller
    table1_ctrl = Node(
        package='cafe_butler_sim',
        executable='table1_controller',
        name='table1_controller',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        prefix='gnome-terminal --title="TABLE 1 Controller" --',
    )

    # TABLE 2 Controller
    table2_ctrl = Node(
        package='cafe_butler_sim',
        executable='table2_controller',
        name='table2_controller',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        prefix='gnome-terminal --title="TABLE 2 Controller" --',
    )

    # TABLE 3 Controller
    table3_ctrl = Node(
        package='cafe_butler_sim',
        executable='table3_controller',
        name='table3_controller',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        prefix='gnome-terminal --title="TABLE 3 Controller" --',
    )

    return LaunchDescription([
        declare_use_sim_time,
        table1_ctrl,
        table2_ctrl,
        table3_ctrl,
    ])
