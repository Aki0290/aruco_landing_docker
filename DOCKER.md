# Docker simulation environment (Ubuntu 22.04)

This project includes a reproducible Ubuntu 22.04, ROS 2 Humble, Gazebo
Harmonic, ArduPilot SITL environment. ArduPilot-related repositories are
pinned to tested commits and the project simulation overlays are installed
during the image build.

## Requirements

- Docker Engine 24 or newer
- Docker Compose v2 (`docker compose`)
- At least 20 GB of free disk space
- 8 GB RAM recommended

The first build downloads and compiles ArduPilot and the ROS/Gazebo workspace,
so it can take tens of minutes.

## Build and run

From the repository root:

```bash
docker compose build
docker compose up
```

The simulator, MAVROS, and `aruco_landing` start automatically. Open:

<http://localhost:6080/vnc.html?autoconnect=true>

Gazebo and RViz are rendered in the browser through noVNC, so host X11
configuration is not required.

Stop the environment with `Ctrl+C`, then:

```bash
docker compose down
```

## Options

Change the takeoff/search altitude:

```bash
SEARCH_HEIGHT=2.5 docker compose up
```

Rebuild after changing source or simulation assets:

```bash
docker compose build
docker compose up
```

Open a shell in a running container:

```bash
docker compose exec ardupilot-sim bash
```

Runtime logs are written to `runtime/logs/` on the host:

- `runtime/logs/simulation.log`
- `runtime/logs/aruco_landing.log`

## Troubleshooting

```bash
docker compose ps
docker compose logs --tail=200
```

On Apple Silicon or other ARM64 hosts, the pinned ArduPilot/Gazebo stack may
need an amd64 container. Add `platform: linux/amd64` to the service in
`compose.yaml`; emulation will be significantly slower.
