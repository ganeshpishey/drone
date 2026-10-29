#!/usr/bin/env python3
"""Create a separate compact, fully aligned copy of the disaster world.

All environmental geometry and poses receive the same uniform 0.5 transform
about the existing launch apron. The apron and three launch pads stay full-size
and in place so PX4 spawn poses remain valid. The source world and its assets
are never modified.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "earthquake_landslide_world.sdf"
OUTPUT = ROOT / "earthquake_landslide_box_world.sdf"
FACTOR = 0.5
ANCHOR = (-70.0, -56.0, 1.56)
KEEP_FULL_SIZE = {"launch_apron", "launch_pad_1", "launch_pad_2", "launch_pad_3"}


def values(element: ET.Element) -> list[float]:
    return [float(value) for value in (element.text or "").split()]


def write_values(element: ET.Element, sequence: list[float]) -> None:
    element.text = " ".join(f"{value:.9g}" for value in sequence)


def scale_pose(pose: ET.Element, *, world_pose: bool) -> None:
    numbers = values(pose)
    if len(numbers) < 3:
        raise ValueError(f"Expected at least xyz in SDF pose: {pose.text!r}")
    for axis in range(3):
        anchor = ANCHOR[axis] if world_pose else 0.0
        numbers[axis] = anchor + (numbers[axis] - anchor) * FACTOR
    write_values(pose, numbers)


def scale_vector(element: ET.Element, axes: int = 3) -> None:
    numbers = values(element)
    for axis in range(min(axes, len(numbers))):
        numbers[axis] *= FACTOR
    write_values(element, numbers)


def scale_scalar(element: ET.Element) -> None:
    if element.text and element.text.strip():
        element.text = f"{float(element.text) * FACTOR:.9g}"


def scale_model_geometry(model: ET.Element) -> None:
    for size in model.findall(".//box/size"):
        scale_vector(size)
    for size in model.findall(".//plane/size"):
        scale_vector(size, axes=2)
    for mesh in model.findall(".//mesh"):
        scale = mesh.find("scale")
        if scale is None:
            scale = ET.SubElement(mesh, "scale")
            scale.text = "1 1 1"
        scale_vector(scale)
    for element in model.findall(".//ellipsoid/radii"):
        scale_vector(element)
    for geometry_type in ("cylinder", "sphere", "cone", "capsule"):
        for geometry in model.findall(f".//{geometry_type}"):
            for tag in ("radius", "length"):
                element = geometry.find(tag)
                if element is not None:
                    scale_scalar(element)
    for heightmap in model.findall(".//heightmap"):
        size = heightmap.find("size")
        if size is not None:
            scale_vector(size)
        position = heightmap.find("pos")
        if position is not None:
            scale_vector(position)


def main() -> None:
    tree = ET.parse(SOURCE)
    root = tree.getroot()
    world = root.find("world")
    if world is None or world.find("model[@name='terrain']") is None:
        raise SystemExit("Source SDF must contain a world and its terrain model")

    output_world = copy.deepcopy(world)
    output_world.set("name", "earthquake_landslide_world")

    for model in output_world.findall("model"):
        name = model.get("name", "")
        if name in KEEP_FULL_SIZE:
            continue

        pose = model.find("pose")
        if pose is None:
            pose = ET.Element("pose")
            static = model.find("static")
            model.insert(list(model).index(static) if static is not None else 0, pose)
            pose.text = "0 0 0 0 0 0"
        scale_pose(pose, world_pose=True)

        # Child/link/visual/collision poses and every geometry dimension use
        # the same scale, preserving each object's internal alignment.
        for local_pose in model.findall(".//pose"):
            if local_pose is not pose:
                scale_pose(local_pose, world_pose=False)
        scale_model_geometry(model)

    fog = output_world.find("scene/fog")
    if fog is not None:
        for distance in ("start", "end"):
            element = fog.find(distance)
            if element is not None:
                scale_scalar(element)

    root.clear()
    root.set("version", "1.9")
    root.append(output_world)
    ET.indent(tree, space="  ")
    tree.write(OUTPUT, encoding="utf-8", xml_declaration=True)
    print(f"Created {OUTPUT}")
    print("Terrain: 90 x 75 m; vertical relief and environmental geometry: 50% scale.")
    print("Launch apron, launch pads, PX4 spawn coordinates, and source assets are unchanged.")


if __name__ == "__main__":
    main()
