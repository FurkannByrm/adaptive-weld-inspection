import os
import subprocess
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, FindExecutable
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory
import yaml

def load_yaml(package_name, file_path):
    pkg_path = get_package_share_directory(package_name)
    abs_path = os.path.join(pkg_path, file_path)
    with open(abs_path, 'r') as f:
        return yaml.safe_load(f)

def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    pkg_awi_desc = get_package_share_directory('awi_description')
    pkg_awi_moveit = get_package_share_directory('awi_moveit')

    # 1. URDF Üretimi (Simülasyon dosyanızdaki ile birebir aynı dosya)
    xacro_file = os.path.join(pkg_awi_desc, 'urdf', 'cart_with_h2515.urdf.xacro')
    robot_desc_str = subprocess.check_output(['xacro', xacro_file]).decode('utf-8')
    robot_description = {'robot_description': robot_desc_str}

    # 2. SRDF Okuma
    srdf_file = os.path.join(pkg_awi_moveit, 'config', 'h2515_on_slider.srdf')
    with open(srdf_file, 'r') as f:
        robot_description_semantic = {'robot_description_semantic': f.read()}

    # 3. YAML Konfigürasyonları
    kinematics_yaml = load_yaml('awi_moveit', 'config/kinematics.yaml')
    joint_limits_yaml = load_yaml('awi_moveit', 'config/joint_limits.yaml')
    moveit_controllers = load_yaml('awi_moveit', 'config/moveit_controllers.yaml')

    # MoveIt Trajectory Execution Parametreleri
    trajectory_execution = {
        'moveit_manage_controllers': False, # Kontrolcüleri ros2_control spawner başlattığı için False
        'trajectory_execution.allowed_execution_duration_scaling': 1.2,
        'trajectory_execution.allowed_goal_duration_margin': 0.5,
        'trajectory_execution.allowed_start_tolerance': 0.01,
    }

    planning_scene_monitor_parameters = {
        'publish_planning_scene': True,
        'publish_geometry_updates': True,
        'publish_state_updates': True,
        'publish_transforms_updates': True,
    }

    # MoveGroup Düğümü
    move_group_node = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        output='screen',
        parameters=[
            robot_description,
            robot_description_semantic,
            kinematics_yaml,
            joint_limits_yaml,
            moveit_controllers,
            trajectory_execution,
            planning_scene_monitor_parameters,
            {'use_sim_time': use_sim_time}
        ]
    )

    # MoveIt Arayüzü ile RViz2 (MotionPlanning eklentisiyle)
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2_moveit',
        output='screen',
        parameters=[
            robot_description,
            robot_description_semantic,
            kinematics_yaml,
            joint_limits_yaml,
            {'use_sim_time': use_sim_time}
        ]
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        move_group_node,
        rviz_node
    ])
