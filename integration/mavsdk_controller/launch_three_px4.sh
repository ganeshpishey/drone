#!/usr/bin/env bash
set -euo pipefail

PX4_ROOT="${PX4_AUTOPILOT_DIR:-/tmp/PX4-Autopilot}"
PX4_BIN="$PX4_ROOT/build/px4_sitl_default/bin/px4"
RUN_DIR="${TMPDIR:-/tmp}/drone-swarm-px4-multi-${UID}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
WORLD_NAME="earthquake_landslide_world"
WORLD_FILE="${PX4_GZ_WORLD_FILE:-$PROJECT_ROOT/worlds/earthquake_landslide_apron_world.sdf}"
PX4_WORLDS_DIR="$PX4_ROOT/Tools/simulation/gz/worlds"
PX4_MODELS_DIR="$PX4_ROOT/Tools/simulation/gz/models"
PX4_MODEL_NAME="x500"
PX4_SCOUT_MODEL_NAME="x500_mono_cam_down"
DISASTER_WORLD_MODELS_DIR="${DISASTER_WORLD_MODELS_DIR:-${HOME}/disaster_world/models}"

if [[ "${1:-}" == "stop" ]]; then
  pkill -TERM -x px4 2>/dev/null || true
  pkill -x px4-gz_bridge 2>/dev/null || true
  pkill -TERM -x gz-sim-server 2>/dev/null || true
  pkill -TERM -x gz-sim 2>/dev/null || true
  pkill -x gz-gui 2>/dev/null || true
  pkill -TERM -f '[g]z sim' 2>/dev/null || true
  for _ in $(seq 1 5); do
    if ! pgrep -x px4 >/dev/null && ! pgrep -x px4-gz_bridge >/dev/null \
      && ! pgrep -x gz-sim-server >/dev/null && ! pgrep -x gz-sim >/dev/null \
      && ! pgrep -f '[g]z sim' >/dev/null; then
      break
    fi
    sleep 1
  done
  # Force-stop any simulator processes that ignored SIGTERM.
  pkill -KILL -x px4 2>/dev/null || true
  pkill -KILL -x px4-gz_bridge 2>/dev/null || true
  pkill -KILL -x gz-sim-server 2>/dev/null || true
  pkill -KILL -x gz-sim 2>/dev/null || true
  pkill -KILL -f '[g]z sim' 2>/dev/null || true
  if pgrep -a -x px4 || pgrep -a -x px4-gz_bridge || pgrep -a -x gz-sim-server \
    || pgrep -a -x gz-sim || pgrep -af '[g]z sim'; then
    echo "Some PX4/Gazebo processes are still running; see the PIDs above." >&2
    exit 1
  fi
  echo "Stopped PX4 SITL and Gazebo Sim processes."
  exit 0
fi

if [[ ! -x "$PX4_BIN" ]]; then
  echo "PX4 binary not found: $PX4_BIN" >&2
  echo "Set PX4_AUTOPILOT_DIR to your PX4-Autopilot checkout." >&2
  exit 1
fi

if [[ ! -f "$WORLD_FILE" ]]; then
  echo "Gazebo world not found: $WORLD_FILE" >&2
  exit 1
fi

if [[ "$(basename -- "$WORLD_FILE")" == "earthquake_landslide_apron_world.sdf" ]]; then
  for model in standing_person rescue_randy_sitting; do
    if [[ ! -f "$DISASTER_WORLD_MODELS_DIR/$model/model.sdf" ]]; then
      echo "Required local model wrapper not found: $DISASTER_WORLD_MODELS_DIR/$model/model.sdf" >&2
      echo "Set DISASTER_WORLD_MODELS_DIR to the directory containing disaster_world/models." >&2
      exit 1
    fi
  done
fi

if [[ ! -d "$PX4_WORLDS_DIR" ]]; then
  echo "PX4 Gazebo world directory not found: $PX4_WORLDS_DIR" >&2
  exit 1
fi

if [[ ! -d "$PX4_MODELS_DIR/x500" || ! -d "$PX4_MODELS_DIR/x500_base" ]]; then
  echo "PX4 X500 model files not found under: $PX4_MODELS_DIR" >&2
  exit 1
fi

if pgrep -x px4 >/dev/null; then
  echo "A PX4 SITL process is already running." >&2
  echo "Stop the existing single-drone PX4 session and Gazebo before this swarm." >&2
  exit 1
fi

if command -v gz >/dev/null 2>&1; then
  while IFS= read -r clock_topic; do
    [[ -n "$clock_topic" ]] || continue
    topic_info="$(gz topic -i -t "$clock_topic" 2>/dev/null || true)"
    # Gazebo Transport can list a clock topic with subscribers but no live
    # publisher after the server has stopped. Only a clock publisher means an
    # active world that would conflict with this launch.
    if grep -q '^Publishers ' <<<"$topic_info"; then
      existing_world="${clock_topic#/world/}"
      existing_world="${existing_world%/clock}"
      echo "Gazebo world '$existing_world' is already running." >&2
      echo "Close/stop that Gazebo server before starting $WORLD_NAME." >&2
      exit 1
    fi
  done < <(gz topic -l 2>/dev/null | grep -E '^/world/[^/]+/clock$' || true)
fi

# PX4 opens the Gazebo GUI as soon as instance 0 starts, before the other
# vehicles have joined. Preserve any pre-existing standalone GUI windows, and
# remember the PIDs of GUI windows created by this launch so they can be
# replaced after all three models are present.
GUI_PIDS_BEFORE=" $( { pgrep -f '[g]z sim -g' 2>/dev/null || true; } | tr '\n' ' ') "

# PX4's gz_env.sh resets PX4_GZ_WORLDS to the PX4 checkout's own directory.
# Stage the project-owned world there so PX4 can load it by world name.
install -m 644 "$WORLD_FILE" "$PX4_WORLDS_DIR/$WORLD_NAME.sdf"
install -d "$PX4_WORLDS_DIR/earthquake_landslide_assets"
cp -a "$PROJECT_ROOT/worlds/earthquake_landslide_assets/." \
  "$PX4_WORLDS_DIR/earthquake_landslide_assets/"
install -d "$PX4_MODELS_DIR/survivor_female" "$PX4_MODELS_DIR/survivor_male"
cp -a "$PROJECT_ROOT/worlds/disaster_assets/models/survivor_female/." \
  "$PX4_MODELS_DIR/survivor_female/"
cp -a "$PROJECT_ROOT/worlds/disaster_assets/models/survivor_male/." \
  "$PX4_MODELS_DIR/survivor_male/"
for model in standing_person_small rescue_randy_sitting_small; do
  install -d "$PX4_MODELS_DIR/$model"
  cp -a "$PROJECT_ROOT/worlds/disaster_assets/models/$model/." \
    "$PX4_MODELS_DIR/$model/"
done
for model in fire_only smoke_only; do
  install -d "$PX4_MODELS_DIR/$model"
  cp -a "$PROJECT_ROOT/worlds/disaster_assets/models/$model/." \
    "$PX4_MODELS_DIR/$model/"
done
# ParticleEmitter's color-range image path is resolved against Gazebo resource
# paths rather than the model SDF directory. Add each self-contained effect
# folder so its relative materials/textures paths resolve from any cwd.
export GZ_SIM_RESOURCE_PATH="${GZ_SIM_RESOURCE_PATH:+${GZ_SIM_RESOURCE_PATH}:}$PX4_MODELS_DIR/fire_only:$PX4_MODELS_DIR/smoke_only"
if [[ "$(basename -- "$WORLD_FILE")" == "earthquake_landslide_apron_world.sdf" ]]; then
  for model in standing_person rescue_randy_sitting; do
    source_model="$DISASTER_WORLD_MODELS_DIR/$model"
    staged_model="$PX4_MODELS_DIR/$model"
    if [[ -L "$staged_model" ]]; then
      if [[ "$(readlink -f -- "$staged_model")" != "$(readlink -f -- "$source_model")" ]]; then
        echo "Gazebo model path already links elsewhere: $staged_model" >&2
        exit 1
      fi
    elif [[ -e "$staged_model" ]]; then
      echo "Gazebo model path already exists; refusing to overwrite it: $staged_model" >&2
      exit 1
    else
      ln -s -- "$source_model" "$staged_model"
    fi
  done
fi

mkdir -p "$RUN_DIR"
pids=()
stop_started_instances() {
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  pkill -x px4-gz_bridge 2>/dev/null || true
  # A failed first PX4 launch can leave the Gazebo server it started behind.
  # The preflight check above guarantees no Gazebo world existed before this
  # launcher started, so these are the server processes owned by this run.
  pkill -x gz-sim-server 2>/dev/null || true
  pkill -x gz-sim 2>/dev/null || true
  pkill -x gz-gui 2>/dev/null || true
  pkill -f '[g]z sim' 2>/dev/null || true
}
trap stop_started_instances ERR

start_instance() {
  local instance="$1" pose="$2" role="$3" standalone="${4:-0}"
  local model_name="$PX4_MODEL_NAME"
  if [[ "$role" == "scout_0" ]]; then
    model_name="$PX4_SCOUT_MODEL_NAME"
  fi
  local instance_dir="$PX4_ROOT/build/px4_sitl_default/swarm_instance_$instance"
  local log_file="$RUN_DIR/${role}.log"
  mkdir -p "$instance_dir"
  : >"$log_file"

  if [[ "$standalone" == "1" ]]; then
    (
      cd "$instance_dir"
      exec env PX4_GZ_STANDALONE=1 PX4_GZ_NO_FOLLOW=1 PX4_GZ_WORLD="$WORLD_NAME" \
        PX4_SYS_AUTOSTART=4001 PX4_GZ_MODEL_POSE="$pose" \
        PX4_SIM_MODEL="gz_$model_name" \
        "$PX4_BIN" -i "$instance" \
        > >(stdbuf -oL tr '\r' '\n' | stdbuf -oL awk '!/pxh>/' >>"$log_file") 2>&1
    ) >"$log_file" 2>&1 &
  else
    (
      cd "$instance_dir"
      exec env PX4_GZ_WORLD="$WORLD_NAME" PX4_SYS_AUTOSTART=4001 \
        PX4_GZ_MODEL_POSE="$pose" PX4_SIM_MODEL="gz_$model_name" \
        "$PX4_BIN" -i "$instance" \
        > >(stdbuf -oL tr '\r' '\n' | stdbuf -oL awk '!/pxh>/' >>"$log_file") 2>&1
    ) >"$log_file" 2>&1 &
  fi
  local pid=$!
  pids+=("$pid")
  instance_pids+=("$pid")
  instance_roles+=("$role")
  echo "Started PX4 for $role (instance $instance, PID $pid)."
}

wait_for_instance() {
  local role="$1" pid="$2" instance="$3" model_name="$4"
  local log_file="$RUN_DIR/${role}.log"
  for _ in $(seq 1 120); do
    # PX4's readiness banner varies between builds and may never print when
    # optional GCS/power preflight checks fail. The Gazebo bridge world line
    # confirms that this PX4 instance spawned and connected its vehicle.
    if grep -q "\\[gz_bridge\\] world: $WORLD_NAME, model: ${model_name}_${instance}" "$log_file"; then
      echo "$role spawned and connected (instance $instance, system ID $((instance + 1)))."
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "$role PX4 exited; see $log_file" >&2
      grep -aE 'INFO|WARN|ERROR|Error|Failed|Gazebo|gz_bridge|Ready|Spawning|Preflight' \
        "$log_file" | tail -n 25 | cut -c1-240 >&2 || true
      return 1
    fi
    sleep 1
  done

  echo "Timed out waiting for $role; see $log_file" >&2
  grep -aE 'INFO|WARN|ERROR|Error|Failed|Gazebo|gz_bridge|Ready|Spawning|Preflight' \
    "$log_file" | tail -n 25 | cut -c1-240 >&2 || true
  return 1
}

# Instance 0 starts Gazebo. Give it a moment to create the server, then start
# both standalone PX4 instances before waiting for any one vehicle. This way a
# slow join from one PX4 instance cannot prevent the remaining drones spawning.
instance_pids=()
instance_roles=()
scout_spawn="-75,-60,1.70,0,0,0"
ambulance_spawn="-67,-60,1.70,0,0,0"
fireman_spawn="-75,-52,1.70,0,0,0"
if [[ "$(basename -- "$WORLD_FILE")" == "earthquake_landslide_apron_world.sdf" ]]; then
  # The compact world has a dedicated, obstacle-cleared launch corner.
  scout_spawn="-76,-61,1.70,0,0,0"
  ambulance_spawn="-72,-61,1.70,0,0,0"
  fireman_spawn="-76,-57,1.70,0,0,0"
fi
scout_spawn="${PX4_GZ_SCOUT_SPAWN:-$scout_spawn}"
ambulance_spawn="${PX4_GZ_AMBULANCE_SPAWN:-$ambulance_spawn}"
fireman_spawn="${PX4_GZ_FIREMAN_SPAWN:-$fireman_spawn}"
start_instance 0 "$scout_spawn" scout_0 0
sleep 5
start_instance 1 "$ambulance_spawn" ambulance_0 1
start_instance 2 "$fireman_spawn" fireman_0 1

failed_roles=()
for index in "${!instance_roles[@]}"; do
  role="${instance_roles[$index]}"
  pid="${instance_pids[$index]}"
  expected_model="$PX4_MODEL_NAME"
  if [[ "$role" == "scout_0" ]]; then
    expected_model="$PX4_SCOUT_MODEL_NAME"
  fi
  if ! wait_for_instance "$role" "$pid" "$index" "$expected_model"; then
    failed_roles+=("$role")
  fi
done

if ((${#failed_roles[@]})); then
  echo "PX4 did not confirm Gazebo connection for: ${failed_roles[*]}" >&2
  echo "Stopping this partial launch. Logs: $RUN_DIR" >&2
  stop_started_instances
  trap - ERR
  exit 1
fi

trap - ERR

# Reopen only this launch's initial GUI after all model insertions. A fresh GUI
# scene avoids the stale/empty view seen when PX4 creates its GUI before the
# standalone vehicles have joined. Focus the camera on the first drone so the
# user can immediately see the swarm's launch area.
if command -v gz >/dev/null 2>&1; then
  while read -r gui_pid; do
    [[ -n "$gui_pid" ]] || continue
    if [[ "$GUI_PIDS_BEFORE" != *" $gui_pid "* ]]; then
      kill -TERM "$gui_pid" 2>/dev/null || true
    fi
  done < <(pgrep -f '[g]z sim -g' 2>/dev/null || true)
  sleep 1
  nohup gz sim -g >"$RUN_DIR/gz_gui.log" 2>&1 </dev/null &
  gui_pid=$!
  for _ in $(seq 1 30); do
    if gz service -l 2>/dev/null | grep -qx '/gui/move_to'; then
      gz service -s /gui/move_to --reqtype gz.msgs.StringMsg \
        --reptype gz.msgs.Boolean -r "data: \"${PX4_SCOUT_MODEL_NAME}_0\"" --timeout 3000 \
        >/dev/null 2>&1 || true
      echo "Gazebo GUI refreshed after all three drones spawned (camera focused on ${PX4_SCOUT_MODEL_NAME}_0)."
      break
    fi
    if ! kill -0 "$gui_pid" 2>/dev/null; then
      echo "Gazebo GUI did not stay open; drones remain spawned in the Gazebo server." >&2
      break
    fi
    sleep 1
  done
fi

echo "Three PX4/Gazebo vehicles are running. Logs: $RUN_DIR"
echo "Gazebo world: $WORLD_FILE"
echo "Spawn poses: scout_0=$scout_spawn, ambulance_0=$ambulance_spawn, fireman_0=$fireman_spawn"
echo "MAVSDK endpoints: scout_0=14540, ambulance_0=14541, fireman_0=14542"
