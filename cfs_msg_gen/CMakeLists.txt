cmake_minimum_required(VERSION 3.0.2)
project(cfs_msg_gen)

find_package(catkin REQUIRED)

catkin_python_setup()

catkin_package(
  CATKIN_DEPENDS message_runtime std_msgs
  CFG_EXTRAS cfs_msg_gen-extras.cmake)

# install the .action -> .msg generator
catkin_install_python(PROGRAMS generate_cfs_messages.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})


