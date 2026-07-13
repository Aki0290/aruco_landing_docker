from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory
from launch.launch_description_sources import PythonLaunchDescriptionSource


def launch_setup(context, *args, **kwargs):
    # 'sim' argument: true means simulation mode.
    sim_mode = LaunchConfiguration("sim").perform(context) == "true"

    if sim_mode:
        fcu_url = "udp://:14551@127.0.0.1:14550"
    else:
        fcu_url = "/dev/ttyAMA0:921600"

    mavros_parameters = {"fcu_url": fcu_url}
    if sim_mode:
        mavros_parameters["plugin_denylist"] = [
            "param", "waypoint", "geofence", "rallypoint"
        ]

    mavros_node = Node(
        package="mavros",
        executable="mavros_node",
        output="screen",
        parameters=[mavros_parameters],
    )

    aruco_landing_node = Node(
        package="aruco_landing",
        executable="landing_node",
        name="aruco_landing_node",
        output="screen",
        parameters=[{
            "search_height": ParameterValue(
                LaunchConfiguration("search_height"), value_type=float
            )
        }],
    )

    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                PathJoinSubstitution(
                    [
                        get_package_share_directory("realsense2_camera"),
                        "launch",
                        "rs_launch.py",
                    ]
                )
            ]
        ),
        launch_arguments={
            "pointcloud.enable": "false",
            "align_depth.enable": "false",
            "enable_infra1": "false",
            "enable_infra2": "false",
            "rgb_camera.profile": "640,480,15",
        }.items(),
    )

    nodes_to_launch = []

    if sim_mode:
        nodes_to_launch.extend([mavros_node, aruco_landing_node])
    else:
        nodes_to_launch.extend([realsense_launch, mavros_node, aruco_landing_node])

    return nodes_to_launch


def generate_launch_description():
    sim_arg = DeclareLaunchArgument(
        "sim",
        default_value="false",
        description='Set to "true" to run in simulation mode.',
    )
    search_height_arg = DeclareLaunchArgument(
        "search_height",
        default_value="2.0",
        description="Takeoff and search altitude in meters.",
    )

    return LaunchDescription(
        [sim_arg, search_height_arg, OpaqueFunction(function=launch_setup)]
    )
