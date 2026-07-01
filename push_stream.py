#!/usr/bin/env python3
"""VideoDB CCTV Connector: relay local camera/NVR/DVR feeds to VideoDB.

This connector does one job: create a VideoDB RTStream push destination and relay
an on-prem CCTV source into it with ffmpeg. Video analysis/indexing/alerts are
handled by VideoDB after the stream is connected; this process only acts as the
network bridge from the local CCTV environment to VideoDB.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
import videodb


HERE = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "https://api.videodb.io"


def redact_url(value: str | None) -> str:
    """Mask credentials in a URL before printing it."""
    if not value:
        return ""
    try:
        parts = urlsplit(value)
        if not parts.scheme or not parts.netloc:
            return value
        if parts.username or parts.password:
            host = parts.hostname or ""
            if parts.port:
                host = f"{host}:{parts.port}"
            return urlunsplit((parts.scheme, f"***:***@{host}", parts.path, parts.query, parts.fragment))
        return value
    except Exception:
        return "<redacted>"


def positive_duration(value: str) -> int:
    duration = int(value)
    if duration < 0:
        raise argparse.ArgumentTypeError("duration must be >= 0; use 0 for indefinite")
    return duration


def choose_duration(args: argparse.Namespace) -> int:
    """Choose safe defaults: short tests for synthetic, indefinite for live."""
    if args.duration is not None:
        return args.duration
    if args.synthetic:
        return 60
    return 0


def build_ffmpeg_command(args: argparse.Namespace, push_url: str, duration: int) -> list[str]:
    ffmpeg = args.ffmpeg_bin
    loglevel = args.ffmpeg_loglevel

    if args.synthetic:
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            loglevel,
            "-re",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={args.synthetic_size}:rate={args.synthetic_rate}",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=500",
            "-c:v",
            "libx264",
            "-preset",
            args.x264_preset,
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-g",
            str(args.gop),
            "-c:a",
            "aac",
            "-ar",
            "44100",
        ]
    else:
        source = args.source_url
        if not source:
            raise ValueError("one of --synthetic or --source-url is required")

        input_opts: list[str] = []
        if source.lower().startswith("rtsp://"):
            input_opts.extend(["-rtsp_transport", args.rtsp_transport])

        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            loglevel,
            *input_opts,
            "-i",
            source,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            args.x264_preset,
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-g",
            str(args.gop),
            "-c:a",
            "aac",
            "-ar",
            "44100",
        ]

    if duration > 0:
        cmd.extend(["-t", str(duration)])
    cmd.extend(["-f", "flv", push_url])
    return cmd


def print_source(args: argparse.Namespace, duration: int) -> None:
    if args.synthetic:
        source = f"synthetic test pattern ({args.synthetic_size}@{args.synthetic_rate}fps)"
    else:
        source = redact_url(args.source_url)

    duration_text = "indefinitely" if duration == 0 else f"for {duration}s"
    print(f"    source={source}")
    print(f"    duration={duration_text}")


def terminate_process(process: subprocess.Popen[str], timeout: int = 10) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def write_status_file(path: str, payload: dict) -> None:
    status_path = Path(path).expanduser()
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(payload, indent=2) + "\n")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Relay an on-prem CCTV source to VideoDB RTStream")

    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--synthetic", action="store_true", help="push a generated test pattern")
    source.add_argument(
        "--source-url",
        default=os.environ.get("CAMERA_SOURCE_URL") or os.environ.get("CAMERA_RTSP_URL"),
        help="camera/NVR/DVR source URL, typically rtsp://... (can also use CAMERA_SOURCE_URL env)",
    )

    parser.add_argument("--name", default=os.environ.get("VIDEODB_STREAM_NAME", "cctv-camera"))
    parser.add_argument("--duration", type=positive_duration, help="seconds to relay; 0 means indefinite")
    parser.add_argument("--api-key", default=os.environ.get("VIDEO_DB_API_KEY"), help="prefer VIDEO_DB_API_KEY env")
    parser.add_argument("--base-url", default=os.environ.get("VIDEODB_BASE_URL", DEFAULT_BASE_URL), help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=int, default=180, help="seconds to wait for VideoDB push endpoint")
    parser.add_argument("--store", action="store_true", help="ask VideoDB to store the stream recording, if enabled")
    parser.add_argument(
        "--keep-rtstream",
        action="store_true",
        help="do not stop the RTStream on connector exit (default: cleanup on exit)",
    )
    parser.add_argument("--status-file", help="write stream connection details to a local JSON file")
    parser.add_argument(
        "--print-push-url",
        action="store_true",
        help="print the generated RTMP push URL in logs (treat it as a secret)",
    )

    parser.add_argument("--ffmpeg-bin", default=os.environ.get("FFMPEG_BIN", "ffmpeg"))
    parser.add_argument("--ffmpeg-loglevel", default="error")
    parser.add_argument("--rtsp-transport", default="tcp", choices=["tcp", "udp"])
    parser.add_argument("--x264-preset", default="veryfast")
    parser.add_argument("--gop", type=int, default=60)
    parser.add_argument("--synthetic-size", default="640x480")
    parser.add_argument("--synthetic-rate", type=int, default=15)

    args = parser.parse_args(argv)

    if not (args.synthetic or args.source_url):
        parser.error("one of --synthetic or --source-url is required")
    if not args.api_key:
        parser.error("VIDEO_DB_API_KEY is required; set it in .env or the environment")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    # Load .env from the current working directory first, then next to this script.
    load_dotenv(Path.cwd() / ".env")
    load_dotenv(HERE / ".env", override=False)

    args = parse_args(argv or sys.argv[1:])
    duration = choose_duration(args)

    print("[1] Connect to VideoDB")
    conn = videodb.connect(api_key=args.api_key, base_url=args.base_url)
    coll = conn.get_collection()

    print("[2] Create RTStream push destination")
    try:
        rtstream = coll.connect_rtstream(
            name=args.name,
            ingest_mode="push",
            protocol="rtmp",
            timeout=args.timeout,
            store=args.store or None,
        )
    except TypeError as exc:
        raise RuntimeError(
            "Installed videodb SDK does not support push ingest. Install the push-capable SDK version."
        ) from exc

    print(f"    rtstream_id={rtstream.id}")
    if args.print_push_url:
        print(f"    push_url={rtstream.push_url}")
    else:
        print("    push_url=<hidden; use --print-push-url only for debugging>")

    status_payload = {
        "rtstream_id": rtstream.id,
        "name": args.name,
        "source": "synthetic" if args.synthetic else redact_url(args.source_url),
        "push_url": rtstream.push_url if args.print_push_url else "hidden",
    }
    if args.status_file:
        write_status_file(args.status_file, status_payload)
        print(f"    status_file={args.status_file}")

    print("[3] Start relay")
    print_source(args, duration)
    ffmpeg_cmd = build_ffmpeg_command(args, rtstream.push_url, duration)
    relay = subprocess.Popen(ffmpeg_cmd)

    stop_requested = False

    def _handle_signal(signum, _frame):
        nonlocal stop_requested
        print(f"\nReceived signal {signum}; stopping relay...")
        stop_requested = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    print("[4] Relay running")
    print(f"    VIDEODB_RTSTREAM_ID={rtstream.id}")
    print("    Share this RTStream ID with VideoDB if support/validation is needed.")
    try:
        while not stop_requested:
            return_code = relay.poll()
            if return_code is not None:
                print(f"    ffmpeg exited with code {return_code}")
                if return_code != 0:
                    return return_code
                break
            time.sleep(1)
    finally:
        print("[5] Cleanup")
        terminate_process(relay)
        if not args.keep_rtstream:
            try:
                rtstream.stop()
            except Exception as exc:  # best-effort cleanup
                print(f"    warning: could not stop RTStream: {exc}")

    print(f"DONE -- relay stopped; rtstream_id={rtstream.id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
