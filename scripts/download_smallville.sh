#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/joonspk-research/generative_agents.git"
TARGET_DIR="${1:-external/stanford-smallville}"

mkdir -p "$(dirname "$TARGET_DIR")"

if [ -d "$TARGET_DIR/.git" ]; then
  echo "Smallville repository already exists at: $TARGET_DIR"
  exit 0
fi

if git clone "$REPO_URL" "$TARGET_DIR"; then
  echo "Downloaded Stanford Smallville repository to: $TARGET_DIR"
else
  echo "Failed to clone $REPO_URL"
  echo "If this environment blocks GitHub access, run this script on a network-enabled machine."
  exit 1
fi
