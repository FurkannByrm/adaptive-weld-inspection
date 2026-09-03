import os
import tempfile
import subprocess
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, TimerAction, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import FindExecutable, LaunchConfiguration, PathJoinSubstitution
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

    # Xacro'yu derle ve temiz bir geçici URDF dosyasına yaz
    temp_urdf = tempfile.NamedTemporaryFile(mode='w', suffix='.urdf', delete=False)
    urdf_content = subprocess.check_output([xacro_exec, xacro_file]).decode('utf-8')
    temp_urdf.write(urdf_content)
    temp_urdf.close()

    # Robot State Publisher
    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': urdf_content, 'use_sim_time': use_sim_time}]
    )

    # Gazebo Simülatörü
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

    # ROS-GZ Bridge (/clock simülasyon zamanı köprüsü)
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

    # 1. Joint State Broadcaster Spawner Düğümü
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'joint_state_broadcaster',
            '-t', 'joint_state_broadcaster/JointStateBroadcaster'
        ],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    # 2. Trajectory Controller Spawner Düğümü
    trajectory_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'joint_trajectory_controller',
            '-t', 'joint_trajectory_controller/JointTrajectoryController',
            '--param-file', controllers_file
        ],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    # Gazebo ve controller_manager oturduktan 4.0 saniye sonra İLK OLARAK State Broadcaster başlasın
    delayed_broadcaster = TimerAction(
        period=4.0,
        actions=[joint_state_broadcaster_spawner]
    )

    # State Broadcaster başarıyla tamamlanınca (exit olunca) Trajectory Controller yüklensin
    delay_controller_after_broadcaster = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[trajectory_controller_spawner],
        )
    )

    return [
        node_robot_state_publisher,
        gz_sim,
        gz_spawn_entity,
        bridge,
        delayed_broadcaster,
        delay_controller_after_broadcaster,
        rviz_node
    ]

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        OpaqueFunction(function=launch_setup)
    ])
