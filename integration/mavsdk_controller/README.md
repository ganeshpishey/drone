# Day 3: MAVSDK-Python controller

> **Current handoff status (29 Oct 2026):** the Scout-only vertical
> `scout_hover_check.py` takeoff/hover/land check passed at 3 m, and an 8 m
> hover produced telemetry and a useful airborne camera frame. The
> three-vehicle launcher has also spawned and connected all three SITL
> vehicles. However, `three_drone_takeoff_demo.py` lost its MAVSDK gRPC stream
> during Offboard waypoint control, and a PX4 log reported a Hold failsafe
> after link loss. The cause is unknown. Do not run the waypoint demos as the
> next step; diagnose the disconnect and validate one Scout waypoint first.
> The current status and 14-day continuation plan are in
> [`../../docs/DRONE_SWARM_14_DAY_PLAN.md`](../../docs/DRONE_SWARM_14_DAY_PLAN.md).

This module is the first Python-to-PX4 control adapter. It uses MAVSDK-Python's
asyncio API and leaves the existing MAPPO environment and checkpoints intact.
The controller owns flight-level actions; PX4 remains responsible for low-level
attitude and motor control.

## Install

The main Drone-Swarm package requires Python 3.11.9 or newer. The current
Ubuntu session has Python 3.10, so you can run this standalone integration in a
separate Python 3.10 venv without installing or changing the MAPPO package:

```bash
cd Drone-Swarm
python3 -m venv .venv-mavsdk
source .venv-mavsdk/bin/activate
python -m pip install --upgrade pip
python -m pip install 'mavsdk-grpc>=3.17,<4'
```

For a Python 3.11.9+ environment, install the optional project extra instead:
`python -m pip install -e '.[px4]'`. The extra installs `mavsdk-grpc`, the
established MAVSDK-Python asyncio client package, separately from the project's
normal dependencies.

## Run

Start PX4 SITL and Gazebo first. For a safe vertical-only check, keep the PX4
session open and run the Scout-only script from a second terminal:

```bash
cd "/home/ganesh/Drone Swarm/Drone-Swarm"
source .venv-mavsdk/bin/activate
python integration/mavsdk_controller/scout_hover_check.py \
  --altitude 3 --hover-seconds 10 \
  --telemetry-log /tmp/scout-hover-check.jsonl
```

This check does not test horizontal movement or Offboard waypoint control. The
older `single_drone_mission.py` and `three_drone_takeoff_demo.py` waypoint
examples are experimental; do not treat their presence as evidence that
waypoint flight has passed. See the status notice above before attempting them.

The default UDP listener is `udpin://0.0.0.0:14540`, matching the PX4 SITL
MAVSDK endpoint. Override it with `--connection-uri` if the SITL configuration
uses another port.

## Coordinate convention

`PX4Controller.goto_location(x, y, z)` accepts metres relative to PX4 home:
`x` is north, `y` is east, and `z` is altitude above home. It converts these
local offsets to the WGS84 latitude/longitude and AMSL altitude required by
MAVSDK's `goto_location` action. The waypoint call waits for telemetry to show
arrival before the mission advances.

The script is for SITL only. Do not point it at a physical vehicle.

## Day 4: three PX4 vehicles

The starter swarm configuration is in `drones.json`. It assigns PX4 instances
0, 1, and 2 to Scout, Medical-Support, and Fire-Response, giving them system
IDs 1, 2, and 3 and MAVSDK UDP ports 14540, 14541, and 14542. Their Gazebo
spawn points are separated by 6 m. Each Python MAVSDK controller also uses a
distinct local gRPC server port (50051, 50052, and 50053); sharing the default
gRPC port would route the controllers through the same MAVSDK server.

Close the existing single-PX4 SITL and Gazebo sessions first. From the
Drone-Swarm root, launch the three PX4 instances:

```bash
cd "/home/ganesh/Drone Swarm/Drone-Swarm"
./integration/mavsdk_controller/launch_three_px4.sh
```

The script uses `/tmp/PX4-Autopilot` by default. Set `PX4_AUTOPILOT_DIR` if
your checkout is elsewhere. Instance 0 starts Gazebo; instances 1 and 2 join
its world. Startup logs are written under `/tmp/drone-swarm-px4-multi-<uid>/`.
The launcher refuses to start if a PX4 process is already running, to avoid
overlapping it with the single-drone session.

The three-vehicle launcher and connection have been observed to work, but the
multi-vehicle waypoint mission is currently blocked by the Offboard/gRPC
disconnect described above. Do not run the following demo until that issue has
been diagnosed and a Scout-only waypoint test has passed:

```bash
cd "/home/ganesh/Drone Swarm/Drone-Swarm"
source .venv-mavsdk/bin/activate
python integration/mavsdk_controller/three_drone_takeoff_demo.py
```

The demo connects to each configured UDP port, arms and takes off all three
vehicles, waits for each to reach takeoff altitude, then sends each to its own
nearby waypoint using local NED offboard position setpoints. It requests
landing after the waypoint run. It logs telemetry to
`three_drone_telemetry.jsonl` and waits for PX4 to report each vehicle is no
longer airborne before confirming landing.

The launcher uses PX4's stock `x500_mono_cam_down` model for Scout and stock
`x500` models for Ambulance and Fireman. The Scout variant includes PX4's
unchanged `x500` model plus its downward-facing `mono_cam` camera; the other
two vehicles keep the original model. No PX4 parameters, airframe, motors,
propellers, or flight-control code are changed. Gazebo names the vehicles
`x500_mono_cam_down_0`, `x500_1`, and `x500_2`.

The Scout camera is expected to publish a Gazebo RGB image topic under
`/world/earthquake_landslide_world/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image`.
PX4's Gazebo server configuration also discovers camera sensors and streams
RGB frames as H.264/RTP to UDP port 5600. Gazebo Transport Python bindings and
OpenCV are not present in the project's MAVSDK virtual environment. The host
system has PyGObject/GStreamer, which a Python camera consumer can use to read
the RTP stream; this camera setup does not add victim detection. To capture one
decoded RGB frame without ROS, stop any existing `gst-launch-1.0` viewer first
(only one UDP receiver should read port 5600), then run:

```bash
cd "/home/ganesh/Drone Swarm/Drone-Swarm"
/usr/bin/python3 integration/mavsdk_controller/capture_scout_frame.py \
  --output /tmp/scout_camera_frame.ppm
xdg-open /tmp/scout_camera_frame.ppm
```

Run this while the simulation and Scout camera stream are active. The capture
utility uses the host Python GStreamer bindings, not the MAVSDK virtualenv.

To inspect more terrain with the downward-facing Scout camera without testing
horizontal Offboard control, the Scout-only hover check accepts a vertical
takeoff height. For example, use `--altitude 8 --hover-seconds 30`, capture the
camera frame during the hover, and confirm it lands before trying waypoint
flight again.

## Combined earthquake and landslide world

`worlds/earthquake_landslide_world.sdf` targets Gazebo Harmonic / Gazebo Sim
8.15.0 and SDF 1.9. The world retains its original 180 x 150 m terrain footprint and layout.
Mesh assets under
`worlds/earthquake_landslide_assets/` provide the collapsed apartment, village
houses, bridge, rubble, and irregular boulders. Their original geometry is split
by existing MTL material groups, then assigned explicit SDF colors so the
materials do not depend on Gazebo importing the OBJ MTL appearance. Building
and bridge collisions, poses, terrain texture, stream segments, and object
placement remain as in the original scene. The valley, landslide slope, debris,
cracked roads, forested slopes, fog, static dust/smoke cues, incident markers,
and flattened 20 x 18 m launch apron with three pads are retained.
There are no drones in the SDF. Fire and victim objects are visual/collision
markers rather than sensor detections; smoke and dust are static visual cues,
not animated particles or simulated fluid/heat. The SDF world relies on the
PX4 launcher for its normal Gazebo systems.

Reapply the material fix without regenerating terrain or moving any objects:

```bash
cd "/home/ganesh/Drone Swarm/Drone-Swarm"
python3 worlds/generate_earthquake_landslide.py
```

The material repair script needs Python 3 and Pillow (`python -m pip install Pillow`);
afterward, the SDF and mesh assets run without Python or ROS.

Launch three external PX4 X500 drones; the script stages the SDF and its local
asset model into PX4's Gazebo world directory and starts at the three corner
pads:

```bash
./integration/mavsdk_controller/launch_three_px4.sh
```

### Apron-centered launcher default

The PX4 launcher defaults to `worlds/earthquake_landslide_apron_world.sdf`,
the apron-centered scene shown above. It keeps the 20 x 18 m launch apron and
three pads full-size, with the surrounding terrain and environment scaled to
an 18 x 15 m footprint. To use the original 180 x 150 m world instead, set
`PX4_GZ_WORLD_FILE="$PWD/worlds/earthquake_landslide_world.sdf"` when launching.

### Half-size operational-area variant

`worlds/earthquake_landslide_world_50pct.sdf` is a separate compact variant
with a 90 x 75 m terrain footprint. Landscape and obstacle footprints are
scaled horizontally around the existing launch apron; terrain elevation and
PX4's three launch coordinates remain unchanged. It references the original
heightmap without modifying it, and the original world is not overwritten.
Recreate and validate it:

```bash
python3 worlds/generate_compact_disaster_world.py
gz sdf -k worlds/earthquake_landslide_world_50pct.sdf
```

To launch the three PX4 drones in this version, stop any existing simulation
first, then set the world's source file for the normal launcher:

```bash
./integration/mavsdk_controller/launch_three_px4.sh stop
PX4_GZ_WORLD_FILE="$PWD/worlds/earthquake_landslide_world_50pct.sdf" \
  ./integration/mavsdk_controller/launch_three_px4.sh
```

For a visual-only preview, add the project's `worlds` folder to Gazebo's
resource search path and run:

```bash
source /tmp/PX4-Autopilot/build/px4_sitl_default/gz_env.sh
export GZ_SIM_RESOURCE_PATH="$PWD/worlds:$GZ_SIM_RESOURCE_PATH"
gz sim -r worlds/earthquake_landslide_world.sdf
```

### Compact box-sized disaster world

`worlds/earthquake_landslide_box_world.sdf` is a separate compact variant of
the same disaster layout. Its terrain is 90 x 75 m with half-height relief;
buildings, rubble, roads, vegetation, water features, and their collisions are
uniformly scaled to half size so they remain aligned. The launch apron and
three pads retain their original dimensions and locations, so the PX4 spawn
poses and drone models are unchanged. The original environment and assets are
not modified.

Regenerate and validate the compact world:

```bash
python3 worlds/generate_box_sized_disaster_world.py
gz sdf -k worlds/earthquake_landslide_box_world.sdf
```

Launch the three PX4 vehicles in it:

```bash
./integration/mavsdk_controller/launch_three_px4.sh stop
PX4_GZ_WORLD_FILE="$PWD/worlds/earthquake_landslide_box_world.sdf" \
  ./integration/mavsdk_controller/launch_three_px4.sh
```

Create repeatable isolated variants with an explicit integer seed. The script
writes the chosen SDF and a JSON manifest; incident marker positions are
deterministically varied. Earthquake-only terrain removes landslide debris;
landslide-only terrain retains intact settlement shells and removes the
earthquake fissures. The combined SDF remains the default:

```bash
python3 worlds/generate_earthquake_landslide.py --mode earthquake --seed 7
PX4_GZ_WORLD_FILE="$PWD/worlds/earthquake_seed_7.sdf" ./integration/mavsdk_controller/launch_three_px4.sh

python3 worlds/generate_earthquake_landslide.py --mode landslide --seed 7
PX4_GZ_WORLD_FILE="$PWD/worlds/landslide_seed_7.sdf" ./integration/mavsdk_controller/launch_three_px4.sh
```

Validate the default world and generated variants with:

```bash
gz sdf -k worlds/earthquake_landslide_world.sdf
python3 worlds/generate_earthquake_landslide.py --mode earthquake --seed 7
gz sdf -k worlds/earthquake_seed_7.sdf
python3 worlds/generate_earthquake_landslide.py --mode landslide --seed 7
gz sdf -k worlds/landslide_seed_7.sdf
```

For operation, maintain terrain clearance and route around ridges, treetops,
building faces, boulders, and bridge cables/deck. Static collision shapes let
Gazebo's physics report contacts; the planner still needs a map or onboard
range/vision sensing to detect obstacles before contact. Water and smoke are
visual-only, and the X500 model's available sensors depend on the PX4 model
configuration. The old compact `worlds/earthquake_world.sdf` remains available
as a separate reference scene.

## Earlier compact earthquake world

`worlds/earthquake_world.sdf` is a self-contained SDF 1.9 world for Gazebo
Harmonic. It has a 70 m square ground area and a 14 m clear launch apron in the
southwest corner. The three marked pads are spaced 6 m apart. Compact road
corridors, damaged multi-storey shells with exposed beams and fallen roof slabs,
grouped concrete/brick rubble, road cracks and barriers, three abandoned
vehicles, a 5 m canal and a segmented damaged bridge make up the rescue area.
The scene follows the supplied reference composition, with an exposed-frame
collapsed tower, a diagonal cracked street, rubble on the road shoulders, six
inspection pads, victim cues and fire/smoke visual cues. The world contains no
drone models. Its earlier PX4 pad coordinates were (-31,-31), (-25,-31), and
(-31,-25) metres. Ground truth coordinates are in
`worlds/incident_manifest.yaml`.

This is a primitive-geometry SDF approximation of the reference. It does not
provide photorealistic building textures, animated smoke, or physically
simulated fire.

Fire and smoke are static visual markers, not simulated heat, fluid, or
particle effects. All environment collision geometry uses simple boxes,
cylinders or spheres; visual-only road markings, water and incident cues do not
create collision surfaces. There are no external model assets or ROS
dependencies. The PX4 launcher supplies its normal Gazebo system plugins.

This compact legacy world can still be previewed without PX4:

```bash
cd "/home/ganesh/Drone Swarm/Drone-Swarm"
source /tmp/PX4-Autopilot/build/px4_sitl_default/gz_env.sh
export GZ_SIM_RESOURCE_PATH="$PWD/worlds:$GZ_SIM_RESOURCE_PATH"
gz sim -r worlds/earthquake_world.sdf
```

The PX4 launcher uses the apron-centered disaster scene by default; this
compact legacy world is not selected by that launcher.

The scene provides multiple approach routes but has no autonomy or collision
avoidance controller built into SDF. Keep the initial flight within the clear
launch apron, then use conservative speed/altitude limits and route around the
bridge piers, buildings, and road obstacles. Visual target markers are not
sensor detections; those are implemented in a later milestone.
