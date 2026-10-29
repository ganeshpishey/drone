# Drone-Swarm 14-Day Plan and Handoff

This is the working handoff for continuing the Ubuntu PX4/Gazebo disaster-response
simulation. It combines the original Days 1–5 plan with the updated Days 6–14
roadmap. Status labels distinguish user-reported or observed work from work that
has not been verified.

## Project goal and boundaries

Build a simulation prototype using the existing project and disaster scene:

- Ubuntu, PX4 SITL, Gazebo Harmonic, MAVSDK-Python, and Python perception.
- Three simulated vehicles: Scout, Medical-Support, and Fire-Response.
- Reuse the existing discrete MAPPO environment; do not replace it or train it
  to command motors. PX4 owns low-level flight control.
- Do not introduce ROS or ROS 2.
- Do not claim automatic victim/fire detection, localization, response, or
  real-world readiness until each feature is implemented and demonstrated.
- Scope excludes real flights, HIL, real radio tests, raw-image model training,
  and full SLAM.

## Current verified state

### Completed or demonstrated

- The default simulation world is
  `worlds/earthquake_landslide_apron_world.sdf`; the user selected this apron
  environment as the project environment.
- The three PX4/Gazebo vehicles have spawned and connected in prior runs:
  Scout `x500_mono_cam_down_0`, Ambulance `x500_1`, Fire-Response `x500_2`.
- Scout completed a MAVSDK 3 m takeoff, hover, and normal landing.
- Scout also completed an 8 m vertical hover check. Telemetry showed about
  7.51–7.98 m relative altitude with near-zero horizontal velocity.
- Gazebo publishes the Scout camera image topic. PX4 also streams H.264/RTP to
  UDP 5600. A host-Python/GStreamer script saved a detailed airborne 1280×960
  RGB frame.
- Five victim model poses from the active world are recorded in
  `worlds/earthquake_landslide_apron_ground_truth.json`. This is scene ground
  truth, not camera output or detections.

### Incomplete or not verified

- `three_drone_takeoff_demo.py` lost its MAVSDK gRPC connection at the Offboard
  waypoint stage. A PX4 log reported a Hold failsafe after link loss. The cause
  is not established; the demo has not passed an end-to-end waypoint/landing
  run. Do not retry the full swarm waypoint demo yet.
- Person detection and fire/smoke detection are not implemented.
- Camera-to-world localization has not been implemented or measured.
- There is no incident coordinator, dispatch integration, or live rescue
  ground-station dashboard yet. `src/relay/viewer.py` is a replay viewer for the
  existing MAPPO work, not the drone operations dashboard.
- A prior Gazebo startup log reported missing particle color-range textures
  `materials/textures/flame_life.png` and `smoke_life.png`. Fire/smoke visuals
  should be visually checked and those resource errors fixed before claiming
  reliable effects.

## Repository map for the handoff

| Path | Purpose |
| --- | --- |
| `worlds/earthquake_landslide_apron_world.sdf` | Default user-selected Gazebo world |
| `worlds/earthquake_landslide_apron_ground_truth.json` | Five victim IDs, models, and world poses |
| `worlds/disaster_assets/` | World meshes and local victim/fire/smoke model assets |
| `integration/mavsdk_controller/launch_three_px4.sh` | Starts/stops the three PX4 SITL vehicles and Gazebo |
| `integration/mavsdk_controller/drones.json` | MAVSDK ports, roles, and local NED demo waypoint offsets |
| `integration/mavsdk_controller/controller.py` | MAVSDK controller wrapper |
| `integration/mavsdk_controller/scout_hover_check.py` | Scout-only vertical takeoff, hold, and land; no Offboard |
| `integration/mavsdk_controller/capture_scout_frame.py` | Captures one RGB frame from UDP 5600 using host GStreamer Python |
| `integration/mavsdk_controller/three_drone_takeoff_demo.py` | Experimental three-drone waypoint demo; currently blocked at Offboard |
| `src/relay/viewer.py` | Existing replay-only viewer, not the future ground station |

The launcher reads its spawn poses from its own shell variables; `spawn_pose`
fields in `drones.json` do not configure the launcher. The launcher's `stop`
subcommand terminates PX4/Gazebo processes system-wide. Check process ownership
before using it if other simulations may be running.

## Day-by-day status and work

### Day 1 — Ubuntu and development setup — Complete per project history

Set up Ubuntu, the repository, PX4 Autopilot, Gazebo Harmonic, Python, and
MAVSDK-Python. Keep PX4 outside the Drone-Swarm repository. Confirm the selected
environment and dependencies before changing them.

**Acceptance:** project and PX4 are available on Ubuntu and the simulation can
be launched from the project scripts.

### Day 2 — One PX4 SITL vehicle — Complete for basic flight

Launch an X500 in Gazebo; verify telemetry, arm, take off, hover, and land.
Scout’s 3 m MAVSDK hover and normal landing were observed in the recent check.

**Acceptance:** one vehicle completes basic flight without joystick input.

### Day 3 — MAVSDK controller — Partial

The controller wrapper and single-drone mission exist. Connection, arming,
takeoff, hover, and landing work in the Scout-only check. Offboard waypoint
control remains unverified because the gRPC stream closed during a waypoint
attempt.

**Next:** diagnose server lifetime, connection errors, PX4 failsafe logs, and
Offboard startup/setpoint handling. First retry a short waypoint with Scout
alone only after the cause is understood.

### Day 4 — Three PX4 vehicles — Partial

The launcher has started all three vehicle instances with unique PX4 instances,
MAVSDK UDP ports, and local gRPC ports. The three-drone waypoint demo has not
passed a complete mission, so independent motion and coordinated separation
must not be described as validated.

**Acceptance:** once Offboard is stable, demonstrate each vehicle independently,
then run a conservative three-drone mission with separate routes and verified
landing.

### Day 5 — Disaster world — Complete per user and project history

Use the existing apron-centered earthquake/landslide environment. Preserve the
terrain, river, debris, buildings, launch apron, and all three pads. The active
world contains five victim entities and fire/smoke visual models.

**Acceptance:** the default launcher loads this world and the three PX4 models
spawn at the intended pads.

### Day 6 — Camera and scene preparation — Complete for sensor and ground-truth setup

Scout has a downward RGB camera. Its Gazebo topic and RTP stream were observed;
Python/GStreamer saved a detailed airborne 1280×960 frame. The active SDF victim
poses are recorded in the ground-truth JSON. The 3 m hover/land behavior works.

**Still tracked separately:** the older Offboard waypoint failure. Camera
ground-truth registration and localization belong to Day 8.

**Acceptance:** usable camera frames are captured and victim scene coordinates
are available for evaluation.

### Day 7 — Detect people and visible fire — Not started

1. Build a Python consumer for the Scout image stream; support continuous frames,
   not only a single-frame capture.
2. Run a suitable pretrained person detector on a saved frame first.
3. Draw and save bounding boxes, labels, and confidence scores.
4. Evaluate person detection against visible victims in the test scene; record
   missed people and false positives.
5. Investigate fire/smoke detection separately. A person detector does not
   detect fire, and static smoke/fire visuals are not proof of a detector.

**Acceptance:** repeatable detections are visible on the annotated frame. No
model training is required for this milestone.

### Day 8 — Estimate incident locations — Not started

1. Read Scout position and attitude while the image is captured.
2. Determine camera intrinsics, camera-to-body transform, image orientation,
   and camera-to-ground geometry.
3. Project detections to the ground plane under stated terrain assumptions.
4. Compare estimates to `earthquake_landslide_apron_ground_truth.json`.
5. Record localization error and cases where rubble, slope, or occlusion breaks
   the assumptions.

**Acceptance:** detection records include approximate world coordinates and
measured error. A bounding box alone is not a world location.

### Day 9 — Incident coordinator — Not started

Implement a small, understandable Python coordinator. Maintain incident IDs,
type, coordinates, confidence, timestamp, assigned drone, and mission state.
Start with rule-based dispatch: Medical-Support for victims and Fire-Response
for fire incidents. Avoid duplicate assignments and track unavailable drones.

Do not connect MAPPO directly to motors. Keep existing MAPPO training and
checkpoints unchanged; high-level policy integration can follow stable rules.

**Acceptance:** deterministic input detections produce documented assignments
and status updates.

### Day 10 — Messages and safe mission dispatch — Not started; depends on waypoint fix

Define an incident message with ID, type, world position, confidence, time,
assigned drone, and status. Connect Scout reports to the coordinator and
coordinator assignments to MAVSDK. Test duplicate reports, missing messages,
and unavailable vehicles. Keep safe hold/land behavior and do not dispatch to
unvalidated waypoints.

**Acceptance:** one simulated report results in the intended specialist
assignment and a safely completed waypoint mission.

### Day 11 — Ground-station dashboard — Not started

Create a simple browser dashboard or extend a suitable drone-specific view.
Show vehicle position, altitude, status, incidents, confidence, assignments,
mission status, and camera/detection updates. The current `src/relay/viewer.py`
is replay-only and should not be mistaken for this dashboard.

**Acceptance:** the operator can see drones, incidents, assignments, and mission
progress in one place.

### Day 12 — End-to-end integration — Not started

Integrate camera, perception, localization, coordinator, MAVSDK dispatch, and
dashboard. Start in a controlled simulation. Verify a victim report is routed
to Medical-Support and a fire report to Fire-Response. Only claim capabilities
that were demonstrated in the run.

**Acceptance:** one complete simulated report-to-assignment-to-response flow.

### Day 13 — Scenario testing and metrics — Not started

Test one victim, one fire, simultaneous incidents, multiple victims, unavailable
drone, low-confidence detection, and message loss/delay if a network simulator
exists. Record person precision/recall, fire performance if available,
localization error, report-to-assignment time, mission completion, duplicate
assignments, and failures. Preserve logs and screenshots from each run.

**Acceptance:** repeatable scenarios and evidence-backed metrics, including
limitations and failed cases.

### Day 14 — Reproducible demonstration and documentation — Not started

Run the demonstrated workflow from startup through landing. Prepare architecture
and setup notes, commands, screenshots/video, results, and limitations. Explain
that the work is a simulation prototype, not a certified real-world disaster
response system. Do not claim medical-severity classification from ordinary RGB.

**Acceptance:** another teammate can reproduce the validated demonstration
without relying on undocumented chat history.

## Launch and camera commands

Start the default three-vehicle simulation from the repository root:

```bash
./integration/mavsdk_controller/launch_three_px4.sh
```

Run the Scout-only 8 m vertical hover check in a second terminal:

```bash
source .venv-mavsdk/bin/activate
python integration/mavsdk_controller/scout_hover_check.py \
  --altitude 8 --hover-seconds 30 \
  --telemetry-log /tmp/scout-hover-8m.jsonl
```

During the hover, close a live GStreamer viewer and capture one frame using the
host Python bindings:

```bash
/usr/bin/python3 integration/mavsdk_controller/capture_scout_frame.py \
  --output /tmp/scout_camera_frame_8m.ppm
xdg-open /tmp/scout_camera_frame_8m.ppm
```

Wait for the hover script to confirm landing before starting another flight.
Use a separate telemetry filename for every run; existing JSONL logs append
and can contain records from previous runs.

## Working rules for continuing teammates

- Read this plan, the root README, and `integration/mavsdk_controller/README.md`
  before launching or editing.
- Do not redesign or regenerate the selected disaster world for perception
  tasks. Back it up before any necessary world edit.
- Do not alter drone models, PX4 parameters, or low-level flight control to
  compensate for an unexplained failure.
- Do not rerun the three-drone waypoint demo until Offboard/gRPC is diagnosed.
- Start with one vehicle and small, explicit changes. Confirm landing after each
  flight test.
- Keep fire detection separate from person detection. Added models do not imply
  automatic detection.
- Keep generated frame images and temporary telemetry in `/tmp` unless they are
  intentionally selected as project artifacts.
- Preserve the existing discrete MAPPO research project and its checkpoints.
