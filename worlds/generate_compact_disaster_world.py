#!/usr/bin/env python3
"""Generate a separate half-width/half-length Gazebo disaster world.

The original earthquake_landslide_world.sdf and its assets are read-only inputs.
Horizontal positions and footprints are scaled around the launch apron; vertical
coordinates, elevations, and PX4 drone spawn poses are preserved.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "earthquake_landslide_assets"
SOURCE = ROOT / "earthquake_landslide_world.sdf"
OUTPUT = ROOT / "earthquake_landslide_world_50pct.sdf"
FACTOR = 0.5
ANCHOR_X, ANCHOR_Y = -70.0, -56.0


def numbers(text: str) -> list[float]:
    return [float(value) for value in text.split()]


def scaled_size(element: ET.Element, factor: float) -> None:
    values = numbers(element.text or "")
    if len(values) >= 2:
        values[0] *= factor
        values[1] *= factor
        element.text = " ".join(f"{v:.6g}" for v in values)


def main() -> None:
    tree = ET.parse(SOURCE)
    root = tree.getroot()
    world = root.find("world")
    if world is None:
        raise SystemExit("Source SDF has no <world>")

    # Transform the heightmap's world origin while keeping vertical relief.
    terrain = world.find("model[@name='terrain']")
    if terrain is None:
        raise SystemExit("Source world has no terrain model")
    terrain_pose = ET.Element("pose")
    terrain_pose.text = (
        f"{ANCHOR_X * (1-FACTOR):.6g} {ANCHOR_Y * (1-FACTOR):.6g} 0 0 0 0"
    )
    terrain.insert(1, terrain_pose)
    for heightmap in terrain.findall(".//heightmap"):
        uri = heightmap.find("uri")
        if uri is not None:
            uri.text = "model://earthquake_landslide_assets/meshes/terrain_combined.png"
        size = heightmap.find("size")
        if size is not None:
            values = numbers(size.text or "")
            values[0] *= FACTOR
            values[1] *= FACTOR
            size.text = " ".join(f"{v:.6g}" for v in values)
        offset = heightmap.find("pos")
        if offset is not None:
            scaled_size(offset, FACTOR)
        texture_size = heightmap.find("texture/size")
        if texture_size is not None and texture_size.text:
            texture_size.text = f"{float(texture_size.text) * FACTOR:.6g}"

    launch_names = {"launch_apron", "launch_pad_1", "launch_pad_2", "launch_pad_3"}
    for model in world.findall("model"):
        name = model.get("name", "")
        if name == "terrain" or name in launch_names:
            continue

        # Root poses are global coordinates; child poses are local offsets.
        pose = model.find("pose")
        if pose is not None and pose.text:
            values = numbers(pose.text)
            values[0] = ANCHOR_X + (values[0] - ANCHOR_X) * FACTOR
            values[1] = ANCHOR_Y + (values[1] - ANCHOR_Y) * FACTOR
            pose.text = " ".join(f"{v:.6g}" for v in values)
        for local_pose in model.findall(".//pose"):
            if local_pose is pose or not local_pose.text:
                continue
            values = numbers(local_pose.text)
            if len(values) >= 2:
                values[0] *= FACTOR
                values[1] *= FACTOR
                local_pose.text = " ".join(f"{v:.6g}" for v in values)

        # Scale every visual and collision footprint horizontally. Keep heights.
        for box_size in model.findall(".//box/size"):
            scaled_size(box_size, FACTOR)
        for radius in model.findall(".//cylinder/radius") + model.findall(".//sphere/radius") + model.findall(".//cone/radius"):
            if radius.text:
                radius.text = f"{float(radius.text) * FACTOR:.6g}"
        for mesh in model.findall(".//mesh"):
            scale = mesh.find("scale")
            if scale is None:
                scale = ET.SubElement(mesh, "scale")
                scale.text = f"{FACTOR} {FACTOR} 1"
            else:
                values = numbers(scale.text or "1 1 1")
                values[0] *= FACTOR
                values[1] *= FACTOR
                scale.text = " ".join(f"{v:.6g}" for v in values)

    fog = world.find("scene/fog")
    if fog is not None:
        for key in ("start", "end"):
            item = fog.find(key)
            if item is not None and item.text:
                item.text = f"{float(item.text) * FACTOR:.6g}"

    ET.indent(tree, space="  ")
    tree.write(OUTPUT, encoding="utf-8", xml_declaration=True)
    print(f"Created {OUTPUT}")
    print("Terrain footprint: 90 x 75 m; drone spawn poses and terrain relief preserved.")


if __name__ == "__main__":
    main()
