cmake_minimum_required(VERSION 3.8)
project(coffee_shop_sim)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY launch config worlds urdf maps
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
