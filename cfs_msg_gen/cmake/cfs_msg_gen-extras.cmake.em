# need genmsg for _prepend_path()
find_package(genmsg REQUIRED)

include(CMakeParseArguments)

@[if DEVELSPACE]@
# program in develspace
set(GENCFS_BIN "@(CMAKE_CURRENT_SOURCE_DIR)/generate_cfs_messages.py")
@[else]@
# program in installspace
set(GENCFS_BIN "${generate_cfs_messages_DIR}/../../../@(CATKIN_PACKAGE_BIN_DESTINATION)/generate_cfs_messages.py")
@[end if]@

macro(add_cfs_messages)

    set(_options "")
    set(_oneValueArgs BUNDLE MISSION TARGET)
    set(_multiValueArgs APPS STRUCTS CONSTANTS GLOBS)

    cmake_parse_arguments(
        ARG
        "${_options}"
        "${_oneValueArgs}"
        "${_multiValueArgs}"
        ${ARGN} )

    if(ARG_UNPARSED_ARGUMENTS)
        message(FATAL_ERROR "add_cfs_messages() called with unused arguments: ${ARG_UNPARSED_ARGUMENTS}")
    endif()

    #if(NOT IS_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/${ARG_DIRECTORY})
    #message(FATAL_ERROR "add_action_files() directory not found: ${CMAKE_CURRENT_SOURCE_DIR}/${ARG_DIRECTORY}")
    #endif()

    # get path to message generator script
    find_package(catkin REQUIRED COMPONENTS cfs_msg_gen)

    set(MESSAGE_DIR ${CATKIN_DEVEL_PREFIX}/share/${PROJECT_NAME}/msg)

    file(MAKE_DIRECTORY ${MESSAGE_DIR})

    safe_execute_process(COMMAND
        ${GENCFS_BIN}
        -p ${ARG_BUNDLE}
        --mission ${ARG_MISSION}
        --target ${ARG_TARGET}
        --apps ${ARG_APPS}
        --structs ${ARG_STRUCTS}
        --constants ${ARG_CONSTANTS}
        --globs ${ARG_GLOBS}
        -o ${MESSAGE_DIR})

    # get thelist of generated messages
    file(GLOB _autogen_msg_list "${MESSAGE_DIR}/*.msg")
    list(SORT _autogen_msg_list)

    set(OUTPUT_FILES "")
    foreach(_autogen_msg_path ${_autogen_msg_list})
        message(STATUS "Generated cFS Message " ${_autogen_msg_path})
        file(RELATIVE_PATH _autogen_msg_path_rel ${MESSAGE_DIR} ${_autogen_msg_path})
        list(APPEND OUTPUT_FILES ${_autogen_msg_path_rel})
    endforeach()


    add_message_files(
        BASE_DIR ${MESSAGE_DIR}
        FILES ${OUTPUT_FILES})
endmacro()
