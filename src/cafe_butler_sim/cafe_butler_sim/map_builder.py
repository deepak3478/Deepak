#!/usr/bin/env python3
"""
map_builder.py
==============
Standalone utility to generate cafe_map.pgm and cafe_map.yaml.
Run this ONCE before building to create the static map files:

  python3 src/cafe_butler_sim/cafe_butler_sim/map_builder.py

The output files are written into:
  src/cafe_butler_sim/config/cafe_map.pgm
  src/cafe_butler_sim/config/cafe_map.yaml
"""

import os
import pathlib

# Map parameters (must match cafe.world dimensions)
WIDTH      = 280   # pixels  (14 m wide / 0.05 m·px)
HEIGHT     = 280   # pixels  (14 m tall / 0.05 m·px)
RESOLUTION = 0.05  # m / pixel
ORIGIN_X   = -7.0  # world X at pixel column 0
ORIGIN_Y   = -7.0  # world Y at pixel row 0

FREE     = 254
OCCUPIED = 0


def w2p(wx, wy):
    """World coords -> pixel (col, row)."""
    return int((wx - ORIGIN_X) / RESOLUTION), int((wy - ORIGIN_Y) / RESOLUTION)


def fill_rect(grid, wx1, wy1, wx2, wy2, val=OCCUPIED):
    x1, y1 = w2p(wx1, wy1)
    x2, y2 = w2p(wx2, wy2)
    for r in range(min(y1, y2), max(y1, y2) + 1):
        for c in range(min(x1, x2), max(x1, x2) + 1):
            if 0 <= c < WIDTH and 0 <= r < HEIGHT:
                grid[r][c] = val


def build():
    grid = [[FREE] * WIDTH for _ in range(HEIGHT)]

    # Outer walls (0.2 m thick)
    fill_rect(grid, -7.0,  6.8,  7.0,  7.0)   # North
    fill_rect(grid, -7.0, -7.0,  7.0, -6.8)   # South
    fill_rect(grid,  6.8, -7.0,  7.0,  7.0)   # East
    fill_rect(grid, -7.0, -7.0, -6.8,  7.0)   # West

    # Kitchen counter  (3m × 1m)  centred at (0, 5.5)
    fill_rect(grid, -1.5, 5.0, 1.5, 6.0)

    # Table 1  (1.4m × 1m)  centred at (-4, 1.5)
    fill_rect(grid, -4.7, 1.0, -3.3, 2.0)

    # Table 2  centred at (0, 1.5)
    fill_rect(grid, -0.7, 1.0,  0.7, 2.0)

    # Table 3  centred at (4, 1.5)
    fill_rect(grid,  3.3, 1.0,  4.7, 2.0)

    # PGM origin is bottom-left; row 0 in our array is world south -> flip
    grid_out = grid[::-1]

    # Locate output dir
    this_dir   = pathlib.Path(__file__).parent
    config_dir = this_dir.parent / 'config'
    config_dir.mkdir(exist_ok=True)

    pgm_path  = config_dir / 'cafe_map.pgm'
    yaml_path = config_dir / 'cafe_map.yaml'

    # Write binary P5 PGM
    with open(pgm_path, 'wb') as f:
        f.write(f"P5\n{WIDTH} {HEIGHT}\n255\n".encode())
        for row in grid_out:
            f.write(bytes(row))

    # Write YAML
    yaml_path.write_text(
        f"image: cafe_map.pgm\n"
        f"resolution: {RESOLUTION}\n"
        f"origin: [{ORIGIN_X}, {ORIGIN_Y}, 0.0]\n"
        f"negate: 0\n"
        f"occupied_thresh: 0.65\n"
        f"free_thresh: 0.25\n"
    )

    print(f"[SUCCESS]  Map written to:\n    {pgm_path}\n    {yaml_path}")


if __name__ == '__main__':
    build()
