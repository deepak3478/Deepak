# my_robot_description — ROS2 Control Workspace

Your original `my_robot_description` package, upgraded with full `ros2_control` support.

---

## What changed from your starting code

| File | Status |
|---|---|
| `urdf/common_properties.xacro` | Unchanged |
| `urdf/my_robot.urdf.xacro` | Unchanged |
| `urdf/mobile_base.xacro` | **Upgraded** — added `<collision>`, `<inertial>`, and `<ros2_control>` tags |
| `launch/display.launch.py` | Unchanged — still works for URDF preview |
| `launch/display.launch.xml` | Unchanged |
| `rviz/urdf_config.rviz` | Unchanged |
| `config/ros2_controllers.yaml` | **New** — diff_drive_controller config |
| `launch/bringup.launch.py` | **New** — full ros2_control bringup |
| `package.xml` | **New** |
| `CMakeLists.txt` | Minor — added `config` to install dirs |

---

## Package structure

```
ros2_ws/
└── src/
    └── my_robot_description/
        ├── urdf/
        │   ├── my_robot.urdf.xacro       ← main entry (unchanged)
        │   ├── common_properties.xacro   ← materials (unchanged)
        │   └── mobile_base.xacro         ← robot body + ros2_control tags
        ├── launch/
        │   ├── display.launch.py         ← your original URDF preview
        │   ├── display.launch.xml        ← your original XML version
        │   └── bringup.launch.py         ← NEW: full ros2_control stack
        ├── rviz/
        │   └── urdf_config.rviz          ← your original RViz config
        ├── config/
        │   └── ros2_controllers.yaml     ← NEW: controller params
        ├── package.xml
        └── CMakeLists.txt
```

---

## Install dependencies

```bash
sudo apt install \
  ros-humble-ros2-control \
  ros-humble-ros2-controllers \
  ros-humble-diff-drive-controller \
  ros-humble-joint-state-broadcaster \
  ros-humble-controller-manager
```

---

## Build

```bash
cd ~/ros2_ws
colcon build --symlink-install
source install/setup.bash
```

---

## Run

### 1. URDF preview only (your original workflow — unchanged)
```bash
ros2 launch my_robot_description display.launch.py
```

### 2. Full ros2_control bringup (mock hardware — no real robot needed)
```bash
ros2 launch my_robot_description bringup.launch.py
```

### 3. Send velocity commands
```bash
# Teleop keyboard
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -r /cmd_vel:=/diff_drive_controller/cmd_vel_unstamped

# Or publish directly
ros2 topic pub /diff_drive_controller/cmd_vel_unstamped \
  geometry_msgs/msg/Twist \
  "{linear: {x: 0.2}, angular: {z: 0.5}}"
```

### 4. Check active controllers
```bash
ros2 control list_controllers
```

---

## Next steps (Gazebo)

When you're ready to simulate, change the hardware plugin in `mobile_base.xacro`:

```xml
<!-- From this (mock): -->
<plugin>mock_components/GenericSystem</plugin>

<!-- To this (Gazebo): -->
<plugin>gazebo_ros2_control/GazeboSystem</plugin>
```

Then add `gazebo_ros2_control` to your `package.xml` depends.

---

## Joint names reference

| Joint | Type | Role |
|---|---|---|
| `base_left_wheel_joint` | continuous | Left drive wheel |
| `base_right_wheel_joint` | continuous | Right drive wheel |
| `base_caster_wheel_joint` | fixed | Front caster (no motor) |
