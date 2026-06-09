# Coffee Shop Butler Robot — ROS 2 Workspace

A complete ROS 2 workspace for a differential-drive butler robot that autonomously
collects orders from a kitchen and delivers them to three customer tables inside a
simulated coffee shop (Gazebo Classic + Nav2 + RViz2).

---

## Repository layout

```
coffee_shop_ws/
├── src/
│   ├── coffee_shop_sim/          ← Simulation environment package
│   │   ├── worlds/
│   │   │   └── coffee_shop.world         Gazebo SDF world
│   │   ├── urdf/
│   │   │   └── coffee_shop_robot.urdf.xacro  TurtleBot3-style robot
│   │   ├── maps/
│   │   │   ├── coffee_shop_map.pgm       Pre-built occupancy map
│   │   │   └── coffee_shop_map.yaml      Map metadata
│   │   ├── config/
│   │   │   ├── nav2_params.yaml          Nav2 full-stack configuration
│   │   │   └── coffee_shop_rviz.rviz     RViz2 layout
│   │   └── launch/
│   │       └── coffee_shop.launch.py     ★ ONE-SHOT launch (Gazebo+Nav2+Butler)
│   │
│   └── coffee_shop_butler/       ← Butler robot logic package
│       ├── coffee_shop_butler/
│       │   ├── __init__.py
│       │   ├── butler_node.py            State machine + Nav2 client
│       │   └── order_manager_node.py     CLI bridge / status service
│       ├── config/
│       │   └── waypoints.yaml            Named waypoint coordinates
│       └── launch/
│           └── butler.launch.py          Standalone butler launch
└── README.md
```

---

## World layout

```
         West(-6)                       East(+6)
North(+5) ┌─────────────────────────────────────┐
          │                                     │
          │  Table 1 (0, +3)                    │
          │                                     │
          │  Table 2 (0,  0)   Kitchen(2.5, 0)  │
          │                    ████████████████  │
          │  Table 3 (0, -3)                    │
          │                                     │
          │  Home (-2, 0)                       │
South(-5) └─────────────────────────────────────┘
```

---

## Delivery cycle (automatic, no commands needed)

| Time (s) | Event |
|---------|-------|
| 0       | Butler node starts, enters **IDLE** |
| 0–10    | 10-second wait (order-collect interval) |
| ~10     | Robot navigates to **Kitchen** → **AT_KITCHEN** (order collected) |
| ~10+nav | Navigate to **Table 1** → wait **5 s** → deliver ✓ |
| ~15+nav | Navigate to **Table 2** → wait **5 s** → deliver ✓ |
| ~20+nav | Navigate to **Table 3** → wait **5 s** → deliver ✓ |
| ~25+nav | Return **Home** |
| repeat  | Cycle restarts |

If a table order is cancelled before/during delivery the food is not dropped
and the robot returns the uncollected portion to the kitchen before going home.

---

## Prerequisites

| Software | Version |
|----------|---------|
| Ubuntu   | 22.04 LTS |
| ROS 2    | Humble (recommended) |
| Gazebo   | Classic 11 (`gazebo11`) |
| Nav2     | `ros-humble-navigation2` |
| xacro    | `ros-humble-xacro` |
| colcon   | any recent |

Install all ROS 2 / Nav2 / Gazebo dependencies:

```bash
sudo apt update
sudo apt install -y \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-gazebo-ros-pkgs \
  ros-humble-gazebo-ros2-control \
  ros-humble-robot-state-publisher \
  ros-humble-xacro \
  ros-humble-rviz2 \
  python3-colcon-common-extensions
```

---

## Build

```bash
cd ~/coffee_shop_ws
colcon build --symlink-install
source install/setup.bash
```

---

## Run — full system (Gazebo + RViz + Butler)

```bash
# In terminal 1 — everything in one command
ros2 launch coffee_shop_sim coffee_shop.launch.py

# Optional flags:
#   open_rviz:=false       skip RViz
#   table_timeout_s:=5.0   seconds to wait at each table (default 5)
```

The launch file:
1. Opens Gazebo with the coffee shop world.
2. Spawns the robot at the **home** position `(-2, 0)`.
3. Starts Nav2 with the pre-built map and AMCL localisation.
4. Opens RViz2 in top-down costmap view.
5. After 8 s (Nav2 initialisation grace period), starts the butler and order manager.

The robot will automatically begin its first delivery run ~10 seconds later.

---

## Run — butler only (Nav2 already running)

```bash
ros2 launch coffee_shop_butler butler.launch.py
```

---

## Interacting at runtime

### Cancel a table's order
```bash
ros2 topic pub --once /butler/cancel std_msgs/String "data: 'table2'"
```

### Watch status
```bash
ros2 topic echo /butler/status
ros2 topic echo /butler/state
```

### Query status via service
```bash
ros2 service call /order_manager/status std_srvs/srv/Trigger
```

### Place a manual order (if butler is idle)
```bash
ros2 topic pub --once /butler/order std_msgs/String "data: 'table1,table3'"
```

---

## Waypoints (editable in `config/waypoints.yaml`)

| Name    | X (m) | Y (m) | Yaw (rad) |
|---------|-------|-------|-----------|
| home    | -2.0  |  0.0  | 0.0 |
| kitchen |  2.5  |  0.0  | π |
| table1  |  0.0  |  3.0  | -π/2 |
| table2  |  0.0  |  0.0  | 0.0 |
| table3  |  0.0  | -3.0  |  π/2 |

---

## Timing parameters (editable in launch or at runtime)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ORDER_COLLECT_INTERVAL_S` | 10 s | Idle time before heading to kitchen |
| `TABLE_WAIT_S` | 5 s | Dwell time at each table |
| `NAV_TIMEOUT_S` | 60 s | Max time per navigation goal |

---

## State machine diagram

```
                   ┌──────────────────────────────────────┐
                   │                                      │
                   ▼                                      │
              ┌─────────┐                                 │
              │  IDLE   │ ◄── 10 s wait ─────────────────┘
              └────┬────┘
                   │
                   ▼
          ┌──────────────────┐
          │  GOING_KITCHEN   │──► nav fail ──► RETURNING_HOME
          └────────┬─────────┘
                   │
                   ▼
          ┌──────────────────┐
          │   AT_KITCHEN     │  (order collected instantly)
          └────────┬─────────┘
                   │
            ┌──────┴──────┐
            │  for each   │
            │   table     │
            └──────┬──────┘
                   ▼
         ┌─────────────────┐
         │  GOING_TABLE    │──► nav fail / cancelled ──┐
         └────────┬────────┘                           │
                  │                                    │
                  ▼                                    │
         ┌─────────────────┐                           │
         │    AT_TABLE     │◄── 5 s wait ──────────────┘
         └────────┬────────┘
                  │
         (all tables done)
                  │
                  ▼
    ┌─────────────────────────────┐
    │  GOING_KITCHEN_RETURN       │ (only if food undelivered)
    └─────────────┬───────────────┘
                  │
                  ▼
         ┌────────────────┐
         │ RETURNING_HOME │
         └────────┬───────┘
                  │
                  ▼
              ┌─────────┐
              │  IDLE   │
              └─────────┘
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Nav2 action server not available` | Nav2 takes ~15 s to start; the butler waits 8 s — extend `TimerAction(period=...)` in `coffee_shop.launch.py` if needed |
| Robot doesn't move in Gazebo | Check `ros2 topic echo /cmd_vel`; confirm `libgazebo_ros_diff_drive.so` loaded |
| AMCL particles scattered | Set initial pose in RViz2 using the **2D Pose Estimate** tool |
| `xacro` not found | `sudo apt install ros-humble-xacro` |
| Map looks empty | Ensure `coffee_shop_map.pgm` was generated during build (`colcon build`) |
