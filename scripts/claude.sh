#!/bin/bash
# Launch Claude Code in this project with .env loaded for MCP servers.
# Usage: ./scripts/claude.sh [claude args...]

set -euo pipefail

ENV_FILE="$(dirname "$(readlink -f "$0")")/../.env"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
else
  echo "Warning: $ENV_FILE not found — MCP servers may fail to authenticate" >&2
fi

exec claude "$@"
