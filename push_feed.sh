#!/usr/bin/env bash
# Low-level ffmpeg publisher for VideoDB RTStream push URLs.
#
# Recommended: use push_stream.py, which creates the VideoDB push URL just-in-time
# and prints the RTStream ID. This script is useful only if you already have a
# push_url and need to publish media manually.
#
# Usage:
#   ./push_feed.sh <push_url> [rtsp_url|synthetic] [duration_seconds]
#
# Examples:
#   ./push_feed.sh "rtmp://host:1935/rts-..." synthetic 60
#   ./push_feed.sh "rtmp://host:1935/rts-..." "rtsp://user:pass@192.168.1.20:554/stream1" 0
set -euo pipefail

PUSH_URL="${1:?usage: push_feed.sh <push_url> [rtsp_url|synthetic] [duration]}"
SOURCE="${2:-synthetic}"
DURATION="${3:-60}"
FFMPEG_BIN="${FFMPEG_BIN:-ffmpeg}"
RTSP_TRANSPORT="${RTSP_TRANSPORT:-tcp}"

command -v "$FFMPEG_BIN" >/dev/null || {
  echo "ffmpeg not found. Install ffmpeg or set FFMPEG_BIN=/path/to/ffmpeg" >&2
  exit 1
}

DURATION_ARGS=()
if [[ "$DURATION" != "0" ]]; then
  DURATION_ARGS=(-t "$DURATION")
fi

COMMON_OUTPUT=(
  -c:v libx264 -preset veryfast -tune zerolatency -pix_fmt yuv420p -g 60
  -c:a aac -ar 44100
  "${DURATION_ARGS[@]}"
  -f flv "$PUSH_URL"
)

if [[ -z "$SOURCE" || "$SOURCE" == "synthetic" ]]; then
  echo "Publishing synthetic test pattern to VideoDB for ${DURATION}s (0 = indefinite)"
  exec "$FFMPEG_BIN" -hide_banner -loglevel error -re \
    -f lavfi -i "testsrc2=size=640x480:rate=15" \
    -f lavfi -i "sine=frequency=500" \
    "${COMMON_OUTPUT[@]}"
fi

INPUT_ARGS=()
if [[ "$SOURCE" == rtsp://* ]]; then
  INPUT_ARGS=(-rtsp_transport "$RTSP_TRANSPORT")
fi

echo "Publishing provided source to VideoDB for ${DURATION}s (0 = indefinite)"
exec "$FFMPEG_BIN" -hide_banner -loglevel error \
  "${INPUT_ARGS[@]}" -i "$SOURCE" \
  -map 0:v:0 -map 0:a:0? \
  "${COMMON_OUTPUT[@]}"
