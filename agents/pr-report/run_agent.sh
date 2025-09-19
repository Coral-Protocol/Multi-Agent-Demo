#!/usr/bin/env bash
set -e

fatal () {
    echo "$1" >&2
    exit 1
}

PYTHON_SCRIPT="main.py"

# Determine script directory
SCRIPT_DIR=$(dirname "$(realpath "$0" 2>/dev/null || readlink -f "$0" 2>/dev/null || echo "$0")")

PROJECT_DIR="$SCRIPT_DIR"
echo "Agent directory: $PROJECT_DIR"

# Change to project directory
cd "$PROJECT_DIR" || fatal "Could not cd to '$PROJECT_DIR'"
echo "Running $PYTHON_SCRIPT..."
uv run "$PYTHON_SCRIPT"
