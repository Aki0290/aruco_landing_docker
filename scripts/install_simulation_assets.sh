#!/usr/bin/env bash
set -eo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ardu_ws="${ARDU_WS:-$HOME/ardu_ws}"
force=false

if [[ "${1:-}" == "--force" ]]; then
  force=true
elif [[ $# -gt 0 ]]; then
  echo "Usage: ARDU_WS=~/ardu_ws $0 [--force]" >&2
  exit 2
fi

gz_repo="$ardu_ws/src/ardupilot_gz"
gazebo_repo="$ardu_ws/src/ardupilot_gazebo"

for repo in "$gz_repo" "$gazebo_repo"; do
  if [[ ! -d "$repo/.git" ]]; then
    echo "Required repository not found: $repo" >&2
    echo "Install the ArduPilot ROS 2 / Gazebo workspace first." >&2
    exit 1
  fi
  if [[ "$force" != true ]] && [[ -n "$(git -C "$repo" status --porcelain)" ]]; then
    echo "Refusing to overwrite a checkout with local changes: $repo" >&2
    echo "Commit/stash them, or rerun with --force after reviewing the changes." >&2
    exit 1
  fi
done

echo "Installing ardupilot_gz overlay..."
cp -a "$repo_root/simulation/overlays/ardupilot_gz/." "$gz_repo/"

echo "Installing ardupilot_gazebo overlay..."
cp -a "$repo_root/simulation/overlays/ardupilot_gazebo/config/." \
  "$gazebo_repo/config/"
cp -a "$repo_root/simulation/overlays/ardupilot_gazebo/models/aruco_tag_model101" \
  "$gazebo_repo/models/"
cp -a "$repo_root/simulation/overlays/ardupilot_gazebo/models/aruco_tag_model102" \
  "$gazebo_repo/models/"
cp -a "$repo_root/simulation/overlays/ardupilot_gazebo/models/probes" \
  "$gazebo_repo/models/"
cp "$repo_root/simulation/overlays/ardupilot_gazebo/models/gimbal_small_3d.model.sdf" \
  "$gazebo_repo/models/gimbal_small_3d/model.sdf"
cp "$repo_root/simulation/overlays/ardupilot_gazebo/models/iris_with_gimbal.model.sdf" \
  "$gazebo_repo/models/iris_with_gimbal/model.sdf"
cp "$repo_root/simulation/overlays/ardupilot_gazebo/models/iris_with_standoffs.model.sdf" \
  "$gazebo_repo/models/iris_with_standoffs/model.sdf"

chmod +x "$gz_repo/ardupilot_gz_bringup/scripts/initialize_gimbal.py"

echo "Building ArduPilot Gazebo packages..."
source /opt/ros/humble/setup.bash
cd "$ardu_ws"
colcon build --packages-up-to ardupilot_gz_bringup --packages-skip micro_ros_agent --parallel-workers 2 --cmake-args -DBUILD_TESTING=OFF

echo
echo "Simulation assets installed successfully."
echo "Run: source $ardu_ws/install/setup.bash"

