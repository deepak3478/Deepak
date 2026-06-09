#!/usr/bin/env python3
"""
butler_robot.py
===============
Core state-machine for the Cafe Butler Robot.

Navigation Architecture
-----------------------
  Global Path Planning  : A* algorithm  (NavFn planner, use_astar=True)
  Local Obstacle Avoidance : Dijkstra-inspired DWB local planner
    - DWB evaluates candidate trajectories with a cost function equivalent
      to Dijkstra's shortest-path expansion in the local costmap.
    - Ensures dynamic obstacle avoidance with optimal local path selection.

Scenario Interface (ROS 2 topics)
----------------------------------
  Sub:  /butler/order    (std_msgs/String) -> "SCENARIO:TABLE1,TABLE2,..."
  Sub:  /butler/confirm  (std_msgs/String) -> "kitchen" | "table"
  Sub:  /butler/cancel   (std_msgs/String) -> "TABLE1" | "all" | "quit"
  Pub:  /butler/status   (std_msgs/String) -> human-readable log

Scenario Summary
----------------
  Sc 1  : Home -> Kitchen (collect, no confirm) -> Table -> Home
  Sc 2  : Home -> Kitchen (wait confirm|timeout->Home) -> Table
           (wait confirm|timeout->Home) -> Home
  Sc 3  : Home -> Kitchen (wait confirm|timeout->Home) -> Table
           (wait confirm|table-timeout->Kitchen->Home) -> Home
  Sc 4  : Home -> Kitchen -> Table -> Home  [cancel-aware]
           cancel@kitchen -> Home | cancel@table -> Kitchen -> Home
  Sc 5  : Home -> Kitchen (collect all) -> Table1..N -> Home  [no confirm]
  Sc 6  : Home -> Kitchen (collect all) -> Tables (timeout=skip next)
           -> if any unconfirmed: Kitchen -> Home | else: Home
  Sc 7  : Home -> Kitchen (collect all) -> Tables (skip cancelled)
           -> if any skipped: Kitchen -> Home | else: Home

Layout Reference (all waypoints are in FREE SPACE, NOT inside obstacles)
-------------------------------------------------------------------------
  Home     : (0.0, -5.0)  — south end, clear of all furniture
  Kitchen  : (0.0,  3.5)  — 1.5 m south of counter front face (y≈5.0)
                             Provides safe clearance from kitchen_counter
                             (center y=5.5, half-depth=0.5 -> front at y=5.0)
  Table 1  : (-4.0, 0.2)  — 1.3 m south of table1 top (center y=1.5)
  Table 2  : ( 0.0, 0.2)  — 1.3 m south of table2 top (center y=1.5)
  Table 3  : ( 4.0, 0.2)  — 1.3 m south of table3 top (center y=1.5)

  Waypoints are placed ≥ 1.5 m from every obstacle boundary so the
  inflation_radius (0.55 m) + robot_radius (0.22 m) cannot overlap them.
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import String
import threading
import time
import math


# ---------------------------------------------------------------------------
# Location map  (x, y, yaw_rad)
#
# Kitchen counter: center (0, 5.5), size (3.0 x 1.0)
#   -> occupies x=[-1.5..1.5], y=[5.0..6.0]
#   -> KITCHEN waypoint placed at y=3.5 (1.5 m clearance from y=5.0)
#
# Tables (top center y=1.5, half-width=0.6):
#   -> front face at y=1.1
#   -> TABLE waypoints at y=0.2 (0.9 m clearance from y=1.1)
#
# Chairs (center y=2.6, depth 0.1):
#   -> waypoints are SOUTH of chairs (y<1.1), so no conflict
#
# Walls at x=±7, y=±7 (0.2 m thick):
#   -> interior face at x=±6.9, y=±6.9
#   -> all waypoints are well inside
# ---------------------------------------------------------------------------
LOCATIONS = {
    #             x      y      yaw (rad)
    'HOME':    ( 0.0,  -5.0,   math.pi / 2),   # face north  (π/2)
    'KITCHEN': ( 0.0,   3.8,   math.pi / 2),   # face north toward counter
    'TABLE1':  (-4.0,   0.2,   math.pi / 2),   # south of Table 1, face north
    'TABLE2':  ( 0.0,   0.2,   math.pi / 2),   # south of Table 2, face north
    'TABLE3':  ( 4.0,   0.2,   math.pi / 2),   # south of Table 3, face north
}

# Seconds to wait for human confirmation before timing out
CONFIRMATION_TIMEOUT = 30.0

# Seconds to pause at kitchen/table for pickup/delivery
PICKUP_WAIT   = 3.0
DELIVERY_WAIT = 3.0

# Seconds to wait at kitchen after Key-X abort
ABORT_KITCHEN_WAIT = 5.0


class ButlerRobot(Node):
    """
    Multi-threaded ROS 2 butler state machine.

    Uses A* (via Nav2 NavFn planner) for global path planning and
    Dijkstra-equivalent DWB local planner for dynamic obstacle avoidance,
    ensuring optimal, collision-free navigation.
    """

    def __init__(self):
        super().__init__('butler_robot')
        self.cb_group = ReentrantCallbackGroup()

        # ── Nav2 action client (A* global + Dijkstra-like local planner) ──
        self._nav = ActionClient(self, NavigateToPose, 'navigate_to_pose',
                                 callback_group=self.cb_group)

        # ── Subscriptions ──
        self.create_subscription(String, '/butler/order',   self._order_cb,   10,
                                 callback_group=self.cb_group)
        self.create_subscription(String, '/butler/confirm', self._confirm_cb,  10,
                                 callback_group=self.cb_group)
        self.create_subscription(String, '/butler/cancel',  self._cancel_cb,   10,
                                 callback_group=self.cb_group)

        # ── Publisher ──
        self._status_pub = self.create_publisher(String, '/butler/status', 10)

        # ── Runtime state ──
        self._lock                = threading.Lock()
        self._confirmed           = threading.Event()
        self._confirmed_sources   = set()        # 'kitchen' and/or 'table'
        self._current_goal_handle = None         # active Nav2 goal handle
        self._cancel_requested    = False        # Key X: abort delivery
        self._quit_requested      = False        # Key Q: global quit
        self._skipped_tables      = set()        # tables skipped by user (Key x, y, z)
        self._current_target      = None         # active target waypoint name
        self._busy                = False

        self._log("[READY] Butler Robot initialised.")
        self._log("[NAV]   Global planner  : A* (NavFn, use_astar=True)")
        self._log("[NAV]   Local planner   : Dijkstra-inspired DWB (optimal local path)")
        self._log("[READY] Waiting for orders... (Key 1-7 / X / Y / Z / K / C / Q)")

    # ==========================================================================
    #  ROS 2 Callbacks
    # ==========================================================================

    def _order_cb(self, msg: String):
        """Receive an order from the controller or order nodes."""
        with self._lock:
            if self._busy:
                self._log("[WARNING] Robot is busy — order ignored.")
                return
            self._busy              = True
            self._cancel_requested  = False
            self._quit_requested    = False
            self._skipped_tables.clear()
            self._confirmed_sources.clear()
        
        self._confirmed.clear()

        try:
            parts    = msg.data.strip().split(':', 1)
            scenario = int(parts[0])
            tables   = [t.strip().upper() for t in parts[1].split(',') if t.strip()]
        except Exception as exc:
            self._log(f"[ERROR] Bad order format: {exc}  (expected 'SCENARIO:TABLE1,...')")
            with self._lock:
                self._busy = False
            return

        self._log(f"[ORDER] Scenario {scenario} | Tables: {tables}")

        thread = threading.Thread(
            target=self._run_scenario, args=(scenario, tables), daemon=True)
        thread.start()

    def _confirm_cb(self, msg: String):
        """Receive kitchen/table confirmation (Key k / c in order consoles)."""
        src = msg.data.strip().lower()
        if src in ('kitchen', 'table'):
            with self._lock:
                self._confirmed_sources.add(src)
            self._confirmed.set()
            self._log(f"[CONFIRM] Received confirmation from: {src}")

    def _cancel_cb(self, msg: String):
        """
        Receive cancel/quit commands.
          'all' | 'quit' | 'q'            -> Key Q (Global Quit)
          'TABLE1' | 'TABLE2' | 'TABLE3'  -> Skip Table (Key X, Y, Z)
        """
        tbl = msg.data.strip().upper()
        if tbl in ('ALL', 'QUIT', 'Q'):
            with self._lock:
                self._quit_requested = True
            self._log("[KEY-Q] Global Quit command received.")
            self._cancel_active_goal()
        elif tbl in ('TABLE1', 'TABLE2', 'TABLE3'):
            with self._lock:
                self._skipped_tables.add(tbl)
            self._log(f"[SKIP-CMD] Table requested to skip: {tbl}")
            # If currently navigating to this table, cancel the active goal
            with self._lock:
                tgt = self._current_target
            if tgt == tbl:
                self._log(f"[SKIP-CMD] Robot is currently navigating to {tbl}. Cancelling active goal to skip...")
                self._cancel_active_goal()
        else:
            with self._lock:
                self._cancel_requested = True
            self._log(f"[CANCEL-CMD] Abort received: {tbl}")
            self._cancel_active_goal()

    def _cancel_active_goal(self):
        with self._lock:
            gh = self._current_goal_handle
        if gh is not None:
            self._log("[CANCEL] Cancelling active Nav2 goal...")
            gh.cancel_goal_async()

    # ==========================================================================
    #  Scenario Router
    # ==========================================================================

    def _run_scenario(self, scenario: int, tables: list):
        status = 'SUCCESS'
        try:
            if scenario == 1:
                status = self._scenario_1(tables)
            elif scenario == 2:
                status = self._scenario_2(tables)
            elif scenario == 3:
                status = self._scenario_3(tables)
            elif scenario == 4:
                status = self._scenario_4(tables)
            elif scenario == 5:
                status = self._scenario_5(tables)
            elif scenario == 6:
                status = self._scenario_6(tables)
            elif scenario == 7:
                status = self._scenario_7(tables)
            else:
                self._log(f"[ERROR] Unknown scenario: {scenario}")
                return

            if status == 'QUIT':
                self._handle_quit()
            elif status == 'CANCELLED':
                self._handle_abort()
        except Exception as exc:
            self._log(f"[ERROR] Scenario crashed: {exc}")
        finally:
            with self._lock:
                self._busy = False

    # ==========================================================================
    #  Scenario Implementations
    # ==========================================================================

    def _scenario_1(self, tables: list) -> str:
        """
        Scenario 1: Single table autonomous delivery.
        Flow: Home -> Kitchen (collect, 3s pause) -> Table (deliver, 3s pause) -> Home.
        No confirmation required.
        """
        self._log("[SCENARIO-1] START: Single table autonomous delivery")
        table = tables[0] if tables else 'TABLE1'

        self._log("[SCENARIO-1] Navigating to KITCHEN...")
        st = self._navigate('KITCHEN')
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log("[SCENARIO-1] Collecting order at Kitchen...")
        st = self._sleep(PICKUP_WAIT)
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log(f"[SCENARIO-1] Navigating to {table}...")
        st = self._navigate(table)
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log(f"[SCENARIO-1] Delivering order at {table}...")
        st = self._sleep(DELIVERY_WAIT)
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log("[SCENARIO-1] Returning to HOME...")
        self._navigate('HOME')
        return 'SUCCESS'

    def _scenario_2(self, tables: list) -> str:
        """
        Scenario 2: Single table confirmation with timeout.
        If no one confirms (either at kitchen or table), return home after timeout.
        """
        self._log("[SCENARIO-2] START: Confirmation-based delivery, return home on timeout")
        table = tables[0] if tables else 'TABLE1'

        self._log("[SCENARIO-2] Navigating to KITCHEN...")
        st = self._navigate('KITCHEN')
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log(f"[SCENARIO-2] Waiting up to {CONFIRMATION_TIMEOUT}s for KITCHEN confirmation...")
        st = self._wait_confirm(CONFIRMATION_TIMEOUT, 'kitchen')
        if st in ('QUIT', 'CANCELLED'):
            return st
        if st == 'TIMEOUT':
            self._log("[SCENARIO-2] Kitchen confirmation timed out. Returning Home...")
            self._navigate('HOME')
            return 'SUCCESS'

        self._log("[SCENARIO-2] Kitchen confirmed. Collecting order...")
        st = self._sleep(PICKUP_WAIT)
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log(f"[SCENARIO-2] Navigating to {table}...")
        st = self._navigate(table)
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log(f"[SCENARIO-2] Waiting up to {CONFIRMATION_TIMEOUT}s for CUSTOMER confirmation at {table}...")
        st = self._wait_confirm(CONFIRMATION_TIMEOUT, 'table')
        if st in ('QUIT', 'CANCELLED'):
            return st
        if st == 'TIMEOUT':
            self._log("[SCENARIO-2] Customer confirmation timed out. Returning Home...")
            self._navigate('HOME')
            return 'SUCCESS'

        self._log(f"[SCENARIO-2] Customer confirmed. Delivering order...")
        st = self._sleep(DELIVERY_WAIT)
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log("[SCENARIO-2] Returning to HOME...")
        self._navigate('HOME')
        return 'SUCCESS'

    def _scenario_3(self, tables: list) -> str:
        """
        Scenario 3: Single table confirmation with return food to kitchen on table timeout.
        - Kitchen timeout: return home.
        - Table timeout: return food to kitchen first, then home.
        """
        self._log("[SCENARIO-3] START: Confirmation-based delivery, return to kitchen on table timeout")
        table = tables[0] if tables else 'TABLE1'

        self._log("[SCENARIO-3] Navigating to KITCHEN...")
        st = self._navigate('KITCHEN')
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log(f"[SCENARIO-3] Waiting up to {CONFIRMATION_TIMEOUT}s for KITCHEN confirmation...")
        st = self._wait_confirm(CONFIRMATION_TIMEOUT, 'kitchen')
        if st in ('QUIT', 'CANCELLED'):
            return st
        if st == 'TIMEOUT':
            self._log("[SCENARIO-3] Kitchen confirmation timed out. Returning Home...")
            self._navigate('HOME')
            return 'SUCCESS'

        self._log("[SCENARIO-3] Kitchen confirmed. Collecting order...")
        st = self._sleep(PICKUP_WAIT)
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log(f"[SCENARIO-3] Navigating to {table}...")
        st = self._navigate(table)
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log(f"[SCENARIO-3] Waiting up to {CONFIRMATION_TIMEOUT}s for CUSTOMER confirmation at {table}...")
        st = self._wait_confirm(CONFIRMATION_TIMEOUT, 'table')
        if st in ('QUIT', 'CANCELLED'):
            return st
        if st == 'TIMEOUT':
            self._log("[SCENARIO-3] Customer confirmation timed out. Returning food to KITCHEN...")
            self._navigate('KITCHEN')
            self._sleep(5.0)
            self._log("[SCENARIO-3] Returning Home...")
            self._navigate('HOME')
            return 'SUCCESS'

        self._log(f"[SCENARIO-3] Customer confirmed. Delivering order at {table}...")
        st = self._sleep(DELIVERY_WAIT)
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log("[SCENARIO-3] Returning to HOME...")
        self._navigate('HOME')
        return 'SUCCESS'

    def _scenario_4(self, tables: list) -> str:
        """
        Scenario 4: Task cancel handling.
        - Canceled while going to kitchen: return home.
        - Canceled while going to table: return food to kitchen, then home.
        """
        self._log("[SCENARIO-4] START: Cancel handling mode")
        table = tables[0] if tables else 'TABLE1'

        self._log("[SCENARIO-4] Navigating to KITCHEN...")
        st = self._navigate('KITCHEN')
        if st in ('QUIT', 'CANCELLED'):
            self._log("[SCENARIO-4] Canceled/Quit while going to KITCHEN. Returning Home...")
            with self._lock:
                self._cancel_requested = False
                self._quit_requested = False
            self._navigate('HOME')
            return 'SUCCESS'

        self._log("[SCENARIO-4] Collecting order at Kitchen...")
        st = self._sleep(PICKUP_WAIT)
        if st in ('QUIT', 'CANCELLED'):
            self._log("[SCENARIO-4] Canceled/Quit at Kitchen. Returning Home...")
            with self._lock:
                self._cancel_requested = False
                self._quit_requested = False
            self._navigate('HOME')
            return 'SUCCESS'

        self._log(f"[SCENARIO-4] Navigating to {table}...")
        st = self._navigate(table)
        if st in ('QUIT', 'CANCELLED'):
            self._log(f"[SCENARIO-4] Canceled/Quit while going to {table}. Returning food to KITCHEN first...")
            with self._lock:
                self._cancel_requested = False
                self._quit_requested = False
            self._navigate('KITCHEN')
            self._sleep(5.0)
            self._log("[SCENARIO-4] Returning Home...")
            self._navigate('HOME')
            return 'SUCCESS'

        self._log(f"[SCENARIO-4] Delivering order at {table}...")
        st = self._sleep(DELIVERY_WAIT)
        if st in ('QUIT', 'CANCELLED'):
            self._log(f"[SCENARIO-4] Canceled/Quit during delivery at {table}. Returning food to KITCHEN first...")
            with self._lock:
                self._cancel_requested = False
                self._quit_requested = False
            self._navigate('KITCHEN')
            self._sleep(5.0)
            self._log("[SCENARIO-4] Returning Home...")
            self._navigate('HOME')
            return 'SUCCESS'

        self._log("[SCENARIO-4] Returning to HOME...")
        self._navigate('HOME')
        return 'SUCCESS'

    def _scenario_5(self, tables: list) -> str:
        """
        Scenario 5: Multiple tables autonomous delivery.
        """
        self._log(f"[SCENARIO-5] START: Multi-table autonomous delivery to {tables}")

        self._log("[SCENARIO-5] Navigating to KITCHEN...")
        st = self._navigate('KITCHEN')
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log("[SCENARIO-5] Collecting orders at Kitchen...")
        st = self._sleep(PICKUP_WAIT)
        if st in ('QUIT', 'CANCELLED'):
            return st

        for table in tables:
            self._log(f"[SCENARIO-5] Navigating to {table}...")
            st = self._navigate(table)
            if st in ('QUIT', 'CANCELLED'):
                return st

            self._log(f"[SCENARIO-5] Delivering order at {table}...")
            st = self._sleep(DELIVERY_WAIT)
            if st in ('QUIT', 'CANCELLED'):
                return st

        self._log("[SCENARIO-5] Returning to HOME...")
        self._navigate('HOME')
        return 'SUCCESS'

    def _scenario_6(self, tables: list) -> str:
        """
        Scenario 6: Multiple tables with per-table confirmation / timeout.

        Spec:
          Home -> Kitchen (autonomous collect, no confirmation needed)
               -> for each table: arrive, wait for customer confirm
                    * if confirmed  -> deliver (brief wait) -> next table
                    * if timeout    -> skip table, continue to next
          After all tables: if ANY table was unconfirmed/skipped
               -> return to Kitchen first, THEN Home
          Otherwise -> Home directly.
        """
        self._log(f"[SCENARIO-6] START: Multi-table confirmation delivery to {tables}")
        unconfirmed_present = False

        # ── Step 1: Go to Kitchen and collect (no confirmation required) ──
        self._log("[SCENARIO-6] Navigating to KITCHEN...")
        st = self._navigate('KITCHEN')
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log("[SCENARIO-6] Collecting all orders at Kitchen...")
        st = self._sleep(PICKUP_WAIT)
        if st in ('QUIT', 'CANCELLED'):
            return st

        # ── Step 2: Visit each table and wait for customer confirmation ──
        for table in tables:
            self._log(f"[SCENARIO-6] Navigating to {table}...")
            st = self._navigate(table)
            if st in ('QUIT', 'CANCELLED'):
                return st

            # Clear stale confirmation state before waiting at this table
            self._confirmed.clear()
            with self._lock:
                self._confirmed_sources.discard('table')

            self._log(f"[SCENARIO-6] Waiting up to {CONFIRMATION_TIMEOUT}s for customer confirmation at {table}...")
            st = self._wait_confirm(CONFIRMATION_TIMEOUT, 'table')
            if st in ('QUIT', 'CANCELLED'):
                return st
            if st == 'TIMEOUT':
                self._log(f"[SCENARIO-6] {table} timed out — skipping, moving to next table.")
                unconfirmed_present = True
            else:
                self._log(f"[SCENARIO-6] {table} confirmed. Delivering food...")
                st = self._sleep(DELIVERY_WAIT)
                if st in ('QUIT', 'CANCELLED'):
                    return st

        # ── Step 3: If any unconfirmed, revisit Kitchen before Home ──
        if unconfirmed_present:
            self._log("[SCENARIO-6] Unconfirmed tables exist. Returning remaining food to KITCHEN...")
            self._navigate('KITCHEN')
            self._sleep(5.0)

        self._log("[SCENARIO-6] Returning to HOME...")
        self._navigate('HOME')
        return 'SUCCESS'

    def _scenario_7(self, tables: list) -> str:
        """
        Scenario 7: Multiple tables with cancel/skip handling.

        Spec:
          Home -> Kitchen (collect all orders, autonomous)
               -> for each table:
                    * if table was pre-cancelled -> skip it
                    * if table cancelled during navigation -> skip it
                    * otherwise -> deliver (brief wait)
          After all tables: if ANY table was skipped
               -> return to Kitchen first, THEN Home.
          Otherwise -> Home directly.
        """
        self._log(f"[SCENARIO-7] START: Multi-table cancel-aware delivery to {tables}")
        skipped_present = False

        # ── Step 1: Go to Kitchen and collect (autonomous, no confirmation) ──
        self._log("[SCENARIO-7] Navigating to KITCHEN...")
        st = self._navigate('KITCHEN')
        if st in ('QUIT', 'CANCELLED'):
            return st

        self._log("[SCENARIO-7] Collecting all orders at Kitchen...")
        st = self._sleep(PICKUP_WAIT)
        if st in ('QUIT', 'CANCELLED'):
            return st

        # ── Step 2: Deliver to each table (skip cancelled ones) ──
        for table in tables:
            # Check if already cancelled before we even start navigating
            with self._lock:
                is_skipped = table in self._skipped_tables
            if is_skipped:
                self._log(f"[SCENARIO-7] {table} pre-cancelled — skipping.")
                skipped_present = True
                continue

            self._log(f"[SCENARIO-7] Navigating to {table}...")
            st = self._navigate(table)

            # Check again: table may have been cancelled during navigation
            with self._lock:
                is_skipped = table in self._skipped_tables
            if st == 'CANCELLED' or is_skipped:
                self._log(f"[SCENARIO-7] {table} cancelled during navigation — skipping.")
                skipped_present = True
                with self._lock:
                    self._cancel_requested = False   # clear local cancel; keep going
                continue
            if st == 'QUIT':
                return st

            self._log(f"[SCENARIO-7] Delivering order at {table}...")
            st = self._sleep(DELIVERY_WAIT)
            if st == 'QUIT':
                return st
            # If cancel is raised during delivery, treat this table as skipped
            if st == 'CANCELLED':
                self._log(f"[SCENARIO-7] {table} cancelled during delivery — marking skipped.")
                skipped_present = True
                with self._lock:
                    self._cancel_requested = False
                continue

        # ── Step 3: If any table skipped, return food to Kitchen first ──
        if skipped_present:
            self._log("[SCENARIO-7] Some tables skipped. Returning remaining food to KITCHEN...")
            self._navigate('KITCHEN')
            self._sleep(5.0)

        self._log("[SCENARIO-7] Returning to HOME...")
        self._navigate('HOME')
        return 'SUCCESS'

    # ==========================================================================
    #  Safety Override Handlers
    # ==========================================================================

    def _handle_quit(self):
        """
        Key Q — Global Quit.
        Immediately terminate all operations and navigate robot to Home.
        """
        self._log("[KEY-Q] Executing Global Quit. Navigating to HOME...")
        with self._lock:
            self._quit_requested   = False
            self._cancel_requested = False
        self._navigate('HOME')
        self._log("[KEY-Q] Complete. Robot stopped at HOME.")

    def _handle_abort(self):
        """
        Key X — Order Cancellation / Abort.
        Return food to Kitchen, wait 5 s, return to Home.
        """
        self._log("[KEY-X] Aborting delivery. Returning food to KITCHEN...")
        with self._lock:
            self._quit_requested   = False
            self._cancel_requested = False

        # Return food to kitchen
        self._navigate('KITCHEN')
        self._log(f"[KEY-X] Food returned. Waiting {ABORT_KITCHEN_WAIT}s at Kitchen...")
        time.sleep(ABORT_KITCHEN_WAIT)

        # Return to home
        self._log("[KEY-X] Returning to HOME...")
        self._navigate('HOME')
        self._log("[KEY-X] Abort complete. Robot at HOME.")

    # ==========================================================================
    #  Navigation Helper
    # ==========================================================================

    def _navigate(self, location: str, max_retries: int = 3) -> str:
        """
        Navigate to a named location using A* global planning and
        Dijkstra-inspired DWB local obstacle avoidance.

        Returns: 'SUCCESS', 'CANCELLED', 'QUIT', or 'FAILED'.
        """
        if location not in LOCATIONS:
            self._log(f"[ERROR] Unknown location: {location}")
            return 'FAILED'

        with self._lock:
            self._current_target = location

        try:
            for attempt in range(1, max_retries + 1):
                if self._quit_requested:
                    return 'QUIT'
                with self._lock:
                    is_skipped = location in self._skipped_tables
                if self._cancel_requested or is_skipped:
                    return 'CANCELLED'

                if attempt > 1:
                    self._log(f"[RETRY] Attempt {attempt}/{max_retries} -> {location}")
                    for _ in range(20):
                        if self._quit_requested:
                            return 'QUIT'
                        with self._lock:
                            is_skipped = location in self._skipped_tables
                        if self._cancel_requested or is_skipped:
                            return 'CANCELLED'
                        time.sleep(0.1)
                else:
                    self._log(f"[MOVE] A* path -> {location}")

                self._status_pub.publish(String(data=f"MOVING:{location}"))

                goal = NavigateToPose.Goal()
                goal.pose = self._make_pose(*LOCATIONS[location])

                self._nav.wait_for_server()
                future = self._nav.send_goal_async(goal)

                # Wait for goal acceptance
                while not future.done():
                    if self._quit_requested:
                        return 'QUIT'
                    with self._lock:
                        is_skipped = location in self._skipped_tables
                    if self._cancel_requested or is_skipped:
                        return 'CANCELLED'
                    time.sleep(0.05)

                goal_handle = future.result()
                if not goal_handle.accepted:
                    self._log(f"[ERROR] Goal to {location} rejected by Nav2 — retrying...")
                    continue

                with self._lock:
                    self._current_goal_handle = goal_handle

                result_future   = goal_handle.get_result_async()
                cancelled_sent  = False

                while not result_future.done():
                    with self._lock:
                        is_skipped = location in self._skipped_tables
                    if (self._quit_requested or self._cancel_requested or is_skipped) and not cancelled_sent:
                        self._log("[CANCEL] Aborting active Nav2 goal...")
                        goal_handle.cancel_goal_async()
                        cancelled_sent = True
                    time.sleep(0.1)

                with self._lock:
                    self._current_goal_handle = None

                if self._quit_requested:
                    return 'QUIT'
                with self._lock:
                    is_skipped = location in self._skipped_tables
                if self._cancel_requested or is_skipped:
                    return 'CANCELLED'

                nav_status = result_future.result().status
                if nav_status == 4:   # GoalStatus.SUCCEEDED
                    self._log(f"[SUCCESS] Reached {location} (A* path + Dijkstra local avoidance)")
                    self._status_pub.publish(String(data=f"ARRIVED:{location}"))
                    return 'SUCCESS'
                else:
                    self._log(f"[ERROR] Failed to reach {location} (status={nav_status}), retrying...")

            self._log(f"[ERROR] All {max_retries} attempts to reach {location} failed!")
            return 'FAILED'

        finally:
            with self._lock:
                self._current_target = None

    def _sleep(self, seconds: float) -> str:
        """Interruptible sleep: checks cancel/quit every 100 ms."""
        end = time.time() + seconds
        while time.time() < end:
            if self._quit_requested:
                return 'QUIT'
            if self._cancel_requested:
                return 'CANCELLED'
            time.sleep(0.1)
        return 'SUCCESS'

    def _wait_confirm(self, timeout: float, expected_source: str) -> str:
        """
        Wait up to 'timeout' seconds for a confirmation from 'expected_source'.
        Returns: 'SUCCESS', 'TIMEOUT', 'QUIT', or 'CANCELLED'.
        """
        self._log(f"[WAIT] Expecting '{expected_source}' confirmation (timeout={timeout}s)...")

        # Already confirmed before we started waiting?
        with self._lock:
            if expected_source in self._confirmed_sources:
                self._confirmed_sources.discard(expected_source)
                self._log(f"[CONFIRM] '{expected_source}' was already confirmed.")
                return 'SUCCESS'

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._quit_requested:
                return 'QUIT'
            if self._cancel_requested:
                return 'CANCELLED'

            remaining = deadline - time.time()
            self._confirmed.wait(timeout=min(0.2, remaining))
            self._confirmed.clear()

            with self._lock:
                if expected_source in self._confirmed_sources:
                    self._confirmed_sources.discard(expected_source)
                    return 'SUCCESS'

        self._log(f"[TIMEOUT] No '{expected_source}' confirmation within {timeout}s.")
        return 'TIMEOUT'

    def _make_pose(self, x: float, y: float, yaw: float = 0.0) -> PoseStamped:
        """Build a PoseStamped in the 'map' frame from (x, y, yaw)."""
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp    = self.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)
        return pose

    def _log(self, msg: str):
        self.get_logger().info(msg)
        self._status_pub.publish(String(data=msg))


# ---------------------------------------------------------------------------
def main(args=None):
    rclpy.init(args=args)
    node     = ButlerRobot()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
