# CFS Message Gen

Generate ROS messages from cFS header files.

ROS message spec: http://wiki.ros.org/msg

## Example CMake Usage

Add `cfs_msg_gen` as a build dependency to the ROS package's `package.xml` file and as a package to the `find_pacakge()` call in the package's `CMakeLists.txt`.

Then add the following to `CMakeLists.txt` to build messages supporting the identified structs:

```cmake
add_cfs_messages(
    BUNDLE /path/to/cfs/bundle
    MISSION sim
    TARGET linux-x86-core
    APPS ci_lab to_lab SBN
    GLOBS TO_LAB_EnableOutput_Payload_t)
```

## Example CLI Usage

Run the script from the cFS bundle directory:

```sh
../../dependencies/roscfs/cfs_msg_gen/generate_messages.py --mission sim --target linux-x86-core --apps ci_lab to_lab SBN --structs TO_LAB_EnableOutput_Payload_t
```

Output:

```
# DO NOT EDIT: Auto-generated from cfs headers.
string dest_IP
```
