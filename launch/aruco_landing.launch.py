from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

def launch_setup(context, *args, **kwargs):
    # 'sim'引数の値を取得 ('true'ならシミュレーションモード)
    sim_mode = LaunchConfiguration('sim').perform(context) == 'true'

    # --- MAVROSノードの定義 ---
    if sim_mode:
        # MAVProxy/SITL relay: listen on local 14551 and send to 14550
        fcu_url = "udp://:14551@127.0.0.1:14550"
    else:
        fcu_url = "/dev/ttyAMA0:921600" # 実機用の設定

    mavros_parameters = {'fcu_url': fcu_url}
    if sim_mode:
        # The landing node does not use the MAVROS parameter service.  Avoid
        # downloading ArduPilot's entire parameter table over the UDP relay.
        mavros_parameters['plugin_denylist'] = [
            'param', 'waypoint', 'geofence', 'rallypoint'
        ]

    mavros_node = Node(
        package='mavros',
        executable='mavros_node',
        output='screen',
        parameters=[mavros_parameters]
    )

    # --- あなたの自作ノードの定義 ---
    aruco_landing_node = Node(
        package='aruco_landing',
        executable='landing_node',
        name='aruco_landing_node',
        output='screen',
        parameters=[{
            'search_height': ParameterValue(
                LaunchConfiguration('search_height'), value_type=float
            )
        }]
    )
    
    # --- 起動するノードのリストを作成 ---
    nodes_to_launch = []
    
    if sim_mode:
        nodes_to_launch.extend([
            mavros_node,
            aruco_landing_node
        ])
    else:
        nodes_to_launch.extend([
            mavros_node,
            aruco_landing_node
        ])

    return nodes_to_launch

def generate_launch_description():
    sim_arg = DeclareLaunchArgument(
        'sim',
        default_value='false',
        description='Set to "true" to run in simulation mode.'
    )
    search_height_arg = DeclareLaunchArgument(
        'search_height',
        default_value='2.0',
        description='Takeoff and search altitude in meters.'
    )

    return LaunchDescription([
        sim_arg,
        search_height_arg,
        OpaqueFunction(function=launch_setup)
    ])
