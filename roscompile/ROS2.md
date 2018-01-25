### Message and service definitions
In your `package.xml` you will need to add:
- For each dependent message package add `<depend>message_package</depend>`

In your `CMakeLists.txt`:
- For each dependent message package add `find_package(message_package REQUIRED)` and

### Build system

#### Pure Python package
- Update the `setup.py` file to be a standard Python setup script
- Python3

#### Update the *CMakeLists.txt* to use *ament_cmake*

Apply the following changes to use `ament_cmake` instead of `catkin`:

- Move and update the `catkin_package` invocation with:

  - Invoke `ament_package` instead but **after** all targets have been registered.

  - The only valid argument for [ament_package](https://github.com/ament/ament_cmake/blob/master/ament_cmake_core/cmake/core/ament_package.cmake) is `CONFIG_EXTRAS`.
    All other arguments are covered by separate functions which all need to be invoked *before* `ament_package`.

  - **TODO document ament_export_interfaces?**

- Remove any occurrences of the *devel space*.
  Related CMake variables like `CATKIN_DEVEL_PREFIX` do not exist anymore.

  - The `CATKIN_DEPENDS` and `DEPENDS` arguments are passed to the new function [ament_export_dependencies](https://github.com/ament/ament_cmake/blob/master/ament_cmake_export_dependencies/cmake/ament_export_dependencies.cmake).

#### Unit tests

If you are using gtest

- replace `CATKIN_ENABLE_TESTING` with `BUILD_TESTING` (until alpha 5 this was `AMENT_ENABLE_TESTING`)
- replace `catkin_add_gtest` with `ament_add_gtest`
- add a `<test_depend>ament_cmake_gtest</test_depend>`

##### Linters

In ROS 2.0 we are working to maintain clean code using linters.
The styles for different languages are defined in our [Developer Guide](https://github.com/ros2/ros2/wiki/Developer-Guide).

If you are starting a project from scratch it is recommended to follow the style guide and turn on the automatic linter unittests by adding these lines just below `if(BUILD_TESTING)` (until alpha 5 this was `AMENT_ENABLE_TESTING`)

``` cmake
find_package(ament_lint_auto REQUIRED)
ament_lint_auto_find_test_dependencies()
```

You will also need to add the following dependencies to your `package.xml`:

``` xml
<test_depend>ament_lint_auto</test_depend>
<test_depend>ament_lint_common</test_depend>
```

### Update source code

## Launch files

While launch files in ROS 1 are specified using [.xml](http://wiki.ros.org/roslaunch/XML) files ROS 2 uses Python scripts to enable more flexibility (see [launch package](https://github.com/ros2/launch/tree/master/launch)).

## Example: Converting an existing ROS 1 package to use ROS 2


### Migrating to ROS 2

Let's start by creating a new workspace in which to work:

``` bash
mkdir ~/ros2_talker
cd ~/ros2_talker
```

We'll copy the source tree from our ROS 1 package into that workspace, where we can modify it:

``` bash
mkdir src
cp -a ~/ros1_talker/src/talker src
```

Now we'll modify the the C++ code in the node.
The ROS 2 C++ library, called `rclcpp`, provides a different API from that
provided by `roscpp`.
The concepts are very similar between the two libraries, which makes the changes
reasonably straightforward to make.


#### Changing C++ library calls

Instead of passing the node's name to the library initialization call, we do
the initialization, then pass the node name to the creation of the node object

``` cpp
//  ros::NodeHandle n;
    auto node = rclcpp::node::Node::make_shared("talker");
```

The creation of the publisher and rate objects looks pretty similar, with some
changes to the names of namespace and methods.
For the publisher, instead of an integer queue length argument, we pass a
quality of service (qos) profile, which is a far more flexible way to
controlling how message delivery is handled.
In this example, we just pass the default profile `rmw_qos_profile_default`
(it's global because it's declared in `rmw`, which is written in C and so
doesn't have namespaces).

``` cpp
//  ros::Publisher chatter_pub = n.advertise<std_msgs::String>("chatter", 1000);
//  ros::Rate loop_rate(10);
  auto chatter_pub = node->create_publisher<std_msgs::msg::String>("chatter",
    rmw_qos_profile_default);
  rclcpp::rate::Rate loop_rate(10);
```

The creation of the outgoing message is different in both the namespace and the
fact that we go ahead and create a shared pointer (this may change in the future
with more publish API that accepts const references):

``` cpp
//  std_msgs::String msg;
  auto msg = std::make_shared<std_msgs::msg::String>();
```

Inside the publishing loop, we use the `->` operator to access the `data` field
(because now `msg` is a shared pointer):

``` cpp
//    msg.data = ss.str();
    msg->data = ss.str();
```

To print a console message, instead of using `ROS_INFO()`, we use `printf()`
(this is temporary, because we don't yet have an equivalent of the `rosconsole`
package):

``` cpp
//    ROS_INFO("%s", msg.data.c_str());
    printf("%s\n", msg->data.c_str());
```

Publishing the message is very similar, the only noticeable difference being
that the publisher is now a shared pointer:

``` cpp
//    chatter_pub.publish(msg);
    chatter_pub->publish(msg);
```

#### Changing the `package.xml`

ROS 2 uses a newer version of `catkin`, called `ament`, which we specify in the
`buildtool_depend` tag:

``` xml
<!--  <buildtool_depend>catkin</buildtool_depend> -->
  <buildtool_depend>ament_cmake</buildtool_depend>
```

In our build dependencies, instead of `roscpp` we use `rclcpp`, which provides
the C++ API that we use.
We additionally depend on `rmw_implementation`, which pulls in the default
implementation of the `rmw` abstraction layer that allows us to support multiple
DDS implementations (we should consider restructuring / renaming things so that
it's possible to depend on one thing, analogous to `roscpp`):

``` xml
<!--  <build_depend>roscpp</build_depend> -->
  <build_depend>rclcpp</build_depend>
  <build_depend>rmw_implementation</build_depend>
```

We make the same addition in the run dependencies and also update from the
`run_depend` tag to the `exec_depend` tag (part of the upgrade to version 2 of
the package format):

``` xml
<!--  <run_depend>roscpp</run_depend> -->
  <exec_depend>rclcpp</exec_depend>
  <exec_depend>rmw_implementation</exec_depend>
<!--  <run_depend>std_msgs</run_depend> -->
  <exec_depend>std_msgs</exec_depend>
```

#### Changing the CMake code

``` cmake
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")
```

We call `catkin_package()` to auto-generate things like CMake configuration
files for other packages that use our package.
Whereas that call happens *before* specifying targets to build, we now call the
analogous `ament_package()` *after* the targets:

``` cmake
# catkin_package()
# At the bottom of the file:
ament_package()
```

Similarly to how we found each dependent package separately, instead of finding
them as parts of catkin, we also need to add their include directories
separately (see also `ament_target_dependencies()` below, which is a more
concise and more thorough way of handling dependent packages' build flags):

``` cmake
#include_directories(${catkin_INCLUDE_DIRS})
include_directories(${rclcpp_INCLUDE_DIRS}
                    ${rmw_implementation_INCLUDE_DIRS}
                    ${std_msgs_INCLUDE_DIRS})
```

We do the same to link against our dependent packages' libraries:

``` cmake
#target_link_libraries(talker ${catkin_LIBRARIES})
target_link_libraries(talker
                      ${rclcpp_LIBRARIES}
                      ${rmw_implementation_LIBRARIES}
                      ${std_msgs_LIBRARIES})
```

**TODO: explain how `ament_target_dependencies()` simplifies the above steps and
is also better (also handling `*_DEFINITIONS`, doing target-specific include
directories, etc.).**

For installation, `catkin` defines variables like
`CATKIN_PACKAGE_BIN_DESTINATION`.
With `ament`, we just give a path relative to the installation root, like `bin`
for executables (this is in part because we don't yet have an equivalent of
`rosrun`):

``` cmake
#install(TARGETS talker
#  RUNTIME DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})
install(TARGETS talker RUNTIME DESTINATION bin)
```
