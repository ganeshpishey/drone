"""Fly one PX4 SITL X500 through three short local waypoints, then land.

Run only after PX4 SITL and Gazebo are ready. The waypoints are local
north/east/altitude metres relative to the PX4 home position.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from controller import PX4Controller


async def run(connection_uri: str, telemetry_path: Path) -> None:
    controller = PX4Controller(connection_uri)
    await controller.connect()
    print("Connected to PX4; waiting for position and home estimate succeeded.")

    async def log_snapshot(event: str) -> None:
        snapshot: dict[str, Any] = await controller.telemetry_snapshot()
        record = {"event": event, **snapshot}
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        with telemetry_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps(record, indent=2))

    try:
        print("Arming PX4...")
        await controller.arm()
        print("Taking off to 3 m...")
        await controller.takeoff(altitude_m=3.0)
        await asyncio.sleep(5.0)
        await log_snapshot("takeoff_hover")

        for index, (north, east, altitude) in enumerate(
            ((3.0, 0.0, 4.0), (3.0, 3.0, 4.0), (0.0, 0.0, 4.0)),
            start=1,
        ):
            print(
                f"Flying waypoint {index}/3: north={north:.1f} m, "
                f"east={east:.1f} m, altitude={altitude:.1f} m"
            )
            await controller.goto_location(north, east, altitude)
            await log_snapshot(f"waypoint_{index}")

        await controller.hold()
        await asyncio.sleep(2.0)
    finally:
        # Land on normal completion, cancellation, or waypoint/telemetry errors.
        print("Requesting land...")
        await controller.land()
        await controller.wait_until_landed()
        await log_snapshot("landed")
        print(f"Telemetry log: {telemetry_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--connection-uri",
        default="udpin://0.0.0.0:14540",
        help="MAVLink UDP endpoint used by the running PX4 SITL instance",
    )
    parser.add_argument(
        "--telemetry-log",
        type=Path,
        default=Path("integration/mavsdk_controller/telemetry.jsonl"),
        help="JSONL output file for mission telemetry",
    )
    args = parser.parse_args()
    asyncio.run(run(args.connection_uri, args.telemetry_log))


if __name__ == "__main__":
    main()
