#!/usr/bin/env bash
set -euo pipefail

runtime_dir="${RUNTIME_DIR:-/workspace/runtime}"
log_dir="$runtime_dir/logs"
mkdir -p "$log_dir"

# ArduPilot / MAVProxy create runtime files such as mav.tlog and eeprom.bin in
# the current directory. /workspace is part of the image and is not writable by
# the unprivileged ros user, so always launch them from the mounted runtime
# directory instead.
if [[ ! -w "$runtime_dir" ]]; then
  echo "Runtime directory is not writable: $runtime_dir" >&2
  echo "On the host, run: mkdir -p runtime/logs && chmod u+rwX runtime runtime/logs" >&2
  exit 1
fi
cd "$runtime_dir"

children=()

shutdown() {
  trap - INT TERM EXIT
  for pid in "${children[@]:-}"; do
    kill -INT "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap shutdown INT TERM EXIT

echo "Starting Gazebo and ArduPilot SITL..."
ros2 launch ardupilot_gz_bringup iris_runway.launch.py \
  > "$log_dir/simulation.log" 2>&1 &
children+=("$!")

echo "Waiting for SITL MAVLink output on UDP 14551..."
ready=false
for _ in $(seq 1 90); do
  if pgrep -x arducopter >/dev/null \
      && pgrep -f 'gz sim.*iris_runway' >/dev/null \
      && pgrep -f 'mavproxy.py.*14551' >/dev/null; then
    sleep 8
    if ! pgrep -f 'mavproxy.py.*14551' >/dev/null; then
      echo "MAVProxy exited during startup. Last simulation log lines:" >&2
      tail -80 "$log_dir/simulation.log" >&2
      exit 1
    fi
    ready=true
    break
  fi
  if ! kill -0 "${children[0]}" 2>/dev/null; then
    echo "Simulation launch exited early. Last log lines:" >&2
    tail -80 "$log_dir/simulation.log" >&2
    exit 1
  fi
  if grep -qE '\[ERROR\].*process has died.*mavproxy\.py' "$log_dir/simulation.log"; then
    echo "MAVProxy exited during startup. Last simulation log lines:" >&2
    tail -80 "$log_dir/simulation.log" >&2
    exit 1
  fi
  sleep 1
done

if [[ "$ready" != true ]]; then
  echo "Timed out waiting for ArduPilot SITL. Check $log_dir/simulation.log" >&2
  exit 1
fi

echo "Starting MAVROS and aruco_landing..."
ros2 launch aruco_landing aruco_landing.launch.py \
  sim:=true search_height:="${SEARCH_HEIGHT:-2.0}" \
  > "$log_dir/aruco_landing.log" 2>&1 &
children+=("$!")

echo
echo "Simulation is running."
echo "Open http://localhost:6080/vnc.html?autoconnect=true in a browser."
echo "Logs:"
echo "  $log_dir/simulation.log"
echo "  $log_dir/aruco_landing.log"

set +e
wait -n "${children[@]}"
exit_code=$?
echo "A required simulation process exited with code $exit_code." >&2
exit "$exit_code"
