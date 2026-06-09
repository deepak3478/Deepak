#!/usr/bin/env python3
"""
butler.launch.py
================
Standalone launch for the butler logic only (no Gazebo / RViz).
Use this when Gazebo + Nav2 are already running separately.

Usage:
  ros2 launch coffee_shop_butler butler.launch.py

To run the full stack in one shot, use instead:
  ros2 launch coffee_shop_sim coffee_shop.launch.py
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node



def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time',      default_value='true'),
        DeclareLaunchArgument('kitchen_timeout_s', default_value='30.0'),
        DeclareLaunchArgument('table_timeout_s',   default_value='5.0'),
        DeclareLaunchArgument('nav_timeout_s',     default_value='60.0'),

        Node(
            package='coffee_shop_butler',
            executable='butler_node.py',
            name='butler_node',
            output='screen',
            parameters=[{
                'use_sim_time':            LaunchConfiguration('use_sim_time'),
                'kitchen_timeout_s':       LaunchConfiguration('kitchen_timeout_s'),
                'table_timeout_s':         LaunchConfiguration('table_timeout_s'),
                'nav_timeout_s':           LaunchConfiguration('nav_timeout_s'),
                'require_kitchen_confirm': False,
                'require_table_confirm':   False,
            }],
        ),

        Node(
            package='coffee_shop_butler',
            executable='order_manager_node.py',
            name='order_manager_node',
            output='screen',
            parameters=[{
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            }],
        ),
    ])
