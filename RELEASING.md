# Releasing

## Docker image artifact

A GitHub Actions workflow builds a Docker image and attaches it to each published GitHub Release.

Release asset format:

```txt
videodb-cctv-connector-<tag>-docker-image.tar.gz
videodb-cctv-connector-<tag>-docker-image.tar.gz.sha256
```

## Create a release

1. Create and push a tag:

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

2. Publish a GitHub Release for that tag.
3. The `Build release Docker image` workflow will attach the Docker image archive to the release.

## Manual rebuild for an existing release

Run the `Build release Docker image` workflow manually and provide the existing release tag.

## Loading the release image

```bash
docker load -i videodb-cctv-connector-v0.1.0-docker-image.tar.gz
docker images videodb-cctv-connector
```

## Private SDK dependency

If the SDK dependency is private, configure repository secret `VIDEODB_PYTHON_GITHUB_TOKEN` with read access to `video-db/videodb-python`.
