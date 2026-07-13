import math
import os
import threading
import time
from datetime import datetime
from enum import IntEnum

import cv2
import cv2.aruco as aruco
import cv_bridge
import numpy as np
import rclpy
from rclpy.time import Time
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, CommandTOL, SetMode
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo
from sensor_msgs.msg import Image
from tf2_ros import Buffer, TransformException, TransformListener


class MissionState(IntEnum):
    WAITING_FOR_CONNECTION = 0
    SETTING_MODE = 1
    ARMING = 2
    TAKING_OFF = 3
    SEARCHING = 4
    CENTERING = 5
    LANDING = 6
    MISSION_COMPLETE = 7


class ArucoLandingNode(Node):
    def __init__(self):
        super().__init__("aruco_landing_node")

        self.landing_marker_id = 102
        self.marker_length = 0.15
        self.declare_parameter("search_height", 2.0)
        self.search_height = float(self.get_parameter("search_height").value)
        self.centering_tolerance = 0.1

        self.mission_state = MissionState.WAITING_FOR_CONNECTION
        self.current_state = None
        self.current_pose = None
        self.takeoff_position = None
        self.last_action_time = 0.0
        self.last_wait_log_time = 0.0

        self.search_radius = 0.5
        self.max_search_radius = 3.5
        self.search_angle = 0.0
        self.search_radius_step = 0.5
        self.search_angle_step = math.radians(1)

        mavros_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self.state_sub = self.create_subscription(
            State, "/mavros/state", self.state_callback, mavros_qos
        )
        self.pose_sub = self.create_subscription(
            PoseStamped, "/mavros/local_position/pose", self.pose_callback, mavros_qos
        )
        self.declare_parameter("image_topic", "/camera/image")
        self.declare_parameter("camera_info_topic", "/camera/camera_info")
        self.image_topic = self.get_parameter("image_topic").value
        self.camera_info_topic = self.get_parameter("camera_info_topic").value
        self.image_sub = self.create_subscription(
            Image, self.image_topic, self.image_callback, mavros_qos
        )
        self.camera_info_sub = self.create_subscription(
            CameraInfo, self.camera_info_topic, self.camera_info_callback, mavros_qos
        )
        self.setpoint_pub = self.create_publisher(
            PoseStamped, "/mavros/setpoint_position/local", mavros_qos
        )
        self.arming_client = self.create_client(CommandBool, "/mavros/cmd/arming")
        self.set_mode_client = self.create_client(SetMode, "/mavros/set_mode")
        self.takeoff_client = self.create_client(CommandTOL, "/mavros/cmd/takeoff")

        self.bridge = cv_bridge.CvBridge()
        self.aruco_dict = aruco.getPredefinedDictionary(cv2.aruco.DICT_ARUCO_ORIGINAL)
        self.aruco_params = aruco.DetectorParameters_create()
        self.camera_matrix = np.array(
            [[205.46, 0.0, 320], [0.0, 205.46, 240], [0.0, 0.0, 1.0]]
        )
        self.dist_coeffs = np.zeros(5, dtype=np.float32)
        self.camera_info_received = False
        self.camera_frame = "pitch_link"
        self.declare_parameter("camera_mount_roll", -1.57)
        self.declare_parameter("camera_mount_pitch", -1.57)
        self.declare_parameter("camera_mount_yaw", 0.0)
        self.camera_mount_rpy = (
            self.get_parameter("camera_mount_roll").value,
            self.get_parameter("camera_mount_pitch").value,
            self.get_parameter("camera_mount_yaw").value,
        )
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.last_tf_warning_time = 0.0

        self.hsv_lower_green = np.array([35, 50, 50])
        self.hsv_upper_green = np.array([85, 255, 255])
        self.min_object_area = 500

        self.max_objects_to_detect = 3
        self.min_distance_between_objects = 0.5
        self.detected_objects_positions = []

        current_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.object_log_filename = f"detected_objects_{current_time_str}.txt"

        self.get_logger().info(f"Log file for this run: '{self.object_log_filename}'")

        self.detected_objects_positions = []
        self.detected_objects_camera_coords = []

        self.control_timer = self.create_timer(0.1, self.control_loop)
        self.get_logger().info(
            "Aruco Landing Node started. Waiting for MAVROS connection..."
        )

    def state_callback(self, msg):
        self.current_state = msg

    def pose_callback(self, msg):
        self.current_pose = msg

    def image_callback(self, msg):
        if self.current_pose is None or self.takeoff_position is None:
            return

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except cv_bridge.CvBridgeError as e:
            self.get_logger().error(f"CV Bridge Error: {e}")
            return

        if self.mission_state in [MissionState.SEARCHING, MissionState.CENTERING]:
            tvec, detected_id = self.detect_aruco(frame)
            if detected_id == self.landing_marker_id:
                if self.mission_state == MissionState.SEARCHING:
                    self.get_logger().info(
                        f"Landing marker {self.landing_marker_id} found! Switching to CENTERING mode."
                    )
                    self.mission_state = MissionState.CENTERING
                self.center_over_marker(tvec)

        if (
            self.mission_state >= MissionState.SEARCHING
            and len(self.detected_objects_positions) < self.max_objects_to_detect
        ):
            self.detect_and_manage_objects(frame)

    def camera_info_callback(self, msg):
        if self.camera_info_received:
            return

        self.camera_matrix = np.array(msg.k, dtype=np.float64).reshape(3, 3)

        if len(msg.d) >= 5:
            self.dist_coeffs = np.array(msg.d[:5], dtype=np.float32)
        else:
            self.dist_coeffs = np.zeros(5, dtype=np.float32)

        self.camera_info_received = True
        if msg.header.frame_id:
            self.camera_frame = msg.header.frame_id
        self.get_logger().info(
            f"Camera intrinsics loaded from {self.camera_info_topic}."
        )

    def control_loop(self):
        now = time.monotonic()

        if not self.current_state:
            if now - self.last_wait_log_time >= 5.0:
                self.get_logger().info("Waiting for /mavros/state...")
                self.last_wait_log_time = now
            return

        if self.mission_state == MissionState.WAITING_FOR_CONNECTION:
            if self.current_state.connected:
                self.get_logger().info("MAVROS Connected. Proceeding to set mode.")
                self.mission_state = MissionState.SETTING_MODE

        elif self.mission_state == MissionState.SETTING_MODE:
            if self.current_state.mode == "GUIDED":
                self.get_logger().info("Mode is now GUIDED. Proceeding to arm.")
                self.mission_state = MissionState.ARMING
                self.last_action_time = 0.0
            elif now - self.last_action_time >= 2.0:
                self.get_logger().info("Requesting GUIDED mode...")
                future = self.set_mode_client.call_async(
                    SetMode.Request(custom_mode="GUIDED")
                )
                future.add_done_callback(self.mode_response_callback)
                self.last_action_time = now

        elif self.mission_state == MissionState.ARMING:
            if self.current_state.armed:
                self.get_logger().info("Vehicle is armed. Proceeding to takeoff.")
                self.mission_state = MissionState.TAKING_OFF
                self.takeoff_position = self.current_pose
                self.last_action_time = 0.0
            elif now - self.last_action_time >= 2.0:
                self.get_logger().info("Requesting vehicle arm...")
                future = self.arming_client.call_async(
                    CommandBool.Request(value=True)
                )
                future.add_done_callback(self.arm_response_callback)
                self.last_action_time = now

        elif self.mission_state == MissionState.TAKING_OFF:
            if self.takeoff_position is None and self.current_pose is not None:
                self.takeoff_position = self.current_pose
            below_target = (
                self.current_pose is None
                or self.current_pose.pose.position.z < self.search_height - 0.3
            )
            if now - self.last_action_time >= 2.0 and below_target:
                self.get_logger().info(
                    f"Requesting takeoff to {self.search_height:.1f} m..."
                )
                future = self.takeoff_client.call_async(
                    CommandTOL.Request(
                        altitude=self.search_height,
                        latitude=float("nan"),
                        longitude=float("nan"),
                    )
                )
                future.add_done_callback(self.takeoff_response_callback)
                self.last_action_time = now
            if self.current_pose is None:
                if now - self.last_wait_log_time >= 5.0:
                    self.get_logger().warn(
                        "Takeoff requested; waiting for /mavros/local_position/pose..."
                    )
                    self.last_wait_log_time = now
            elif abs(self.current_pose.pose.position.z - self.search_height) < 0.3:
                self.get_logger().info("Takeoff complete. Switching to SEARCHING mode.")
                self.mission_state = MissionState.SEARCHING

        elif self.mission_state == MissionState.SEARCHING:
            self.execute_search_pattern()

    def mode_response_callback(self, future):
        try:
            if not future.result().mode_sent:
                self.get_logger().warn("GUIDED mode request was rejected; retrying.")
        except Exception as exc:
            self.get_logger().error(f"GUIDED mode request failed: {exc}")

    def arm_response_callback(self, future):
        try:
            if not future.result().success:
                self.get_logger().warn("Arm request was rejected; check PreArm messages.")
        except Exception as exc:
            self.get_logger().error(f"Arm request failed: {exc}")

    def takeoff_response_callback(self, future):
        try:
            if not future.result().success:
                self.get_logger().warn("Takeoff request was rejected; retrying.")
        except Exception as exc:
            self.get_logger().error(f"Takeoff request failed: {exc}")

    def detect_aruco(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.aruco_params
        )

        if ids is not None:
            self.get_logger().info(
                f"Found ArUco markers with IDs: {ids.flatten()}",
                throttle_duration_sec=1.0,
            )
            for i, marker_id in enumerate(ids):
                if marker_id[0] == self.landing_marker_id:
                    self.get_logger().info(
                        f">>> Target marker {self.landing_marker_id} FOUND! <<<"
                    )
                    rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
                        [corners[i]],
                        self.marker_length,
                        self.camera_matrix,
                        self.dist_coeffs,
                    )
                    tvec = tvecs[0][0]
                    self.get_logger().info(
                        f"    - Position from camera (tvec): x={tvec[0]:.3f}, y={tvec[1]:.3f}, z={tvec[2]:.3f}"
                    )
                    return tvec, ids[i][0]

        return None, -1

    def center_over_marker(self, tvec):
        dx, dy = tvec[0], tvec[1]
        if abs(dx) < self.centering_tolerance and abs(dy) < self.centering_tolerance:
            self.get_logger().info("Marker centered. Requesting LAND mode.")
            self.mission_state = MissionState.LANDING
            self.set_mode_client.call_async(SetMode.Request(custom_mode="LAND"))
        else:
            current_x = self.current_pose.pose.position.x
            current_y = self.current_pose.pose.position.y
            self.get_logger().info(
                f"Centering... Error(dx, dy)=({dx:+.2f}, {dy:+.2f})",
                throttle_duration_sec=1.0,
            )
            target_pose = PoseStamped()
            target_pose.header.stamp = self.get_clock().now().to_msg()
            target_pose.header.frame_id = "map"
            target_pose.pose.position.x = current_x + dx
            target_pose.pose.position.y = current_y - dy
            target_pose.pose.position.z = self.search_height
            target_pose.pose.orientation = self.current_pose.pose.orientation
            self.setpoint_pub.publish(target_pose)

    def execute_search_pattern(self):
        if not self.takeoff_position:
            return
        x = self.takeoff_position.pose.position.x + self.search_radius * math.cos(
            self.search_angle
        )
        y = self.takeoff_position.pose.position.y + self.search_radius * math.sin(
            self.search_angle
        )
        target_pose = PoseStamped()
        target_pose.header.stamp = self.get_clock().now().to_msg()
        target_pose.header.frame_id = "map"
        target_pose.pose.position.x = x
        target_pose.pose.position.y = y
        target_pose.pose.position.z = self.search_height
        target_pose.pose.orientation = self.current_pose.pose.orientation
        self.setpoint_pub.publish(target_pose)
        self.search_angle += self.search_angle_step
        if self.search_angle >= 2 * math.pi:
            self.search_angle = 0.0
            self.search_radius += self.search_radius_step
            self.get_logger().info(
                f"Increasing search radius to {self.search_radius:.2f}m"
            )
            if self.search_radius > self.max_search_radius:
                self.get_logger().warn(
                    "Max search radius reached. Landing as failsafe."
                )
                self.mission_state = MissionState.LANDING
                self.set_mode_client.call_async(SetMode.Request(custom_mode="LAND"))

    def detect_and_manage_objects(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower_green, self.hsv_upper_green)
        contours_result = cv2.findContours(
            mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )
        contours = contours_result[-2]

        valid_contours = [
            cnt for cnt in contours if cv2.contourArea(cnt) > self.min_object_area
        ]

        if not valid_contours:
            return

        new_object_found = False
        for contour in valid_contours:
            if len(self.detected_objects_positions) >= self.max_objects_to_detect:
                break

            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue
            center_u = int(M["m10"] / M["m00"])
            center_v = int(M["m01"] / M["m00"])

            result = self.transform_pixel_to_frames(
                center_u, center_v
            )
            if result is None:
                continue
            camera_coords, world_coords = result

            is_new = True
            for saved_pos in self.detected_objects_positions:
                dist = math.sqrt(
                    (world_coords[0] - saved_pos[0]) ** 2
                    + (world_coords[1] - saved_pos[1]) ** 2
                )
                if dist < self.min_distance_between_objects:
                    is_new = False
                    break

            if is_new:
                self.get_logger().info(
                    f">>> New green object DETECTED! Total: "
                    f"{len(self.detected_objects_positions) + 1}; "
                    f"estimated world position=({world_coords[0]:.3f}, "
                    f"{world_coords[1]:.3f}); pixel=({center_u}, {center_v}); "
                    f"vehicle=({self.current_pose.pose.position.x:.3f}, "
                    f"{self.current_pose.pose.position.y:.3f}, "
                    f"{self.current_pose.pose.position.z:.3f}); "
                    f"camera_xyz=({camera_coords[0]:.3f}, "
                    f"{camera_coords[1]:.3f}, {camera_coords[2]:.3f}); "
                    f"fx={self.camera_matrix[0, 0]:.2f}, "
                    f"fy={self.camera_matrix[1, 1]:.2f} <<<"
                )
                self.detected_objects_positions.append(world_coords)
                self.detected_objects_camera_coords.append(camera_coords)
                new_object_found = True

        if new_object_found:
            self.update_log_file()
            if len(self.detected_objects_positions) == self.max_objects_to_detect:
                self.get_logger().info(
                    f"Found all {self.max_objects_to_detect} objects. Stopping search."
                )

    def transform_pixel_to_frames(self, u, v):
        fx = self.camera_matrix[0, 0]
        fy = self.camera_matrix[1, 1]
        cx = self.camera_matrix[0, 2]
        cy = self.camera_matrix[1, 2]

        # Camera optical coordinates: +x right, +y down, +z forward.
        optical_ray = np.array([(u - cx) / fx, (v - cy) / fy, 1.0])

        try:
            camera_in_body = self.tf_buffer.lookup_transform(
                "base_link", self.camera_frame, Time()
            )
        except TransformException as exc:
            now = time.monotonic()
            if now - self.last_tf_warning_time >= 5.0:
                self.get_logger().warn(
                    f"Cannot transform camera frame '{self.camera_frame}' to "
                    f"base_link; object position skipped: {exc}"
                )
                self.last_tf_warning_time = now
            return None

        # Gazebo's camera sensor uses pitch_link as its frame. Convert the
        # optical convention to the link convention (+x forward, +y left,
        # +z up) before applying the dynamic gimbal transform.
        ray_camera_link = np.array(
            [optical_ray[2], -optical_ray[0], -optical_ray[1]]
        )
        ray_camera_link = self.rotate_vector_by_rpy(
            ray_camera_link, *self.camera_mount_rpy
        )

        tf_rotation = camera_in_body.transform.rotation
        ray_body = self.rotate_vector_by_quaternion(ray_camera_link, tf_rotation)

        body_rotation = self.current_pose.pose.orientation
        ray_world = self.rotate_vector_by_quaternion(ray_body, body_rotation)

        camera_offset_body = np.array(
            [
                camera_in_body.transform.translation.x,
                camera_in_body.transform.translation.y,
                camera_in_body.transform.translation.z,
            ]
        )
        camera_offset_world = self.rotate_vector_by_quaternion(
            camera_offset_body, body_rotation
        )
        camera_world = np.array(
            [
                self.current_pose.pose.position.x,
                self.current_pose.pose.position.y,
                self.current_pose.pose.position.z,
            ]
        ) + camera_offset_world

        ground_z = self.takeoff_position.pose.position.z
        if ray_world[2] >= -1e-3:
            self.get_logger().warn(
                "Camera ray does not point toward the ground; object position skipped.",
                throttle_duration_sec=5.0,
            )
            return None

        distance = (ground_z - camera_world[2]) / ray_world[2]
        if distance <= 0.0:
            return None

        object_world = camera_world + distance * ray_world
        camera_coords = tuple((distance * optical_ray).tolist())
        world_coords = (float(object_world[0]), float(object_world[1]))
        return camera_coords, world_coords

    @staticmethod
    def rotate_vector_by_quaternion(vector, quaternion):
        q = np.array(
            [quaternion.x, quaternion.y, quaternion.z, quaternion.w],
            dtype=np.float64,
        )
        norm = np.linalg.norm(q)
        if norm == 0.0:
            return np.asarray(vector, dtype=np.float64)
        q /= norm
        xyz = q[:3]
        w = q[3]
        vector = np.asarray(vector, dtype=np.float64)
        return vector + 2.0 * np.cross(xyz, np.cross(xyz, vector) + w * vector)

    @staticmethod
    def rotate_vector_by_rpy(vector, roll, pitch, yaw):
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        rotation = np.array(
            [
                [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                [-sp, cp * sr, cp * cr],
            ]
        )
        return rotation @ np.asarray(vector, dtype=np.float64)

    def update_log_file(self):
        try:
            with open(self.object_log_filename, "w") as f:
                f.write(
                    f"# Detected Objects: {len(self.detected_objects_positions)} / {self.max_objects_to_detect}\n"
                )
                f.write(
                    f"# Coordinates are in the world frame, relative to the takeoff point (meters).\n\n"
                )

                takeoff_x = self.takeoff_position.pose.position.x
                takeoff_y = self.takeoff_position.pose.position.y

                for i, pos in enumerate(self.detected_objects_positions):

                    relative_x = pos[0] - takeoff_x
                    relative_y = pos[1] - takeoff_y

                    f.write(f"[Object {i+1}]\n")
                    f.write(f"x: {relative_x:.4f}\n")
                    f.write(f"y: {relative_y:.4f}\n\n")

            self.get_logger().info(
                f"Updated object locations in '{self.object_log_filename}'."
            )
        except IOError as e:
            self.get_logger().error(f"Could not write to file: {e}")

    def get_yaw_from_pose(self, pose):
        orientation = pose.orientation
        q_x, q_y, q_z, q_w = orientation.x, orientation.y, orientation.z, orientation.w
        t3 = +2.0 * (q_w * q_z + q_x * q_y)
        t4 = +1.0 - 2.0 * (q_y * q_y + q_z * q_z)
        yaw_z = math.atan2(t3, t4)
        return yaw_z


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ArucoLandingNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node:
            node.destroy_node()
        # ROS 2 launch may already have shut the context down after SIGINT.
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
