#!/usr/bin/env python3
"""
coffee_shop.launch.py
======================
Single launch file that brings up the entire Coffee Shop Butler system:

  1. Gazebo Classic with coffee_shop.world
  2. Robot spawned inside Gazebo (TurtleBot3-style, URDF via xacro)
  3. robot_state_publisher  (tf + /robot_description)
  4. Nav2 full stack        (AMCL + map_server + planner + controller + BT)
  5. RViz2                  (pre-configured view)
  6. Butler node            (order collection + delivery state machine)
  7. Order manager node     (operator CLI bridge)

Usage
-----
  # 1. Build
  cd ~/coffee_shop_ws
  colcon build --symlink-install
  source install/setup.bash

  # 2. Launch  (export TURTLEBOT3_MODEL=burger if you use TB3 meshes)
  ros2 launch coffee_shop_sim coffee_shop.launch.py

  # 3. Watch the butler work — after 10 s it heads to kitchen then
  #    delivers to table1, table2, table3 (5 s each) then returns home.

  # Optional: cancel a table mid-run
  ros2 topic pub --once /butler/cancel std_msgs/String "data: 'table2'"
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    RegisterEventHandler,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit, OnProcessStart
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue


# ── Constants ─────────────────────────────────────────────────────────────────
PKG_SIM    = 'coffee_shop_sim'
PKG_BUTLER = 'coffee_shop_butler'


def generate_launch_description() -> LaunchDescription:

    # ── Shared package directories ─────────────────────────────────────────
    sim_dir    = get_package_share_directory(PKG_SIM)
    butler_dir = get_package_share_directory(PKG_BUTLER)

    # ── File paths ─────────────────────────────────────────────────────────
    world_file   = os.path.join(sim_dir, 'worlds', 'coffee_shop.world')
    urdf_file    = os.path.join(sim_dir, 'urdf',   'coffee_shop_robot.urdf.xacro')
    nav2_params  = os.path.join(sim_dir, 'config', 'nav2_params.yaml')
    map_yaml     = os.path.join(sim_dir, 'maps',   'coffee_shop_map.yaml')
    rviz_config  = os.path.join(sim_dir, 'config', 'coffee_shop_rviz.rviz')
    wp_config    = os.path.join(butler_dir, 'config', 'waypoints.yaml')

    # ── Launch arguments ───────────────────────────────────────────────────
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use simulation (Gazebo) clock.'
    )
    open_rviz_arg = DeclareLaunchArgument(
        'open_rviz', default_value='true',
        description='Launch RViz2.'
    )
    kitchen_timeout_arg = DeclareLaunchArgument(
        'kitchen_timeout_s', default_value='30.0',
        description='Seconds to wait at kitchen.'
    )
    table_timeout_arg = DeclareLaunchArgument(
        'table_timeout_s', default_value='5.0',
        description='Seconds to wait at each table.'
    )

    use_sim_time = LaunchConfiguration('use_sim_time')
    open_rviz    = LaunchConfiguration('open_rviz')

    # ── 1. Gazebo ──────────────────────────────────────────────────────────
    gazebo = ExecuteProcess(
        cmd=[
            'gazebo', '--verbose',
            '-s', 'libgazebo_ros_init.so',
            '-s', 'libgazebo_ros_factory.so',
            world_file,
        ],
        output='screen',
        name='gazebo',
    )

    # ── 2. Robot description (xacro → URDF string) ─────────────────────────
    robot_description_content = Command([
        FindExecutable(name='xacro'), ' ', urdf_file,
    ])
    robot_description = {
        'robot_description': ParameterValue(
            robot_description_content,
            value_type=str
        )
    }

    # ── 3. robot_state_publisher ───────────────────────────────────────────
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[robot_description, {'use_sim_time': use_sim_time}],
    )

    # ── 4. Spawn robot into Gazebo ─────────────────────────────────────────
    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        name='spawn_robot',
        arguments=[
            '-topic', '/robot_description',
            '-entity', 'coffee_shop_robot',
            '-x', '-2.0',   # home position
            '-y',  '0.0',
            '-z',  '0.01',
            '-Y',  '0.0',
        ],
        output='screen',
    )

    # ── 5. Nav2 (map server + AMCL + planner + controller + BT) ───────────
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    nav2_launch = IncludeLaunchDescription(
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

    # ── 6. RViz2 ───────────────────────────────────────────────────────────
    rviz2 = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen',
        condition=IfCondition(open_rviz),
    )

    # ── 7. Butler node (delayed to let Nav2 finish initialising) ───────────
    butler_node = TimerAction(
        period=8.0,   # wait 8 s after launch before starting butler
        actions=[
            Node(
                package=PKG_BUTLER,
                executable='butler_node.py',
                name='butler_node',
                output='screen',
                parameters=[{
                    'use_sim_time':            use_sim_time,
                    'kitchen_timeout_s':       LaunchConfiguration('kitchen_timeout_s'),
                    'table_timeout_s':         LaunchConfiguration('table_timeout_s'),
                    'nav_timeout_s':           60.0,
                    'require_kitchen_confirm': False,
                    'require_table_confirm':   False,
                }],
            ),
        ],
    )

    # ── 8. Order manager node ──────────────────────────────────────────────
    order_manager_node = TimerAction(
        period=8.0,
        actions=[
            Node(
                package=PKG_BUTLER,
                executable='order_manager_node.py',
                name='order_manager_node',
                output='screen',
                parameters=[{'use_sim_time': use_sim_time}],
            ),
        ],
    )

    # ── Assemble ───────────────────────────────────────────────────────────
    return LaunchDescription([
        use_sim_time_arg,
        open_rviz_arg,
        kitchen_timeout_arg,
        table_timeout_arg,

        # Sim environment
        gazebo,
        robot_state_publisher,
        spawn_robot,

        # Navigation
        nav2_launch,

        # Visualisation
        rviz2,

        # Butler (delayed)
        butler_node,
        order_manager_node,
    ])
