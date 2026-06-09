#!/usr/bin/env python3
"""
generate_map.py  –  run once to produce cafe_map.pgm + cafe_map.yaml
Usage:  python3 generate_map.py
"""
import math

# Map parameters
WIDTH      = 280   # pixels  (14 m / 0.05 m per pixel)
HEIGHT     = 280
RESOLUTION = 0.05  # m/pixel
ORIGIN_X   = -7.0
ORIGIN_Y   = -7.0

FREE      = 254
OCCUPIED  = 0
UNKNOWN   = 205


def world_to_pixel(wx, wy):
    px = int((wx - ORIGIN_X) / RESOLUTION)
    py = int((wy - ORIGIN_Y) / RESOLUTION)
    return px, py


def fill_rect(grid, wx1, wy1, wx2, wy2, val=OCCUPIED):
    px1, py1 = world_to_pixel(wx1, wy1)
    px2, py2 = world_to_pixel(wx2, wy2)
    for y in range(min(py1, py2), max(py1, py2) + 1):
        for x in range(min(px1, px2), max(px1, px2) + 1):
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                grid[y][x] = val


# Blank map (all free)
grid = [[FREE] * WIDTH for _ in range(HEIGHT)]

# Outer walls  (0.1 m thick)
# North wall  y=6.9..7.0
fill_rect(grid, -7.0, 6.9,  7.0,  7.0)
# South wall  y=-7.0..-6.9
fill_rect(grid, -7.0, -7.0, 7.0, -6.9)
# East wall   x=6.9..7.0
fill_rect(grid,  6.9, -7.0, 7.0,  7.0)
# West wall   x=-7.0..-6.9
fill_rect(grid, -7.0, -7.0, -6.9, 7.0)

# Kitchen counter  (3m x 1m)  center (0, 5.5)
fill_rect(grid, -1.5, 5.0, 1.5, 6.0)

# Kitchen sign post at (-1.0, 5.0) - thin but present
fill_rect(grid, -1.1, 4.9, -0.9, 5.1)

# Table 1  (1.2m x 0.8m)  center (-4, 1.5)
fill_rect(grid, -4.6, 1.1, -3.4, 1.9)

# Chair 1  (0.5m x 0.1m)  center (-4, 2.6)
fill_rect(grid, -4.3, 2.5, -3.7, 2.7)

# Table 2  center (0, 1.5)
fill_rect(grid, -0.6, 1.1,  0.6, 1.9)

# Chair 2  (0.5m x 0.1m)  center (0, 2.6)
fill_rect(grid, -0.3, 2.5,  0.3, 2.7)

# Table 3  center (4, 1.5)
fill_rect(grid,  3.4, 1.1,  4.6, 1.9)

# Chair 3  (0.5m x 0.1m)  center (4, 2.6)
fill_rect(grid,  3.7, 2.5,  4.3, 2.7)

# Flip vertically (pgm origin = bottom-left, array row 0 = top)
grid_flipped = grid[::-1]

# Write PGM
with open('cafe_map.pgm', 'wb') as f:
    header = f"P5\n{WIDTH} {HEIGHT}\n255\n"
    f.write(header.encode())
    for row in grid_flipped:
        f.write(bytes(row))

# Write YAML
yaml_content = f"""image: cafe_map.pgm
resolution: {RESOLUTION}
origin: [{ORIGIN_X}, {ORIGIN_Y}, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.25
"""
with open('cafe_map.yaml', 'w') as f:
    f.write(yaml_content)

print("Map files generated: cafe_map.pgm + cafe_map.yaml")
