# ERC2026 UAV Autonomous Navigation
ERC2025 UAV Navigation Package

![drone](https://github.com/user-attachments/assets/2e216aca-de09-4890-a808-00fb712153e1)

## Environment

| Item | Version / Type |
| :--- | :--- |
| Drone | PFM Zephyr |
| OS | Ubuntu 22.04 |
| ROS | ROS 2 Humble |
| Companion Computer | Raspberry Pi 4 (4GB+ recommended) |

If you have not installed the required software, please refer to the official documentation:

* **ArduPilot SITL with Gazebo:** [ardupilot.org/dev/docs/ros2-gazebo.html](https://ardupilot.org/dev/docs/ros2-gazebo.html)
* **Gazebo Harmonic:** [gazebosim.org/docs/harmonic/install](https://gazebosim.org/docs/harmonic/install)
* **MAVROS for ROS 2:** [ardupilot.org/dev/docs/ros-install.html#installing-mavros](https://ardupilot.org/dev/docs/ros-install.html#installing-mavros)

## Overview
This package enables a drone to perform autonomous missions as required by the ERC competition. Key features include:
* Autonomous takeoff and landing on a specified ArUco marker.
* Detection of up to three specified objects during a search pattern.
* Calculation and logging of object positions relative to the takeoff point.
* A unified launch system that handles both simulation and real-world flight configurations.

Object positions are estimated by projecting each detected image point through
the calibrated camera model, applying the live gimbal and vehicle TF
rotations, and intersecting the resulting ray with the takeoff ground plane.
Accurate results therefore require a valid `/camera/camera_info` message and a
correct `base_link` to camera-frame transform.

The simulation defaults also apply the Gazebo camera sensor pose
`roll=-1.57`, `pitch=-1.57`, `yaw=0`. For real hardware, set the
`camera_mount_roll`, `camera_mount_pitch`, and `camera_mount_yaw` ROS
parameters to the measured camera mounting angles in radians.

The simulation disables the upstream `CameraZoomPlugin`. That plugin changes
the rendered field of view without updating `CameraInfo`, which makes metric
image projection incorrect. The simulated camera therefore uses the fixed
D455-like horizontal field of view declared in the SDF.

The default takeoff and search altitude is `2.0` m. It can be changed without
editing the node by setting the ROS parameter `search_height`.

## 1. Setup
Clone this package into a ROS 2 workspace:

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone https://github.com/Aki0290/aruco_landing.git
```

Install the ArduPilot ROS 2 / Gazebo workspace separately by following the
official documentation linked above. The expected default location is
`~/ardu_ws`.

### Install the included simulation assets

The repository includes the tested Gazebo world, ArUco marker models (IDs 101
and 102), green probes, gimbal setup, camera configuration, and RViz settings.
After creating the standard ArduPilot workspace at `~/ardu_ws`, install them
with:

```bash
cd ~/ros2_ws/src/aruco_landing
chmod +x scripts/install_simulation_assets.sh
./scripts/install_simulation_assets.sh
```

If the ArduPilot workspace is elsewhere, specify it explicitly:

```bash
ARDU_WS=/path/to/ardu_ws ./scripts/install_simulation_assets.sh
```

The tested upstream revisions are documented in
[`simulation/README.md`](simulation/README.md).

### Build the Package
Navigate to your ROS 2 workspace and build the `aruco_landing` package.
```bash
source /opt/ros/humble/setup.bash
cd ~/ros2_ws
colcon build --packages-select aruco_landing
source ~/ros2_ws/install/setup.bash
```
*Note: The ArduPilot SITL/Gazebo environment should be built separately in its own workspace (`~/ardu_ws`) according to its documentation.*

---

#### ardupilot ROS2 with SITL in GAZEBO package
```bash
cd ~/ardu_ws
colcon build --packages-up-to ardupilot_gz_bringup
source install/setup.bash
```
---


## 2. Running in Simulation
This section explains how to test the system in a SITL (Software-In-The-Loop) environment.

> [!IMPORTANT]
> Source ROS 2 and the required workspace in every new terminal.
> ```bash
> source /opt/ros/humble/setup.bash
> source ~/ros2_ws/install/setup.bash
> source ~/ardu_ws/install/setup.bash
> ```

### Launching the Simulation
The simulation requires three separate terminals.

#### Terminal 1: Launch Gazebo Environment & SITL
This command starts the Gazebo world and the ArduPilot SITL vehicle instance.
```bash
source /opt/ros/humble/setup.bash
source ~/ardu_ws/install/setup.bash
ros2 launch ardupilot_gz_bringup iris_runway.launch.py
```

Wait until ArduPilot reports that it is ready before starting the remaining
terminals.

#### Terminal 2: Launch the MAVProxy UDP relay (Required)
This relay forwards SITL MAVLink traffic from port `14550` to MAVROS on port
`14551`. The console and map are also useful for checking `PreArm` messages.
```bash
mavproxy.py --master=udp:127.0.0.1:14550 --out=udp:127.0.0.1:14551 --console --map
```

The previous manual gimbal parameter and RC commands are applied automatically
by the simulation overlay.

#### Terminal 3: Launch Onboard Software
This single command starts both MAVROS and our custom node. The `sim:=true` argument configures MAVROS for the simulation.
```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 launch aruco_landing aruco_landing.launch.py sim:=true
```

To override the default altitude, for example:

```bash
ros2 launch aruco_landing aruco_landing.launch.py sim:=true search_height:=2.5
```

If you prefer the older name, `aruco_simulation.launch.py` is provided as an alias for the same launch setup.

---

## 3. Running on Real Hardware
This section describes how to run the system on the actual drone with a Raspberry Pi 4.

> [!CAUTION]
> The current code has been validated in SITL. Before fitting propellers,
> verify the serial device, baud rate, RealSense topics, camera-to-body frame,
> failsafe behavior, flight limits, mode changes, and arming behavior on the
> actual flight controller. Do not treat SITL validation as flight approval.

### 3.1. Onboard Computer (Raspberry Pi 4)
On the Raspberry Pi 4 connected to your flight controller, execute this single command. It will launch MAVROS (configured for a serial connection), the RealSense camera driver, and the main landing/detection node.
```bash
ros2 launch aruco_landing aruco_landing.launch.py
```
> [!NOTE]
> This command assumes the `fcu_url` inside the launch file is set to your RPi4's correct serial port and baud rate (e.g., `"/dev/ttyAMA0:921600"`).

### 3.2. Ground Control Station (Optional)
On your laptop (connected to the same network as the drone), you can use MAVProxy to monitor the drone's status.
```bash
# Replace <RPi4_IP_Address> with your Raspberry Pi's IP address
mavproxy.py --master udpin:<RPi4_IP_Address>:14550
```

---

## 4. Autostart on Boot (For Competition Use)

For competition or field deployment, the system is designed to launch all necessary software automatically when the Raspberry Pi is powered on. This creates a reliable, "headless" setup that is ready for flight without manual intervention. This is achieved using a standard Linux `systemd` service.

### 4.1. The Launch Script

First, a simple shell script is needed to source the correct ROS 2 environments and execute our main launch file.

1.  On your Raspberry Pi, create a file named `launch_drone.sh` in your home directory (`~/`).

    ```bash
    nano ~/launch_drone.sh
    ```

2.  Paste the following content into the file. This script ensures that the ROS environment is correctly sourced before running the launch command for the **real hardware configuration**.

    **File: `~/launch_drone.sh`**
    ```sh
    #!/bin/bash
    
    # Source the main ROS 2 environment
    source /opt/ros/humble/setup.bash
    
    # Source your project's workspace
    source ~/ros2_ws/install/setup.bash
    
    # Execute the main launch file. 
    # No arguments are needed, so it runs in real-flight mode by default.
    ros2 launch aruco_landing aruco_landing.launch.py
    ```

3.  Save the file and make it executable.
    ```bash
    chmod +x ~/launch_drone.sh
    ```

### 4.2. The `systemd` Service File

Next, we create a `systemd` service file that tells the operating system to run our script on boot.

1.  Create the service file using a text editor with `sudo` privileges.
    ```bash
    sudo nano /etc/systemd/system/drone.service
    ```

2.  Paste the following content. **Crucially, you must replace `<YOUR_USERNAME>` with your actual username on the Raspberry Pi (e.g., `pi`).**

    **File: `/etc/systemd/system/drone.service`**
    ```ini
    [Unit]
    Description=Drone Autostart Service for ERC2025
    # Start this service after the network is ready
    After=network.target
    
    [Service]
    # The user that the script will run as
    User=<YOUR_USERNAME>
    
    # The command to execute
    ExecStart=/home/<YOUR_USERNAME>/launch_drone.sh
    
    # Automatically restart the service if it fails
    Restart=on-failure
    
    [Install]
    # Enable this service for the default multi-user system state
    WantedBy=multi-user.target
    ```

### 4.3. Enabling and Managing the Service

Finally, enable the service to make it persistent across reboots.

1.  Reload the `systemd` manager to recognize the new service file.
    ```bash
    sudo systemctl daemon-reload
    ```

2.  Enable the service to start automatically on every boot.
    ```bash
    sudo systemctl enable drone.service
    ```

Your setup is now complete! The next time you power on the Raspberry Pi, your entire drone software stack will launch automatically.

> [!TIP]
> **How to check and debug your service:**
> These commands are essential for troubleshooting your autostart setup.
>
> ```bash
> # Check the current status of your service
> sudo systemctl status drone.service
>
> # Manually start your service without rebooting
> sudo systemctl start drone.service
>
> # Manually stop your service
> sudo systemctl stop drone.service
>
> # View the live log output of your service (very useful for debugging!)
> sudo journalctl -u drone.service -f
> ```
>
> ## 5. Adding Custom Models to the Gazebo World

The default ArduPilot Gazebo world does not contain the specific ArUco markers or probes required for the competition mission. This section explains how to create and add these custom models to the simulation environment.

While you can find many pre-made models on [Gazebo Fuel](https://app.gazebosim.org/fuel), the models for this project were created manually. For details on how Gazebo worlds are structured, see the [official documentation](https://gazebosim.org/docs/harmonic/sdf_worlds).

The two custom models we will add are:
1.  **ArUco Markers:** For takeoff (ID 101) and landing (ID 102), as per competition rules. You can generate marker images at this [ArUco Marker Generator](https://aruco-gen.netlify.app/).
2.  **Green Probes:** A lime-green cylinder for the object detection task.

### 5.1. Creating the ArUco Marker Model

This process defines a flat plane with your ArUco marker image applied as a texture.

1.  First, create the necessary directory structure and files for the ArUco marker model.

    ```bash
    # Navigate to the models directory in your ardupilot_gazebo package
    cd ~/ardu_ws/src/ardupilot_gazebo/models

    # Create the full directory path for the model and its texture
    mkdir -p aruco_tag_model101/materials/textures

    # Go into the model directory and create the config/SDF files
    cd aruco_tag_model101
    touch model.config model.sdf
    ```

2.  > [!NOTE]
    > You must generate an ArUco marker image (e.g., using the generator linked above) and save it as `aruco_101.png` inside the `~/ardu_ws/src/ardupilot_gazebo/models/aruco_tag_model101/materials/textures/` directory.

3.  Open `model.config` with a text editor and add the following content.

    ```xml
    <?xml version="1.0"?>
    <model>
      <name>Aruco Marker (ID 101)</name>
      <version>1.0</version>
      <sdf version="1.9">model.sdf</sdf>
      <author>
        <name>Your Name</name>
        <email>your@email.com</email>
      </author>
      <description>An ArUco marker with ID 101 for the ERC competition.</description>
    </model>
    ```

4.  Next, open `model.sdf` and add the following content to define the marker's appearance.

    ```xml
    <?xml version="1.0"?>
    <sdf version="1.9">
      <model name="aruco_marker_101">
        <static>true</static>
        <link name="aruco_link">
          <visual name="aruco_visual">
            <geometry>
              <plane>
                <normal>0 0 1</normal>
                <size>0.15 0.15</size>
              </plane>
            </geometry>
            <material>
              <pbr>
                <metal>
                  <albedo_map>model://aruco_tag_model101/materials/textures/aruco_101.png</albedo_map>
                </metal>
              </pbr>
            </material>
          </visual>
        </link>
      </model>
    </sdf>
    ```
    > Repeat this entire process for marker ID 102 by creating a new `aruco_tag_model102` directory and using an `aruco_102.png` image.

### 5.2. Creating the Green Probe Model

Now, create the model for the green cylindrical probe.

1.  Create the directory and files for the probe model.
    ```bash
    # Navigate back to the main models directory
    cd ~/ardu_ws/src/ardupilot_gazebo/models

    # Create the directory and files
    mkdir probes
    cd probes
    touch model.config model.sdf
    ```

2.  Open `model.config` and add the following:
    ```xml
    <?xml version="1.0"?>
    <model>
      <name>Green Probe Cylinder</name>
      <version>1.0</version>
      <sdf version="1.7">model.sdf</sdf>
      <author>
        <name>Your Name</name>
        <email>your@email.com</email>
      </author>
      <description>A simple green cylinder for object detection testing.</description>
    </model>
    ```

3.  Open `model.sdf` and add the code for the cylinder's shape and color.
    ```xml
    <?xml version="1.0"?>
    <sdf version="1.7">
      <model name="green_cylinder">
        <static>true</static>
        <link name="link">
          <collision name="collision">
            <geometry>
              <cylinder>
                <radius>0.03</radius>
                <length>0.2</length>
              </cylinder>
            </geometry>
          </collision>
          <visual name="visual">
            <geometry>
              <cylinder>
                <radius>0.03</radius>
                <length>0.2</length>
              </cylinder>
            </geometry>
            <material>
              <diffuse>0.3 0.8 0.1 1.0</diffuse>
              <ambient>0.3 0.8 0.1 1.0</ambient>
            </material>
          </visual>
        </link>
      </model>
    </sdf>
    ```

### 5.3. Placing the Models in the World

Finally, include the newly created models in your world file.

1.  Open your world file with a text editor.
    ```bash
    nano ~/ardu_ws/src/ardupilot_gz/ardupilot_gz_gazebo/worlds/iris_runway.sdf
    ```
2.  Add the following `<include>` blocks inside the main `<world>` tags to place the models. You can copy these blocks to add multiple objects, but make sure each has a unique `<name>`.

    ```xml
    <include>
      <name>takeoff_marker</name>
      <uri>model://aruco_tag_model101</uri>
      <pose>0 0 0.01 0 0 0</pose>
    </include>

    <include>
      <name>landing_marker</name>
      <uri>model://aruco_tag_model102</uri>
      <pose>5 5 0.01 0 0 0</pose>
    </include>

    <include>
      <name>green_cylinder_1</name>
      <uri>model://probes</uri>
      <pose>1.5 1.5 0.1 0 1.5708 0</pose> </include>

    <include>
      <name>green_cylinder_2</name>
      <uri>model://probes</uri>
      <pose>-1.5 1.5 0.1 0 1.5708 0</pose> </include>

    <include>
      <name>green_cylinder_3</name>
      <uri>model://probes</uri>
      <pose>0.5 2.5 0.1 0 1.5708 0</pose> </include>
    ```

After completing these steps, rebuild your ArduPilot workspace to ensure Gazebo can find the new models.
```bash
cd ~/ardu_ws
colcon build --packages-select ardupilot_gazebo
```
