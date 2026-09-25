#!/usr/bin/env bash
# Generate placeholder clips (test pattern + quiet tone) so the pipeline can be
# tried without real exercise footage. Requires ffmpeg.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p videos
for id in glute_bridge cat_cow seated_knee_extension; do
  ffmpeg -y -loglevel error \
    -f lavfi -i "testsrc2=duration=15:size=1280x720:rate=30" \
    -f lavfi -i "sine=frequency=220:duration=15" \
    -filter:a "volume=0.3" -shortest \
    -c:v libx264 -pix_fmt yuv420p -c:a aac "videos/${id}.mp4"
  echo "videos/${id}.mp4"
done
