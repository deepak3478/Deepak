cmake_minimum_required(VERSION 3.8)
project(coffee_shop_butler)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)

# Install Python package (butler_node, order_manager_node, __init__)
ament_python_install_package(${PROJECT_NAME})

# Install scripts as executables (no mock_test)
install(PROGRAMS
  coffee_shop_butler/butler_node.py
  coffee_shop_butler/order_manager_node.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch files and config
install(
  DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
