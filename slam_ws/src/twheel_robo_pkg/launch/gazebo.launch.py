"""
gazebo.launch.py  –  ROS 2 Jazzy + Gazebo Harmonic (ros_gz)
Launch: ros2 launch my_robot gazebo.launch.py
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    pkg_name   = "my_robot"
    pkg_share  = get_package_share_directory(pkg_name)

    # ── File paths ─────────────────────────────────────────
    urdf_xacro  = os.path.join(pkg_share, "urdf",   "my_robot.urdf.xacro")
    world_file  = os.path.join(pkg_share, "worlds",  "my_world.sdf")
    rviz_config = os.path.join(pkg_share, "config",  "robot.rviz")

    # ── Launch arguments ───────────────────────────────────
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time", default_value="true",
        description="Use Gazebo simulation clock"
    )
    use_rviz_arg = DeclareLaunchArgument(
        "use_rviz", default_value="true",
        description="Open RViz2"
    )
    x_arg = DeclareLaunchArgument("x_pose", default_value="0.0")
    y_arg = DeclareLaunchArgument("y_pose", default_value="0.0")
    z_arg = DeclareLaunchArgument("z_pose", default_value="0.05")

    use_sim_time = LaunchConfiguration("use_sim_time")
    use_rviz     = LaunchConfiguration("use_rviz")
    x_pose       = LaunchConfiguration("x_pose")
    y_pose       = LaunchConfiguration("y_pose")
    z_pose       = LaunchConfiguration("z_pose")

    # ── Robot description via xacro ───────────────────────
    robot_desc_cmd = Command(["xacro ", urdf_xacro])

    # ── 1. Robot State Publisher ──────────────────────────
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
            "robot_description": robot_desc_cmd,
        }],
    )

    # ── 2. Gazebo Harmonic (gz sim) ───────────────────────
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("ros_gz_sim"),
                "launch",
                "gz_sim.launch.py",
            ])
        ),
        launch_arguments={
            "gz_args": ["-r ", world_file],  # -r = run immediately
            "on_exit_shutdown": "true",
        }.items(),
    )

    # ── 3. Spawn robot into Gazebo ────────────────────────
    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        name="spawn_my_robot",
        output="screen",
        arguments=[
            "-name",  "my_robot",
            "-topic", "robot_description",
            "-x",     x_pose,
            "-y",     y_pose,
            "-z",     z_pose,
        ],
    )

    # ── 4. Bridge: Gazebo topics ↔ ROS 2 topics ──────────
    #   /scan (LaserScan), /odom (Odometry), /cmd_vel (Twist),
    #   /tf, /joint_states, /camera/image_raw
    gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="gz_bridge",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
        arguments=[
            # cmd_vel: ROS → Gazebo
            "/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist",
            # odom: Gazebo → ROS
            "/odom@nav_msgs/msg/Odometry@gz.msgs.Odometry",
            # scan: Gazebo → ROS
            "/scan@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan",
            # joint_states: Gazebo → ROS
            "/joint_states@sensor_msgs/msg/JointState@gz.msgs.Model",
            # tf: Gazebo → ROS
            "/tf@tf2_msgs/msg/TFMessage@gz.msgs.Pose_V",
            # clock: Gazebo → ROS
            "/clock@rosgraph_msgs/msg/Clock@gz.msgs.Clock",
            # camera image: Gazebo → ROS
            "/camera/image_raw@sensor_msgs/msg/Image@gz.msgs.Image",
            "/camera/camera_info@sensor_msgs/msg/CameraInfo@gz.msgs.CameraInfo",
        ],
    )

    # ── 5. RViz2 ─────────────────────────────────────────
    rviz2 = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        condition=IfCondition(use_rviz),
        arguments=["-d", rviz_config],
        parameters=[{"use_sim_time": use_sim_time}],
    )

    return LaunchDescription([
        use_sim_time_arg,
        use_rviz_arg,
        x_arg,
        y_arg,
        z_arg,
        robot_state_publisher,
        gz_sim,
        spawn_robot,
        gz_bridge,
        rviz2,
    ])
