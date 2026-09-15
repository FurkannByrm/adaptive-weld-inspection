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
    pkg_gz_sim = FindPackageShare('ros_gz_sim').perform(context)

    install_share_path = os.path.dirname(pkg_awi_desc)

    current_ign_path = os.environ.get('IGN_GAZEBO_RESOURCE_PATH', '')
    current_gz_path = os.environ.get('GZ_SIM_RESOURCE_PATH', '')

    new_ign_path = f"{current_ign_path}:{install_share_path}" if current_ign_path else install_share_path
    new_gz_path = f"{current_gz_path}:{install_share_path}" if current_gz_path else install_share_path

    os.environ['IGN_GAZEBO_RESOURCE_PATH'] = new_ign_path
    os.environ['GZ_SIM_RESOURCE_PATH'] = new_gz_path

    env_ign_resource = SetEnvironmentVariable(
        name='IGN_GAZEBO_RESOURCE_PATH',
        value=new_ign_path
    )
    env_gz_resource = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=new_gz_path
    )

    xacro_exec = FindExecutable(name='xacro').perform(context)
    xacro_file = os.path.join(pkg_awi_desc, 'urdf', 'cart_with_h2515.urdf.xacro')
    controllers_file = os.path.join(pkg_awi_desc, 'config', 'cell_controllers.yaml')

    urdf_content = subprocess.check_output([xacro_exec, xacro_file]).decode('utf-8')
    temp_urdf = tempfile.NamedTemporaryFile(mode='w', suffix='.urdf', delete=False)
    temp_urdf.write(urdf_content)
    temp_urdf.close()

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
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'
        ],
        output='screen'
    )
    # 1. Broadcaster Spawner
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '-t', 'joint_state_broadcaster/JointStateBroadcaster'],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    # 2. Slider Controller Spawner
    slider_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['slider_controller', '--param-file', controllers_file],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    # 3. Arm Controller Spawner
    arm_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['arm_controller', '--param-file', controllers_file],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    delayed_broadcaster = TimerAction(
        period=8.0,
        actions=[joint_state_broadcaster_spawner]
    )

    delayed_controllers = TimerAction(
        period=11.0,
        actions=[slider_controller_spawner, arm_controller_spawner]
    )

    return [
        env_ign_resource,
        env_gz_resource,
        node_robot_state_publisher,
        gz_sim,
        gz_spawn_entity,
        bridge,
        delayed_broadcaster,
        delayed_controllers
    ]

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        OpaqueFunction(function=launch_setup)
    ])
