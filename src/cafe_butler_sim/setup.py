from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'cafe_butler_sim'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        # ament index marker
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        # package.xml
        ('share/' + package_name, ['package.xml']),
        # Launch files
        (os.path.join('share', package_name, 'launch'),
         glob('launch/*.launch.py')),
        # World files
        (os.path.join('share', package_name, 'world'),
         glob('world/*.world')),
        # Config files (yaml + rviz + map)
        (os.path.join('share', package_name, 'config'),
         glob('config/*.yaml') + glob('config/*.rviz')),
        # Map files (pgm)
        (os.path.join('share', package_name, 'config'),
         glob('config/*.pgm')),
        # URDF / xacro
        (os.path.join('share', package_name, 'urdf'),
         glob('urdf/*.urdf.xacro') + glob('urdf/*.urdf')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='deepak33',
    maintainer_email='deepak33@todo.todo',
    description='ROS 2 Cafe Butler Robot Simulation - 7 Delivery Scenarios',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'butler_robot        = cafe_butler_sim.butler_robot:main',
            'butler_controller   = cafe_butler_sim.butler_controller:main',
            'table1_controller   = cafe_butler_sim.table1_controller:main',
            'table2_controller   = cafe_butler_sim.table2_controller:main',
            'table3_controller   = cafe_butler_sim.table3_controller:main',
            'order_client        = cafe_butler_sim.order_client:main',
            'order_table1        = cafe_butler_sim.order_table1:main',
            'order_table2        = cafe_butler_sim.order_table2:main',
            'order_table3        = cafe_butler_sim.order_table3:main',
        ],
    },
)
