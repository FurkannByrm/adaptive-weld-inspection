import os
import tempfile
import subprocess
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, 
    IncludeLaunchDescription, 
    OpaqueFunction, 
    TimerAction, 
    SetEnvironmentVariable
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import FindExecutable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def launch_setup(context, *args, **kwargs):
    use_sim_time = LaunchConfiguration('use_sim_time', default=True)

    pkg_awi_desc = FindPackageShare('awi_description').perform(context)
    pkg_dsr_desc = FindPackageShare('dsr_description2').perform(context)
    pkg_gz_sim = FindPackageShare('ros_gz_sim').perform(context)

    xacro_exec = FindExecutable(name='xacro').perform(context)
    xacro_file = os.path.join(pkg_awi_desc, 'urdf', 'cart_with_h2515.urdf.xacro')
    controllers_file = os.path.join(pkg_awi_desc, 'config', 'cell_controllers.yaml')

    temp_urdf = tempfile.NamedTemporaryFile(mode='w', suffix='.urdf', delete=False)
    urdf_content = subprocess.check_output([xacro_exec, xacro_file]).decode('utf-8')
    temp_urdf.write(urdf_content)
    temp_urdf.close()

    env_ament = setenvironmentvariable(
        name='ament_prefix_path', 
        value=os.environ.get('ament_prefix_path', '')
    )
    env_ld = setenvironmentvariable(
        name='ld_library_path', 
        value=os.environ.get('ld_library_path', '')
    )

    # Robot State Publisher
    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': urdf_content, 'use_sim_time': use_sim_time}]
    )

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments=[('gz_args', ' -r -v 1 empty.sdf')]
    )

    # Gazebo Entity Spawner
    gz_spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=['-file', temp_urdf.name, '-name', 'awi_cell', '-allow_renaming', 'true']
    )

    # ROS-GZ Bridge (/clock)
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen'
    )

    # RViz2
    rviz_config = os.path.join(pkg_dsr_desc, 'rviz', 'default.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '-t', 'joint_state_broadcaster/JointStateBroadcaster'],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    trajectory_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_trajectory_controller', '--param-file', controllers_file],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    delayed_broadcaster = TimerAction(
        period=8.0,
        actions=[joint_state_broadcaster_spawner]
    )

    delayed_trajectory_controller = TimerAction(
        period=12.0,
        actions=[trajectory_controller_spawner]
    )

    return [
        env_ament,
        env_ld,
        node_robot_state_publisher,
        gz_sim,
        gz_spawn_entity,
        bridge,
        delayed_broadcaster,
        delayed_trajectory_controller,
        rviz_node
    ]

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        OpaqueFunction(function=launch_setup)
    ])
