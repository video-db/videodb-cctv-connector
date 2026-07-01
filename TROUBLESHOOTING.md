# Troubleshooting

## `VIDEO_DB_API_KEY is required`

Create `.env` from the template and set the key provided by VideoDB:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
VIDEO_DB_API_KEY=...
```

## `Installed videodb SDK does not support push ingest`

The installed SDK is older than the push-ingest build. Reinstall from this folder:

```bash
pip install -r requirements.txt --upgrade
```

If using Docker, rebuild the image:

```bash
docker build --no-cache -t videodb-cctv-connector .
```

## `ffmpeg not found`

Docker image includes ffmpeg. For bare-metal installs:

- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`

Or set:

```bash
export FFMPEG_BIN=/path/to/ffmpeg
```

## Synthetic test works, but RTSP source fails

Check from the same machine/container host:

1. The camera/NVR IP is reachable from the connector machine.
2. The RTSP URL is correct for that camera/recorder/channel.
3. Credentials are valid.
4. If cameras are behind NVR PoE/private ports, use the NVR channel stream rather than the camera IP.
5. Try the substream/lower-resolution URL first.

You can test ffmpeg input locally without VideoDB:

```bash
ffmpeg -rtsp_transport tcp -i "$CAMERA_RTSP_URL" -t 10 -f null -
```

## `Broken pipe`, relay exits early, or no data arrives in VideoDB

Common causes:

- Outbound RTMP TCP 1935 is blocked.
- The push endpoint idled before ffmpeg started.
- ffmpeg could not read the local source.
- The camera/NVR stream is too high resolution/bitrate for the connector machine.

Use `push_stream.py` rather than manually creating a push URL. It creates the VideoDB destination and starts ffmpeg immediately to avoid idle-time races.

For initial validation, run:

```bash
python push_stream.py --synthetic --duration 60
```

Then share the printed `VIDEODB_RTSTREAM_ID` with VideoDB.

## High CPU usage

The connector transcodes to H.264 because RTMP/FLV expects H.264 video. For pilots:

- Use the camera/NVR substream if available.
- Prefer 720p or lower initially.
- Prefer 10-15 fps for testing.
- Avoid many cameras on one small machine until sizing is confirmed.

## Logs and credentials

The connector masks credentials in its own URL prints. Some ffmpeg or camera-vendor error messages may still include source details. Review logs before forwarding them outside your organization.
