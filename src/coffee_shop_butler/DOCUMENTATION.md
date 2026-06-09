# French Door Café — Butler Robot Technical Documentation

## Overview

This document describes the design, implementation, and milestone coverage of
the `coffee_shop_butler` ROS 2 package built for the French Door Café robot
assessment.

---

## Architecture

```
coffee_shop_ws/
├── src/
│   ├── coffee_shop_sim/          # Provided simulation scaffold
│   │   ├── launch/               # Gazebo + Nav2 launch file
│   │   ├── config/               # SLAM, Nav2, bridge configs
│   │   ├── urdf/                 # Robot URDF/xacro
│   │   └── worlds/               # Gazebo SDF world
│   │
│   └── coffee_shop_butler/       # NEW — butler state machine
│       ├── coffee_shop_butler/
│       │   ├── butler_node.py         # Core state machine
│       │   └── order_manager_node.py  # Operator interface
│       ├── launch/
│       │   └── butler.launch.py
│       └── config/
│           └── waypoints.yaml
```

### Component Interaction

```
Operator (CLI / GUI)
      |
      | /butler/order  (std_msgs/String)
      | /butler/cancel (std_msgs/String)
      v
 OrderManagerNode  ──→  ButlerNode
                              |
                    ActionClient(NavigateToPose)
                              |
                         Nav2 Stack
                              |
                       Gazebo Simulation
```

---

## State Machine

The butler uses a named-state finite state machine implemented without any
external library. Every state transition is logged to `/butler/status` and
`/butler/state`.

```
                         ┌──────────┐
            Order        │   IDLE   │◄──────────────────┐
            received ──► └────┬─────┘                   │
                              │ GOING_KITCHEN            │
                         ┌────▼─────┐                   │
                         │  KITCHEN │                   │
                         └────┬─────┘                   │
                    ┌─────────┴──────────┐              │
               confirmed            timeout             │
                    │                   │               │
               GOING_TABLE       RETURNING_HOME ────────┘
                    │
            ┌───────┴────────────────┐
         confirmed               timeout / cancel
            │                        │
       mark delivered         GOING_KITCHEN_RETURN
            │                        │
       next table?            RETURNING_HOME ────────────┘
            │
       (loop all tables)
            │
      RETURNING_HOME
```

### States

| State | Meaning |
|-------|---------|
| `IDLE` | At home, no active orders |
| `GOING_KITCHEN` | Navigating to kitchen |
| `WAITING_KITCHEN` | Arrived at kitchen, awaiting confirmation |
| `GOING_TABLE` | Navigating to a customer table |
| `WAITING_TABLE` | Arrived at table, awaiting confirmation |
| `GOING_KITCHEN_RETURN` | Returning to kitchen due to undelivered food |
| `RETURNING_HOME` | Navigating back to home position |
| `FAULT` | Navigation or system error |

---

## Milestone Coverage

### Milestone 1 — Single Order, No Confirmation
**Flow**: Home → Kitchen → Table 1 → Home

The parameters `require_kitchen_confirm` and `require_table_confirm` are both
`false` by default. The robot navigates the full route without waiting for any
button press.

**Implementation**: `_run_delivery_batch()` skips the `_wait_for_confirmation()`
call entirely when the parameter is false.

---

### Milestone 2 — Timeout at Any Stop
**Flow**: Home → Kitchen (wait, timeout) → Home

Set `require_kitchen_confirm:=true` and `kitchen_timeout_s:=30.0`. If no
confirmation arrives within the timeout, `_wait_for_confirmation()` returns
`False` and the robot executes the return-home branch.

**Key code path**:
```python
confirmed = self._wait_for_confirmation('kitchen')
if not confirmed:   # timed out
    self._go_home()
    return
```

---

### Milestone 3 — Selective Timeout Behaviour
**Flow A (M3a)**: Kitchen timeout → Home
**Flow B (M3b)**: Kitchen confirmed → Table (timeout) → Kitchen → Home

When the table confirmation times out, `_undelivered_revisit_kitchen` is set to
`True`. After the full table loop, the robot revisits the kitchen before
returning home.

**Key code path**:
```python
if not confirmed:   # table timeout
    self._undelivered_revisit_kitchen = True
    continue        # next table in batch

# After all tables:
if self._undelivered_revisit_kitchen:
    self._navigate_to('kitchen')
self._go_home()
```

---

### Milestone 4 — Cancellation Handling
**Cancel en-route to kitchen**: `_on_cancel()` sets `order.cancelled = True`.
The delivery loop sees this before the first table navigation and skips all
deliveries.

**Cancel en-route to table**: The current order's `.cancelled` flag is checked
immediately after `_navigate_to()` returns. If cancelled, the robot sets
`_undelivered_revisit_kitchen = True` (food was already collected) and the
post-loop logic sends it to kitchen before home.

```python
if order.cancelled:           # checked after nav_to(table)
    self._undelivered_revisit_kitchen = True
    continue
```

---

### Milestone 5 — Multiple Orders
**Flow**: Home → Kitchen → Table 1 → Table 2 → Table 3 → Home

`_on_order()` accepts comma-separated table IDs (e.g. `"table1,table2,table3"`).
Each appended to `_order_queue`. When the worker picks up a batch it iterates
the full list with a single kitchen trip.

---

### Milestone 6 — Timeout on One Table (Multi-order)
**Flow**: Home → Kitchen → Table 1 (timeout) → Table 2 → Table 3 → Kitchen → Home

The same `_undelivered_revisit_kitchen` flag from M3b is used. When any table
in the batch times out, the flag is set, and the post-loop step navigates to
kitchen before home.

---

### Milestone 7 — Cancel One Table (Multi-order)
**Flow**: Home → Kitchen → Table 1 → *skip table 2* → Table 3 → Kitchen → Home

`/butler/cancel "table2"` sets `order.cancelled = True` for that order before
or after navigation begins. The delivery loop skips cancelled orders. Because
food was collected for table 2, `_undelivered_revisit_kitchen = True` applies.

---

## ROS 2 Interface Reference

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/butler/status` | `std_msgs/String` | Human-readable state + event log |
| `/butler/state` | `std_msgs/String` | Current state name (e.g. `GOING_TABLE`) |

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/butler/order` | `std_msgs/String` | Comma-separated table IDs |
| `/butler/cancel` | `std_msgs/String` | Table ID to cancel |
| `/kitchen/confirmation` | `std_msgs/Bool` | True = food ready |
| `/table1/confirmation` | `std_msgs/Bool` | True = customer ready |
| `/table2/confirmation` | `std_msgs/Bool` | |
| `/table3/confirmation` | `std_msgs/Bool` | |

### Services

| Service | Type | Description |
|---------|------|-------------|
| `/order_manager/status` | `std_srvs/Trigger` | Query current robot status |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `kitchen_timeout_s` | `30.0` | Seconds to wait at kitchen |
| `table_timeout_s` | `30.0` | Seconds to wait at each table |
| `nav_timeout_s` | `60.0` | Max navigation time per waypoint |
| `require_kitchen_confirm` | `false` | Enable kitchen wait |
| `require_table_confirm` | `false` | Enable table wait |

---

## Build & Run

### Deterministic Mock Testing
To verify the state machine behavior and transition sequences for all 7 milestones instantly without running Gazebo or Nav2, run the provided mock test suite:
```bash
export PYTHONPATH=/home/deepak33/Desktop/KKR_TASKS/coffee_shop_ws/src/coffee_shop_butler:$PYTHONPATH
source /opt/ros/jazzy/setup.bash
python3 /home/deepak33/Desktop/KKR_TASKS/coffee_shop_ws/src/coffee_shop_butler/coffee_shop_butler/mock_test.py
```

### Full Simulation Run
```bash
# Build
cd ~/coffee_shop_ws
colcon build --packages-select coffee_shop_butler
source install/setup.bash

# Launch simulation (terminal 1)
ros2 launch coffee_shop_sim coffee_shop_sim.launch.py

# Launch butler (terminal 2)
ros2 launch coffee_shop_butler butler.launch.py \
  require_kitchen_confirm:=true \
  require_table_confirm:=true \
  kitchen_timeout_s:=30.0 \
  table_timeout_s:=30.0

# Place a single order (terminal 3)
ros2 topic pub --once /butler/order std_msgs/String "data: 'table1'"

# Place multi-table order
ros2 topic pub --once /butler/order std_msgs/String "data: 'table1,table2,table3'"

# Cancel a table
ros2 topic pub --once /butler/cancel std_msgs/String "data: 'table2'"

# Simulate kitchen confirmation
ros2 topic pub --once /kitchen/confirmation std_msgs/Bool "data: true"

# Simulate table confirmation
ros2 topic pub --once /table1/confirmation std_msgs/Bool "data: true"

# Check status
ros2 service call /order_manager/status std_srvs/srv/Trigger
```

---

## Design Decisions

### Generic, not hardcoded
The location map (`_build_location_map`) and milestone behaviour are driven by
parameters — adding a 4th table requires only a new waypoint entry and no
logic changes.

### No external state-machine library
The state machine is a plain Python enum + branching logic in one function
(`_run_delivery_batch`). This keeps the dependency tree minimal and the code
readable.

### Multi-threaded safety
The order queue and cancellation flag are protected by `threading.Lock()`.
Navigation uses a background daemon thread; ROS callbacks run on the executor
thread pool.

### Confirmation decoupling
Kitchen and table confirmation are topic-based. This means any ROS-capable
device (button, GUI, mobile app) can send the confirmation signal without
changing the butler node.

---

## ROS 2 Concepts Used

| Concept | Where |
|---------|-------|
| Action Client (`NavigateToPose`) | `butler_node.py` — nav goals |
| Multi-threaded Executor | `butler_node.py` — parallel spin + blocking nav |
| Callback Groups | Nav client uses `MutuallyExclusiveCallbackGroup` |
| Parameters | All timeouts and confirm flags |
| Publishers / Subscribers | Status, order, cancel, confirmation |
| Services | Order Manager status query |
| Launch file with arguments | `butler.launch.py` |
| `rclpy.spin_until_future_complete` | Blocking wait inside nav helper |

---

*End of documentation — French Door Café Butler Robot v1.0*
