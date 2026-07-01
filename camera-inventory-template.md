# Camera / recorder details to collect

Use this as a checklist with the local CCTV/system administrator. Do not send camera passwords over email.

| Field | Example | Notes |
| --- | --- | --- |
| Site / area | loading-dock | Human-readable location |
| Source type | IP camera / NVR channel / DVR channel | If cameras are behind NVR PoE ports, use the NVR channel stream |
| Vendor / model | Hikvision / Axis / Dahua / etc. | Helps find RTSP URL format |
| Local source URL | rtsp://... | Store in `.env`, not in shared docs |
| Main/sub stream | sub stream | Sub stream is usually better for pilots/lower bandwidth |
| Codec | H.264 / H.265 | Connector transcodes to H.264 for RTMP push |
| Resolution/FPS | 1280x720 @ 15fps | Lower resolution is easier for first pilot |
| Connector machine can reach source? | yes/no | Test from the same machine that runs Docker/script |
| Outbound HTTPS 443 allowed? | yes/no | Required for VideoDB API |
| Outbound RTMP TCP 1935 allowed? | yes/no | Required for push ingest |
