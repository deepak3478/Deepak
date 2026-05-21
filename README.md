# ROS2 Projects 🤖

A collection of ROS2 projects covering robotics fundamentals to advanced simulation concepts.

---

## 📦 Workspaces

### 1. `turtle_catch_ws` — Autonomous Turtle Catcher
- **Spawner node:** Randomly spawns turtles every 3 seconds in turtlesim
- **Catcher node:** Autonomously chases and kills each turtle using angle + distance control
- **Concepts:** Services (`/spawn`, `/kill`), Topics (`/pose`, `/cmd_vel`), `math.atan2`, multi-node architecture

### 2. `slam_ws` — Two-Wheel Robot with Gazebo Simulation
- Differential drive robot built with URDF/Xacro
- Full Gazebo Harmonic simulation with custom world
- ROS-Gazebo bridge for LaserScan, Odometry, Camera, cmd_vel
- **Concepts:** Xacro, `ros_gz_bridge`, `robot_state_publisher`, RViz2, SDF world

### 3. `ros2_ws` — Full Robot Description with ros2_control
- Modular Xacro robot (common_properties + mobile_base)
- ros2_control bringup with `diff_drive_controller` and `joint_state_broadcaster`
- **Concepts:** `ros2_control`, controller YAML config, `OnProcessStart` event handler

### 4. `custom_cmake_ws` — Custom ROS2 Interfaces
- Custom messages: `Num.msg`, `Sphere.msg`
- Custom service: `AddThreeInts.srv`
- **Concepts:** `rosidl_generate_interfaces`, CMake interface generation

---

## 🚀 Setup & Run

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# Build any workspace (example: turtle_catch_ws)
cd turtle_catch_ws
colcon build
source install/setup.bash

# Run turtle catcher
ros2 run turtle_catching spawn &
ros2 run turtle_catching catch
```

## ⚙️ Requirements
- ROS2 Jazzy
- Python 3.10+
- `turtlesim`, `gazebo-harmonic`, `ros_gz`, `ros2_control`
