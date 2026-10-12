#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
RUN_DIR="runs/reuse-$(date -u +%Y%m%dT%H%M%SZ)-$$"
python3 -m experience_forge reuse-benchmark --seed 60701 --trials 5 --output "$RUN_DIR"
python3 -m experience_forge reuse-verify --output "$RUN_DIR"
printf 'Report: %s/report.html\n' "$RUN_DIR"
