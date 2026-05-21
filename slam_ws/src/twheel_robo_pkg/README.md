# my_robot — ROS 2 Foxy Differential Drive Package

## Package Structure

```
slam_ws/
└── src/
    └── my_robot/
        ├── CMakeLists.txt
        ├── package.xml
        ├── urdf/
        │   └── my_robot.urdf.xacro      ← Robot model
        ├── launch/
        │   ├── gazebo.launch.py          ← Full simulation launch
        │   └── display.launch.py         ← RViz-only (URDF check)
        ├── worlds/
        │   └── my_world.world            ← Gazebo world (10×10 room)
        └── config/
            └── robot.rviz                ← RViz2 config
```

---

## Dependencies

```bash
sudo apt update
sudo apt install -y \
  ros-foxy-gazebo-ros-pkgs \
  ros-foxy-robot-state-publisher \
  ros-foxy-joint-state-publisher \
  ros-foxy-joint-state-publisher-gui \
  ros-foxy-xacro \
  ros-foxy-rviz2
```

---

## Build

```bash
cd ~/slam_ws
source /opt/ros/foxy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

---

## Run

### 1. Full Simulation (Gazebo + RViz)
```bash
ros2 launch my_robot gazebo.launch.py
```

### 2. URDF Preview only (RViz + joint_state_publisher_gui)
```bash
ros2 launch my_robot display.launch.py
```

### 3. Spawn at custom position
```bash
ros2 launch my_robot gazebo.launch.py x_pose:=1.0 y_pose:=2.0
```

---

## Teleoperation (keyboard)

```bash
# In a new terminal:
source /opt/ros/foxy/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Install if needed:
```bash
sudo apt install ros-foxy-teleop-twist-keyboard
```

---

## Active Topics

| Topic              | Type                        | Description           |
|--------------------|-----------------------------|-----------------------|
| `/cmd_vel`         | geometry_msgs/Twist         | Velocity command in   |
| `/odom`            | nav_msgs/Odometry           | Wheel odometry out    |
| `/scan`            | sensor_msgs/LaserScan       | 360° Lidar scan       |
| `/camera/image_raw`| sensor_msgs/Image           | Front camera image    |
| `/tf`              | tf2_msgs/TFMessage          | Transform tree        |

---

## Robot Specs

| Parameter          | Value          |
|--------------------|----------------|
| Base (L×W×H)       | 0.35×0.30×0.10 m |
| Wheel radius       | 0.05 m         |
| Wheel separation   | 0.32 m         |
| Lidar range        | 0.12 – 10 m    |
| Lidar samples      | 360°           |
| Camera resolution  | 640×480        |
| Camera FPS         | 30             |

---

## World Description

A 10×10 m enclosed room with:
- 4 outer walls
- 4 cylindrical pillars (at ±2, ±2)
- 2 box obstacles
- 1 inner partial wall (divider)

Good for testing SLAM (e.g., slam_toolbox) and navigation (Nav2).
