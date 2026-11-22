#!/bin/bash
# Quick test runner for Didit
#
# Usage:
#   ./tests/run_tests.sh              # Run basic tests
#   ./tests/run_tests.sh --build      # Run all tests including app build
#   ./tests/run_tests.sh --generate   # Generate actual output files
#   ./tests/run_tests.sh --build --generate  # Both

echo "Running Didit tests..."
echo "=================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check for flags
TEST_ARGS=""
for arg in "$@"; do
    if [ "$arg" = "--build" ] || [ "$arg" = "--generate" ] || [ "$arg" = "-g" ]; then
        TEST_ARGS="$TEST_ARGS $arg"
    fi
done

# Run tests using venv python if available
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
else
    PYTHON="python3"
fi

"$PYTHON" "$SCRIPT_DIR/test_pngquant.py" $TEST_ARGS

echo ""
echo "All tests completed!"
