"""Independently control three PX4 SITL vehicles through MAVSDK-Python."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from controller import PX4Controller


DEFAULT_CONFIG = Path(__file__).with_name("drones.json")
DEFAULT_LOG = Path(__file__).with_name("three_drone_telemetry.jsonl")


async def run(config_path: Path, telemetry_path: Path) -> None:
    config: dict[str, dict[str, Any]] = json.loads(config_path.read_text(encoding="utf-8"))
    for field in ("mavsdk_port", "mavsdk_server_port"):
        ports = [int(drone_config[field]) for drone_config in config.values()]
        if len(ports) != len(set(ports)):
            raise ValueError(f"Every vehicle must use a unique {field}; got {ports}")

    controllers: dict[str, PX4Controller] = {}

    for name, drone_config in config.items():
        port = int(drone_config["mavsdk_port"])
        grpc_port = int(drone_config["mavsdk_server_port"])
        controller = PX4Controller(
            f"udpin://0.0.0.0:{port}", mavsdk_server_port=grpc_port
        )
        print(
            f"Connecting {name} ({drone_config['role']}, system ID "
            f"{drone_config['system_id']}) on PX4 UDP {port}, "
            f"MAVSDK gRPC {grpc_port}..."
        )
        await controller.connect(timeout_s=45.0)
        controllers[name] = controller
        print(f"Connected to {name}.")

    async def log_snapshots(event: str) -> None:
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        with telemetry_path.open("a", encoding="utf-8") as stream:
            for name, controller in controllers.items():
                record = {
                    "event": event,
                    "vehicle": name,
                    "role": config[name]["role"],
                    "system_id": config[name]["system_id"],
                    **await controller.telemetry_snapshot(),
                }
                stream.write(json.dumps(record) + "\n")
                print(json.dumps(record, indent=2))

    try:
        print("Arming all three vehicles...")
        await asyncio.gather(*(controller.arm() for controller in controllers.values()))

        async def takeoff_one(name: str, controller: PX4Controller) -> None:
            print(f"{name}: taking off to 3 m; waiting for altitude confirmation...")
            await controller.takeoff(altitude_m=3.0)
            await controller.wait_for_relative_altitude(
                minimum_altitude_m=2.5, timeout_s=45.0
            )
            print(f"{name}: takeoff altitude confirmed.")

        await asyncio.gather(
            *(takeoff_one(name, controller) for name, controller in controllers.items())
        )
        await log_snapshots("takeoff_hover")
        print("All three reached takeoff altitude; holding position for 10 seconds.")
        await asyncio.sleep(10.0)

        print("Sending each vehicle to its own local waypoint...")

        async def goto_one(
            name: str, drone_config: dict[str, Any]
        ) -> tuple[str, str | None]:
            try:
                await controllers[name].goto_position_ned(
                    *drone_config["waypoint_ned_m"]
                )
                print(f"{name}: waypoint reached.")
                return name, None
            except Exception as error:
                message = f"{name}: waypoint failed: {error}"
                print(message)
                return name, message

        # Wait until every vehicle finishes its own waypoint attempt before the
        # finally block sends any landing command. A normal gather would raise
        # on the first failure, letting landing race the remaining controllers.
        waypoint_results = await asyncio.gather(
            *(goto_one(name, drone_config) for name, drone_config in config.items())
        )
        await log_snapshots("waypoint_results")
        failures = [message for _, message in waypoint_results if message]
        if failures:
            print("Waypoint stage finished with failures:")
            for message in failures:
                print(f"  - {message}")
        else:
            print("All three waypoint attempts succeeded; holding for 8 seconds.")
        await asyncio.gather(*(controller.hold() for controller in controllers.values()))
        await asyncio.sleep(8.0)
    finally:
        print("Requesting all vehicles to land...")

        async def land_one(name: str, controller: PX4Controller) -> None:
            try:
                await controller.land()
                await controller.wait_until_landed(timeout_s=60.0)
                print(f"{name}: PX4 telemetry confirms landed.")
            except Exception as error:  # report per vehicle and continue landing others
                print(f"{name}: landing confirmation failed: {error}")

        await asyncio.gather(
            *(land_one(name, controller) for name, controller in controllers.items())
        )
        if controllers:
            await log_snapshots("landed")
        print(f"Telemetry log: {telemetry_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--telemetry-log", type=Path, default=DEFAULT_LOG)
    args = parser.parse_args()
    asyncio.run(run(args.config, args.telemetry_log))


if __name__ == "__main__":
    main()
