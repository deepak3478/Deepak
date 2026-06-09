#!/usr/bin/env python3
"""
cafe_simulation.launch.py
=========================
Unified launch file for the Cafe Butler Simulation.

Launches:
  1. Gazebo (gz sim) with cafe.world
  2. Robot State Publisher (robot URDF → /robot_description + TF)
  3. Spawn robot into Gazebo at HOME position
  4. ROS-GZ bridges (cmd_vel, odom, scan, tf, joint_states, clock)
  5. Nav2 full stack (map server + AMCL + planner + controller + BT)
  6. RViz2 (pre-configured top-down view)
  7. Butler Robot state-machine node (delayed 8 s)

Usage:
  ros2 launch cafe_butler_sim cafe_simulation.launch.py
  ros2 launch cafe_butler_sim cafe_simulation.launch.py open_rviz:=false
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    TimerAction,
    RegisterEventHandler,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessStart
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    # ── Package directories ─────────────────────────────────────────────────
    pkg = get_package_share_directory('cafe_butler_sim')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')

    # ── File paths ──────────────────────────────────────────────────────────
    world_file   = os.path.join(pkg, 'world',  'cafe.world')
    urdf_file    = os.path.join(pkg, 'urdf',   'cafe_butler_robot.urdf.xacro')
    nav2_params  = os.path.join(pkg, 'config', 'nav2_params.yaml')
    map_yaml     = os.path.join(pkg, 'config', 'cafe_map.yaml')
    rviz_config  = os.path.join(pkg, 'config', 'cafe_rviz.rviz')

    # ── Launch arguments ────────────────────────────────────────────────────
    declare_open_rviz = DeclareLaunchArgument(
        'open_rviz', default_value='true',
        description='Launch RViz2'
    )
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use Gazebo simulation clock'
    )

    use_sim_time = LaunchConfiguration('use_sim_time')
    open_rviz    = LaunchConfiguration('open_rviz')

    # ── 1. Gazebo (gz sim) ──────────────────────────────────────────────────
    gz_sim = ExecuteProcess(
        cmd=['gz', 'sim', '-r', world_file],
        output='screen',
        name='gz_sim',
    )

    # ── 2. Robot State Publisher ────────────────────────────────────────────
    robot_description = ParameterValue(
        Command([FindExecutable(name='xacro'), ' ', urdf_file]),
        value_type=str
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time':      use_sim_time,
        }],
    )

    # ── 3. Spawn robot in Gazebo at HOME position ────────────────────────────
    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_cafe_butler',
        arguments=[
            '-name',  'cafe_butler_robot',
            '-topic', '/robot_description',
            '-x',  '0.0',
            '-y', '-5.0',
            '-z',  '0.05',
            '-Y',  '1.5708',   # facing north toward kitchen
        ],
        output='screen',
    )

    # ── 4. ROS-GZ Bridges ───────────────────────────────────────────────────
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='ros_gz_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
            '/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist',
            '/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry',
            '/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',
            '/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V',
            '/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model',
        ],
        output='screen',
    )

    # ── 5. Nav2 full stack ──────────────────────────────────────────────────
    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, 'launch', 'bringup_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'map':          map_yaml,
            'params_file':  nav2_params,
            'autostart':    'true',
        }.items(),
    )

    # ── 6. RViz2 ────────────────────────────────────────────────────────────
    rviz2 = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen',
        condition=IfCondition(open_rviz),
    )

    # ── 7. Butler Robot node (delayed to let Nav2 initialise) ───────────────
    butler_node = TimerAction(
        period=10.0,
        actions=[
            Node(
                package='cafe_butler_sim',
                executable='butler_robot',
                name='butler_robot_sm',
                output='screen',
                parameters=[{'use_sim_time': use_sim_time}],
            ),
        ],
    )
    # ── Assemble ────────────────────────────────────────────────────────────
    return LaunchDescription([
        declare_open_rviz,
        declare_use_sim_time,

        # Simulation environment
        gz_sim,
        robot_state_publisher,

        # Spawn after 2 s so Gazebo is ready
        TimerAction(period=2.0, actions=[spawn_robot]),

        # Bridges
        TimerAction(period=1.0, actions=[bridge]),

        # Navigation
        TimerAction(period=3.0, actions=[nav2]),

        # Visualisation
        TimerAction(period=4.0, actions=[rviz2]),

        # Butler logic (Nav2 needs ~8-10 s to be fully active)
        butler_node,
    ])
