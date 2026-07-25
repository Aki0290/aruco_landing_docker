#!/usr/bin/env bash
set -eo pipefail

export DISPLAY="${DISPLAY:-:1}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export GZ_VERSION="${GZ_VERSION:-harmonic}"

source "/opt/ros/${ROS_DISTRO:-humble}/setup.bash"
source "${ARDU_WS:-/home/ros/ardu_ws}/install/setup.bash"
source "${PROJECT_WS:-/workspace/ros2_ws}/install/setup.bash"

mkdir -p /workspace/runtime/logs

if ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
  Xvfb "$DISPLAY" -screen 0 "${VNC_RESOLUTION:-1600x950x24}" \
    -ac +extension GLX +render -noreset \
    > /workspace/runtime/logs/xvfb.log 2>&1 &

  for _ in $(seq 1 50); do
    xdpyinfo -display "$DISPLAY" >/dev/null 2>&1 && break
    sleep 0.1
  done

  dbus-launch fluxbox > /workspace/runtime/logs/fluxbox.log 2>&1 &
  x11vnc -display "$DISPLAY" -forever -shared -nopw -rfbport 5901 \
    > /workspace/runtime/logs/x11vnc.log 2>&1 &
  websockify --web=/usr/share/novnc/ 6080 localhost:5901 \
    > /workspace/runtime/logs/novnc.log 2>&1 &
fi

exec "$@"
