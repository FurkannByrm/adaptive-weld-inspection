import os
import subprocess
import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def load_yaml(package_name, file_path):
    pkg_path = get_package_share_directory(package_name)
    abs_path = os.path.join(pkg_path, file_path)
    with open(abs_path, 'r') as f:
        return yaml.safe_load(f)


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    pkg_awi_desc = get_package_share_directory('awi_description')
    pkg_awi_moveit = get_package_share_directory('awi_moveit')

    xacro_file = os.path.join(pkg_awi_desc, 'urdf', 'cart_with_h2515.urdf.xacro')
    robot_desc_str = subprocess.check_output(['xacro', xacro_file]).decode('utf-8')
    robot_description = {'robot_description': robot_desc_str}

    srdf_file = os.path.join(pkg_awi_moveit, 'config', 'h2515_on_slider.srdf')
    with open(srdf_file, 'r') as f:
        robot_description_semantic = {'robot_description_semantic': f.read()}

    kinematics_yaml = load_yaml('awi_moveit', 'config/kinematics.yaml')
    joint_limits_yaml = load_yaml('awi_moveit', 'config/joint_limits.yaml')
    moveit_controllers = load_yaml('awi_moveit', 'config/moveit_controllers.yaml')
    ompl_planning_yaml = load_yaml('awi_moveit', 'config/ompl_planning.yaml')

    sim_time_param = {'use_sim_time': True}

    trajectory_execution = {
        'moveit_manage_controllers': False,
        'trajectory_execution.allowed_execution_duration_scaling': 2.0,
        'trajectory_execution.allowed_goal_duration_margin': 1.5,
        'trajectory_execution.allowed_start_tolerance': 0.0,  # 0.0 başlangıç çiftlemesini engeller
        'trajectory_execution.execution_duration_monitoring': False,
        'trajectory_execution.wait_for_trajectory_completion': True,
    }
    planning_scene_monitor_parameters = {
        'publish_planning_scene': True,
        'publish_geometry_updates': True,
        'publish_state_updates': True,
        'publish_transforms_updates': True,
    }

    move_group_node = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        output='screen',
        parameters=[
            {'use_sim_time': True},
            robot_description,
            robot_description_semantic,
            kinematics_yaml,
            joint_limits_yaml,
            moveit_controllers,
            ompl_planning_yaml,
            trajectory_execution,
            planning_scene_monitor_parameters,
        ]
    )

    rviz_config_file = os.path.join(pkg_awi_moveit, 'config', 'moveit.rviz')
    rviz_args = []
    if os.path.exists(rviz_config_file):
        rviz_args = ['-d', rviz_config_file]

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2_moveit',
        output='screen',
        arguments=rviz_args,
        parameters=[
            {'use_sim_time': True},
            robot_description,
            robot_description_semantic,
            kinematics_yaml,
            joint_limits_yaml,
        ]
    )
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        move_group_node,
        rviz_node
    ])
