"""Save one Scout H.264/RTP camera frame using the host GStreamer bindings."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    import gi

    gi.require_version("Gst", "1.0")
    gi.require_version("GstVideo", "1.0")
    from gi.repository import Gst, GstVideo
except (ImportError, ValueError) as error:
    raise SystemExit(
        "GStreamer Python bindings are unavailable. Run this with /usr/bin/python3, "
        "not the MAVSDK virtualenv Python."
    ) from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5600)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--warmup-seconds", type=float, default=2.0)
    parser.add_argument("--output", type=Path, default=Path("scout_camera_frame.ppm"))
    args = parser.parse_args()

    Gst.init(None)
    pipeline_description = (
        f'udpsrc port={args.port} '
        'caps="application/x-rtp,media=video,clock-rate=90000,'
        'encoding-name=H264,payload=96" '
        "! rtph264depay ! avdec_h264 ! videoconvert "
        '! video/x-raw,format=RGB ! '
        "appsink name=framesink sync=false max-buffers=1 drop=true"
    )
    pipeline = Gst.parse_launch(pipeline_description)
    sink = pipeline.get_by_name("framesink")
    if sink is None:
        raise RuntimeError("GStreamer pipeline did not create its appsink")

    pipeline.set_state(Gst.State.PLAYING)
    deadline = time.monotonic() + args.timeout
    warmup_deadline = time.monotonic() + args.warmup_seconds
    try:
        while time.monotonic() < deadline:
            sample = sink.emit("try-pull-sample", 250 * Gst.MSECOND)
            # Ignore the decoder's initial concealment/startup frame. Keep
            # draining samples until the warmup period has passed, then save a
            # fresh frame from the live stream.
            if sample is not None and time.monotonic() >= warmup_deadline:
                caps = sample.get_caps()
                info = GstVideo.VideoInfo.new_from_caps(caps)
                if info is None:
                    raise RuntimeError(f"Could not read video format from caps: {caps}")
                buffer = sample.get_buffer()
                ok, mapped = buffer.map(Gst.MapFlags.READ)
                if not ok:
                    raise RuntimeError("Could not read decoded camera frame")
                try:
                    row_bytes = info.width * 3
                    stride = info.stride[0]
                    plane_offset = info.offset[0]
                    rgb = b"".join(
                        mapped.data[
                            plane_offset + row * stride :
                            plane_offset + row * stride + row_bytes
                        ]
                        for row in range(info.height)
                    )
                    expected_bytes = info.width * info.height * 3
                    if len(rgb) != expected_bytes:
                        raise RuntimeError(
                            f"Decoded RGB frame has {len(rgb)} bytes; "
                            f"expected {expected_bytes}"
                        )
                finally:
                    buffer.unmap(mapped)

                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("wb") as image:
                    image.write(f"P6\n{info.width} {info.height}\n255\n".encode("ascii"))
                    image.write(rgb)
                print(
                    f"Saved {info.width}x{info.height} RGB camera frame to "
                    f"{args.output.resolve()}"
                )
                return 0

            bus = pipeline.get_bus()
            message = bus.pop_filtered(Gst.MessageType.ERROR)
            if message is not None:
                error, debug = message.parse_error()
                raise RuntimeError(f"GStreamer error: {error}; {debug}")

        raise TimeoutError(
            f"No camera frame received on UDP port {args.port} within {args.timeout:g}s. "
            "Confirm the simulation is running and PX4 is streaming the Scout camera."
        )
    finally:
        pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Camera capture failed: {error}", file=sys.stderr)
        raise SystemExit(1)
