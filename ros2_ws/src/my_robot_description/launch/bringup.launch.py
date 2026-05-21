"""
my_robot_description/launch/bringup.launch.py

Full ros2_control bringup:
  - robot_state_publisher
  - controller_manager  (ros2_control_node)
  - joint_state_broadcaster
  - diff_drive_controller
  - RViz2 (optional)

Usage:
  ros2 launch my_robot_description bringup.launch.py
  ros2 launch my_robot_description bringup.launch.py use_rviz:=false
"""

import os
from ament_index_python.packages import get_package_share_path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, RegisterEventHandler, TimerAction
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessStart
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    pkg = get_package_share_path('my_robot_description')

    urdf_path        = os.path.join(pkg, 'urdf', 'my_robot.urdf.xacro')
    rviz_config_path = os.path.join(pkg, 'rviz', 'urdf_config.rviz')
    controllers_yaml = os.path.join(pkg, 'config', 'ros2_controllers.yaml')

    # ── Launch args ────────────────────────────────────────────────────────────
    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz', default_value='true',
        description='Start RViz2',
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
        description='Use simulation clock',
    )

    use_rviz     = LaunchConfiguration('use_rviz')
    use_sim_time = LaunchConfiguration('use_sim_time')

    robot_description = ParameterValue(
        Command(['xacro ', urdf_path]), value_type=str
    )

    # ── robot_state_publisher ──────────────────────────────────────────────────
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': use_sim_time,
        }],
    )

    # ── controller_manager (ros2_control_node) ─────────────────────────────────
    controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        output='screen',
        parameters=[
            {'robot_description': robot_description,
             'use_sim_time': use_sim_time},
            controllers_yaml,
        ],
    )

    # ── Spawners — wait for controller_manager to start ───────────────────────
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster',
                   '--controller-manager', '/controller_manager'],
        output='screen',
    )

    diff_drive_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['diff_drive_controller',
                   '--controller-manager', '/controller_manager'],
        output='screen',
    )

    # Delay 2 s after controller_manager starts, then spawn both controllers
    delayed_spawners = RegisterEventHandler(
        event_handler=OnProcessStart(
            target_action=controller_manager,
            on_start=[
                TimerAction(
                    period=2.0,
                    actions=[joint_state_broadcaster_spawner, diff_drive_spawner],
                )
            ],
        )
    )

    # ── RViz2 ──────────────────────────────────────────────────────────────────
    rviz2 = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config_path],
        condition=IfCondition(use_rviz),
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen',
    )

    return LaunchDescription([
        use_rviz_arg,
        use_sim_time_arg,
        robot_state_publisher,
        controller_manager,
        delayed_spawners,
        rviz2,
    ])
