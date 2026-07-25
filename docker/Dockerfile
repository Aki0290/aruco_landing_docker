FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG ROS_DISTRO=humble
ARG ARDUPILOT_COMMIT=e0fa4a47e18beb0b19108dd02053b5e675c9bf92
ARG ARDUPILOT_GAZEBO_COMMIT=cc0290d964dfa373531963a8fc39093a0836af0a
ARG ARDUPILOT_GZ_COMMIT=8df4dc1726e37504e6fc8b952d02e554cfa3176f
ARG SITL_MODELS_COMMIT=d5d6017367a509b77886379c91207edc66f77652
ARG MICRO_ROS_AGENT_COMMIT=4f363a79ae96aed39dcc5269f53f73f6a70d3a2c
ARG MICRO_ROS_MSGS_COMMIT=100bf269e78da3fe0a58f6531ebe47d6991bd9ab
ARG ROS_GZ_COMMIT=9d7f8c721c233a9ac8b43950129d51e67905523e
ARG SDFORMAT_URDF_COMMIT=4be22a54e48562323f3e9deecbe1bde894eb7508

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    ROS_DISTRO=${ROS_DISTRO} \
    GZ_VERSION=harmonic \
    DISPLAY=:1 \
    QT_X11_NO_MITSHM=1 \
    LIBGL_ALWAYS_SOFTWARE=1 \
    MESA_GL_VERSION_OVERRIDE=3.3 \
    ROS_DOMAIN_ID=42 \
    ARDU_WS=/home/ros/ardu_ws \
    PROJECT_WS=/workspace/ros2_ws

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg2 locales lsb-release software-properties-common \
      git git-lfs sudo build-essential cmake ninja-build ccache \
      python3-pip \
      geographiclib-tools \
      xvfb fluxbox x11vnc novnc websockify xterm dbus-x11 x11-utils \
      mesa-utils libgl1-mesa-dri libglx-mesa0 \
    && locale-gen en_US.UTF-8 \
    && curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
      -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
      > /etc/apt/sources.list.d/ros2.list \
    && curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
      -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
      > /etc/apt/sources.list.d/gazebo-stable.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      ros-${ROS_DISTRO}-desktop \
      python3-rosdep python3-vcstool python3-colcon-common-extensions \
      ros-${ROS_DISTRO}-mavros ros-${ROS_DISTRO}-mavros-extras \
      ros-${ROS_DISTRO}-cv-bridge ros-${ROS_DISTRO}-tf2-ros \
      ros-${ROS_DISTRO}-image-transport ros-${ROS_DISTRO}-vision-opencv \
      gz-harmonic \
      python3-opencv python3-matplotlib python3-tk \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 --shell /bin/bash ros \
    && echo "ros ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ros \
    && chmod 0440 /etc/sudoers.d/ros

RUN rosdep init 2>/dev/null || true

RUN python3 -m pip install --no-cache-dir \
      MAVProxy==1.8.74 \
      pymavlink==2.4.49

# The EGM96 geoid dataset is required by the MAVROS UAS plugin.
RUN geographiclib-get-geoids egm96-5

RUN mkdir -p ${ARDU_WS}/src ${PROJECT_WS}/src \
    && git clone https://github.com/ArduPilot/ardupilot.git ${ARDU_WS}/src/ardupilot \
    && git -C ${ARDU_WS}/src/ardupilot checkout ${ARDUPILOT_COMMIT} \
    && git -C ${ARDU_WS}/src/ardupilot submodule update --init --recursive \
    && git clone https://github.com/ArduPilot/ardupilot_gazebo.git ${ARDU_WS}/src/ardupilot_gazebo \
    && git -C ${ARDU_WS}/src/ardupilot_gazebo checkout ${ARDUPILOT_GAZEBO_COMMIT} \
    && git clone https://github.com/ArduPilot/ardupilot_gz.git ${ARDU_WS}/src/ardupilot_gz \
    && git -C ${ARDU_WS}/src/ardupilot_gz checkout ${ARDUPILOT_GZ_COMMIT} \
    && git clone https://github.com/ArduPilot/SITL_Models.git ${ARDU_WS}/src/ardupilot_sitl_models \
    && git -C ${ARDU_WS}/src/ardupilot_sitl_models checkout ${SITL_MODELS_COMMIT} \
    && git clone https://github.com/micro-ROS/micro-ROS-Agent.git ${ARDU_WS}/src/micro_ros_agent \
    && git -C ${ARDU_WS}/src/micro_ros_agent checkout ${MICRO_ROS_AGENT_COMMIT} \
    && git clone https://github.com/micro-ROS/micro_ros_msgs.git ${ARDU_WS}/src/micro_ros_msgs \
    && git -C ${ARDU_WS}/src/micro_ros_msgs checkout ${MICRO_ROS_MSGS_COMMIT} \
    && git clone https://github.com/gazebosim/ros_gz.git ${ARDU_WS}/src/ros_gz \
    && git -C ${ARDU_WS}/src/ros_gz checkout ${ROS_GZ_COMMIT} \
    && git clone https://github.com/ros/sdformat_urdf.git ${ARDU_WS}/src/sdformat_urdf \
    && git -C ${ARDU_WS}/src/sdformat_urdf checkout ${SDFORMAT_URDF_COMMIT}

COPY docker/patches/ardupilot-dds-compat.patch /tmp/ardupilot-dds-compat.patch
RUN git -C ${ARDU_WS}/src/ardupilot apply /tmp/ardupilot-dds-compat.patch

COPY simulation/overlays/ardupilot_gz/ ${ARDU_WS}/src/ardupilot_gz/
COPY simulation/overlays/ardupilot_gazebo/config/ ${ARDU_WS}/src/ardupilot_gazebo/config/
COPY simulation/overlays/ardupilot_gazebo/models/aruco_tag_model101/ ${ARDU_WS}/src/ardupilot_gazebo/models/aruco_tag_model101/
COPY simulation/overlays/ardupilot_gazebo/models/aruco_tag_model102/ ${ARDU_WS}/src/ardupilot_gazebo/models/aruco_tag_model102/
COPY simulation/overlays/ardupilot_gazebo/models/probes/ ${ARDU_WS}/src/ardupilot_gazebo/models/probes/
COPY simulation/overlays/ardupilot_gazebo/models/gimbal_small_3d.model.sdf ${ARDU_WS}/src/ardupilot_gazebo/models/gimbal_small_3d/model.sdf
COPY simulation/overlays/ardupilot_gazebo/models/iris_with_gimbal.model.sdf ${ARDU_WS}/src/ardupilot_gazebo/models/iris_with_gimbal/model.sdf
COPY simulation/overlays/ardupilot_gazebo/models/iris_with_standoffs.model.sdf ${ARDU_WS}/src/ardupilot_gazebo/models/iris_with_standoffs/model.sdf

RUN source /opt/ros/${ROS_DISTRO}/setup.bash \
    && rosdep update \
    && apt-get update \
    && rosdep install --from-paths ${ARDU_WS}/src --ignore-src -r -y \
    && rm -rf /var/lib/apt/lists/*

# Install the remaining ArduPilot SITL build tools. The compatibility patch
# above matches the generated DDS interfaces to the pinned ROS messages.
RUN chown -R ros:ros /home/ros ${ARDU_WS} ${PROJECT_WS}

USER ros
ENV USER=ros \
    PATH=/home/ros/.local/bin:/home/ros/Micro-XRCE-DDS-Gen/scripts:${PATH}
RUN cd ${ARDU_WS}/src/ardupilot \
    && SKIP_AP_GRAPHIC_ENV=1 SKIP_AP_COV_ENV=1 \
      Tools/environment_install/install-prereqs-ubuntu.sh -y

# ArduPilot's DDS build requires the generator in addition to the runtime
# Micro-XRCE-DDS client installed by the prerequisite script.
ARG MICRO_XRCE_DDS_GEN_TAG=v4.7.1
RUN sudo apt-get update \
    && sudo apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && sudo rm -rf /var/lib/apt/lists/* \
    && git clone --recurse-submodules --depth 1 \
      --branch ${MICRO_XRCE_DDS_GEN_TAG} \
      https://github.com/ArduPilot/Micro-XRCE-DDS-Gen.git \
      /home/ros/Micro-XRCE-DDS-Gen \
    && cd /home/ros/Micro-XRCE-DDS-Gen \
    && ./gradlew assemble \
    && test -x scripts/microxrceddsgen

RUN source /opt/ros/${ROS_DISTRO}/setup.bash \
    && cd ${ARDU_WS} \
    && colcon build \
      --packages-up-to ardupilot_gz_bringup \
      --parallel-workers 2 \
      --cmake-args -DBUILD_TESTING=OFF

COPY --chown=ros:ros . ${PROJECT_WS}/src/aruco_landing
RUN source /opt/ros/${ROS_DISTRO}/setup.bash \
    && source ${ARDU_WS}/install/setup.bash \
    && cd ${PROJECT_WS} \
    && colcon build --packages-select aruco_landing --symlink-install

USER root

COPY docker/entrypoint.sh /usr/local/bin/aruco-entrypoint
COPY docker/run-simulation.sh /usr/local/bin/run-simulation
RUN chmod +x /usr/local/bin/aruco-entrypoint /usr/local/bin/run-simulation \
    && chmod +x ${ARDU_WS}/src/ardupilot_gz/ardupilot_gz_bringup/scripts/initialize_gimbal.py

USER ros
WORKDIR /workspace

EXPOSE 5901 6080

ENTRYPOINT ["/usr/local/bin/aruco-entrypoint"]
CMD ["/usr/local/bin/run-simulation"]
