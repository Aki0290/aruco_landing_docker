# ArUco Landing Docker

Docker environment for running the ERC UAV autonomous landing simulation with
ArduPilot SITL, Gazebo Harmonic, ROS 2 Humble, MAVROS, and the
`aruco_landing` node.

The image contains the complete simulation stack, including the tested
ArduPilot sources, Gazebo world, ArUco marker models, gimbal configuration,
and ROS 2 packages. You do not need to install ROS 2, Gazebo, or ArduPilot on
the host.

## What starts automatically

`docker compose up` starts:

- Gazebo Harmonic and the custom runway world
- ArduPilot SITL
- MAVROS
- The `aruco_landing` ROS 2 node
- A virtual desktop exposed through noVNC

The simulation includes ArUco markers 101 and 102 and the custom green probe
models used by the mission.

## Requirements

- Docker Desktop, or Docker Engine 24 or newer
- Docker Compose v2 (`docker compose`)
- At least 20 GB of free disk space
- 8 GB RAM or more recommended

The first build downloads and compiles ROS 2, Gazebo, and ArduPilot
dependencies. It can take several tens of minutes depending on the machine and
network connection. Later builds reuse the Docker cache.

## Quick start

Clone the repository:

```bash
git clone https://github.com/Aki0290/aruco_landing_docker.git
cd aruco_landing_docker
```

Build the image and start the simulation in the background:

```bash
docker compose up --build -d
```

Check the container status:

```bash
docker compose ps
```

When the service is running, open the virtual desktop:

<http://localhost:6080/vnc.html?autoconnect=true>

Gazebo and RViz are rendered inside the container and displayed through the
browser. Host X11 configuration is not required.

## Start the simulation from inside the container

The normal `docker compose up --build -d` command starts the complete
simulation automatically. You do not need to enter the container or run a
second launch command.

For debugging, you can instead open a clean container shell and start the
simulation manually. First stop the automatically managed container:

```bash
docker compose down
```

Create a temporary container and enter its shell:

```bash
docker compose run --rm --service-ports ardupilot-sim bash
```

The entrypoint automatically sources the ROS 2, ArduPilot, and project
workspaces. From inside the container, start the complete stack with:

```bash
run-simulation
```

This launches Gazebo, ArduPilot SITL, MAVROS, and the `aruco_landing` node.
Keep that terminal open while the simulation is running, then open:

<http://localhost:6080/vnc.html?autoconnect=true>

Press `Ctrl+C` inside the container to stop the simulation. Because the
container was created with `--rm`, it is removed automatically when you exit:

```bash
exit
```

Do not run `run-simulation` after entering an already-running service with
`docker compose exec ardupilot-sim bash`; the normal Compose startup has
already launched those processes, and a second invocation will conflict with
them.

## View logs

Follow the Compose output:

```bash
docker compose logs -f
```

The application logs are also available on the host:

```text
runtime/logs/simulation.log
runtime/logs/aruco_landing.log
```

Follow an individual log:

```bash
tail -f runtime/logs/simulation.log
tail -f runtime/logs/aruco_landing.log
```

## Stop and restart

Stop and remove the container:

```bash
docker compose down
```

Start it again without rebuilding:

```bash
docker compose up -d
```

Rebuild after changing the source code, Dockerfile, or simulation assets:

```bash
docker compose up --build -d
```

## Configuration

The default takeoff and search altitude is 2.0 m. Override it with the
`SEARCH_HEIGHT` environment variable:

```bash
SEARCH_HEIGHT=2.5 docker compose up --build -d
```

The Compose environment also sets:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SEARCH_HEIGHT` | `2.0` | Takeoff and search altitude in metres |
| `ROS_DOMAIN_ID` | `42` | ROS 2 DDS domain |
| `VNC_RESOLUTION` | `1600x950x24` | Virtual desktop resolution |

To open a shell inside the running container:

```bash
docker compose exec ardupilot-sim bash
```

## Ports

| Host port | Service |
| --- | --- |
| `6080` | noVNC browser interface |
| `5901` | Direct VNC connection |

If either port is already in use, change the host-side number in
`compose.yaml`.

## Troubleshooting

### Container does not become healthy

Inspect its status and recent output:

```bash
docker compose ps
docker compose logs --tail=200
```

Then check the application logs under `runtime/logs/`.

### Build fails or was interrupted

Run the same command again. Docker will normally continue from its cached
layers:

```bash
docker compose up --build -d
```

To rebuild without the existing build cache:

```bash
docker compose build --no-cache
docker compose up -d
```

### Apple Silicon and other ARM64 hosts

The pinned ArduPilot and Gazebo stack may require an amd64 container. If the
native build fails, add the following line to the `ardupilot-sim` service in
`compose.yaml`:

```yaml
platform: linux/amd64
```

Running through CPU emulation is considerably slower than a native amd64
machine.

### Reset generated runtime files

Stop the container before clearing generated logs:

```bash
docker compose down
rm -rf runtime
```

The `runtime` directory is recreated automatically the next time the service
starts.

## Repository layout

```text
.
├── aruco_landing/       # ArUco detection and autonomous landing ROS 2 node
├── docker/              # Dockerfile, entrypoint, and startup scripts
├── launch/              # ROS 2 launch files
├── simulation/          # Gazebo and ArduPilot simulation overlays
├── compose.yaml         # Container build and runtime configuration
└── package.xml          # ROS 2 package metadata
```

The `aruco_landing/` directory is required. It contains the ROS 2 node that
performs marker detection, mission control, and landing; it is not a generated
Docker artifact.

## Safety

This Docker setup is intended for SITL simulation. Simulation results do not
constitute approval for real flight. Before using the software on hardware,
validate the flight-controller connection, camera calibration and transforms,
failsafes, flight limits, mode changes, and arming behaviour without
propellers.

## License

See [LICENSE](LICENSE).
