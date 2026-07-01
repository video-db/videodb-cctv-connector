# VideoDB CCTV Connector

A small on-prem connector that relays CCTV/NVR/DVR feeds **outbound** to VideoDB.

The connector has one job: run inside the customer network, read a local camera/recorder/source, create a VideoDB RTStream push destination, and publish the feed to VideoDB with ffmpeg.


```txt
camera / NVR / DVR
        ↓ local network
VideoDB CCTV Connector
        ↓ outbound HTTPS 443 + RTMP 1935
VideoDB RTStream
```

## Why use push mode?

- No public inbound access to cameras/NVRs is required.
- Camera/NVR credentials remain on the local network.
- The connector only needs outbound access to VideoDB.
- Works when cameras are on-prem or behind a firewall/VPN.

## What VideoDB provides

VideoDB will provide a `VIDEO_DB_API_KEY` for the pilot.

Set it in `.env`:

```bash
cp .env.example .env
# edit .env and set VIDEO_DB_API_KEY=...
```

## Network requirements

The machine running this connector needs:

1. Local access to the camera/NVR/DVR source, if using a live source.
2. Outbound HTTPS TCP 443 to the VideoDB API.
3. Outbound RTMP TCP 1935 to the VideoDB push endpoint returned by the API.

No inbound firewall rule to the customer site is required for push mode.

## Recommended: Docker

Prebuilt Docker image archives are attached to GitHub Releases. Local builds need temporary outbound access to PyPI/GitHub to install the VideoDB SDK dependency.

If using a prebuilt release artifact, download it from the release page and load it first:

```bash
docker load -i videodb-cctv-connector-<tag>-docker-image.tar.gz
```

Or build the connector image locally:

```bash
docker build -t videodb-cctv-connector .
```

### 1) Validate outbound connectivity with a synthetic feed

```bash
docker run --rm --env-file .env videodb-cctv-connector \
  --synthetic \
  --duration 60 \
  --name cctv-synthetic-test
```

Success looks like:

```txt
rtstream_id=rts-...
VIDEODB_RTSTREAM_ID=rts-...
DONE -- relay stopped; rtstream_id=rts-...
```

Share the `VIDEODB_RTSTREAM_ID` with VideoDB if validation is needed.

### 2) Relay a live RTSP camera/NVR channel

Set the source URL in `.env` so credentials are not visible in shell history:

```env
CAMERA_RTSP_URL=rtsp://username:password@192.168.1.20:554/stream1
VIDEODB_STREAM_NAME=site-camera-1
```

Run. The connector reads `CAMERA_RTSP_URL` and `VIDEODB_STREAM_NAME` from `.env`:

```bash
docker run --rm --env-file .env videodb-cctv-connector
```

For a time-boxed pilot run:

```bash
docker run --rm --env-file .env videodb-cctv-connector \
  --duration 300
```

For a long-running live relay, omit `--duration`; the default for live sources is indefinite until the process is stopped.

## Bare-metal alternative

Requires Python 3.11+, git, and ffmpeg.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python push_stream.py --synthetic --duration 60
```

For live RTSP, set `CAMERA_RTSP_URL` in `.env`, then run:

```bash
python push_stream.py --name site-camera-1
```

## Optional status file

To write the RTStream ID to a local JSON file:

```bash
python push_stream.py --synthetic --duration 60 --status-file ./status.json
```

Example `status.json`:

```json
{
  "rtstream_id": "rts-...",
  "name": "cctv-synthetic-test",
  "source": "synthetic",
  "push_url": "hidden"
}
```

## Source selection guidance

Most sites use one of these paths:

- IP camera reachable on LAN → use the camera RTSP URL.
- Cameras behind an NVR private/PoE network → use the NVR channel RTSP URL.
- Analog cameras/DVR → use the DVR channel stream.
- No stream access yet → start with the synthetic test to validate outbound connectivity.

For first tests, a lower-resolution substream is often best.

## Security notes

- Keep `VIDEO_DB_API_KEY` secret.
- Treat generated RTMP push URLs as secrets. The main connector hides them by default.
- Do not email camera/NVR passwords.
- Prefer storing camera URLs in `.env` or a local secret manager.
- The connector masks credentials in its own logs, but ffmpeg/vendor errors may still reveal source details in some failure cases.

## Files

- `push_stream.py` — recommended connector entrypoint.
- `push_feed.sh` — low-level ffmpeg helper if you already have a VideoDB push URL.
- `Dockerfile` — reproducible container build.
- `docker-compose.example.yml` — optional long-running service example.
- `.env.example` — environment variable template.
- `TROUBLESHOOTING.md` — common setup issues.
- `camera-inventory-template.md` — checklist for gathering local CCTV details.
- `RELEASING.md` — release/build artifact notes.
