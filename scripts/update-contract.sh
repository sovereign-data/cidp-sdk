#!/usr/bin/env bash
# Copy the data service's public contract (services/data/openapi-v1.json) from an ai-portal-data checkout
# (default ../ai-portal-data), then regenerate the models: make sdk-models.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${1:-${CIDP_SERVICE_REPO:-../ai-portal-data}}"
[ -f "$SRC/services/data/openapi-v1.json" ] || { echo "no ai-portal-data checkout at $SRC" >&2; exit 1; }
cp "$SRC/services/data/openapi-v1.json" contract/openapi-v1.json
echo "contract refreshed from $SRC ($(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo '?')); run: make sdk-models"
