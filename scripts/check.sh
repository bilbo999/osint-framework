#!/usr/bin/env bash
# Runs every quality gate. Must pass before each phase commit.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT/backend"
uv run ruff check .
uv run black --check .
uv run mypy
uv run pytest -q

cd "$ROOT/frontend"
npm run build
echo "All checks passed."
