#!/bin/bash
# Test script for syft-flwr project
# Usage: ./test.sh [unit|integration|all]

TEST_TYPE="${1:-unit}"  # Default to unit tests

echo "Running tests for syft-flwr..."

# Track overall test status
ALL_TESTS_PASSED=true

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[1;36m'
NC='\033[0m'

# Function to setup environment
setup_env() {
    # Get the root directory (parent of scripts)
    ROOT_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"
    cd "$ROOT_DIR" || { echo "Failed to enter root directory"; exit 1; }

    # Check if we're already in a virtual environment
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        echo "Using existing virtual environment: $VIRTUAL_ENV"
    else
        # Remove existing virtual environment if it exists
        if [ -d ".venv" ]; then
            echo "Removing existing virtual environment..."
            rm -rf .venv
        fi

        # Create virtual environment with uv
        echo "Creating virtual environment..."
        if ! uv venv .venv; then
            echo -e "${RED}Failed to create virtual environment${NC}"
            ALL_TESTS_PASSED=false
            return 1
        fi

        # Activate virtual environment based on OS
        echo "Activating virtual environment..."
        if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
            source .venv/Scripts/activate
        else
            source .venv/bin/activate
        fi
    fi

    # Install the package in editable mode with dev dependencies
    echo "Installing syft-flwr and dev dependencies..."
    if ! uv sync --group dev; then
        echo -e "${RED}Failed to install syft-flwr${NC}"
        ALL_TESTS_PASSED=false
        return 1
    fi

    return 0
}

# Function to run unit tests
run_unit_tests() {
    echo ""
    echo "========================================="
    echo "Running Unit Tests"
    echo "========================================="

    ROOT_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"

    if [ -d "tests" ]; then
        echo "Running unit tests in parallel..."
        if uv run pytest tests/ -v -n auto --cov=syft_flwr --cov-report=term-missing --cov-report=xml --ignore="$ROOT_DIR/tests/integration/syft-client"; then
            echo -e "${GREEN}Unit tests PASSED${NC}"
        else
            echo -e "${RED}Unit tests FAILED${NC}"
            ALL_TESTS_PASSED=false
        fi
    else
        echo "No tests directory found"
    fi
}

# Function to run integration tests
run_integration_tests() {
    echo ""
    echo "========================================="
    echo "Running Integration Tests (Google Drive)"
    echo "========================================="

    # Check if credentials exist
    if [ ! -d "credentials" ] || [ ! -f "credentials/.env" ]; then
        echo -e "${RED}Error: credentials/ directory or .env file not found${NC}"
        echo "Please set up Google OAuth credentials first."
        echo "See DEVELOPMENT.md for instructions."
        ALL_TESTS_PASSED=false
        return 1
    fi

    if [ -d "tests/integration/syft-client" ]; then
        # Run each test file separately to avoid conflicts
        # (tests share the same Google Drive accounts and their fixtures conflict)
        for test_file in tests/integration/syft-client/*_test.py; do
            if [ -f "$test_file" ]; then
                echo ""
                echo "-----------------------------------------"
                echo "Running: $(basename "$test_file")"
                echo "-----------------------------------------"
                if uv run pytest "$test_file" -v -s --tb=short; then
                    echo -e "${GREEN}$(basename "$test_file") PASSED${NC}"
                else
                    echo -e "${RED}$(basename "$test_file") FAILED${NC}"
                    ALL_TESTS_PASSED=false
                fi
            fi
        done
    else
        echo "No integration tests directory found"
    fi
}

# Main script
echo -e "${CYAN}Starting syft-flwr test suite (${TEST_TYPE})...${NC}"

# Setup environment
setup_env || exit 1

# Run appropriate tests based on argument
case "$TEST_TYPE" in
    unit)
        run_unit_tests
        ;;
    integration)
        run_integration_tests
        ;;
    all)
        run_unit_tests
        run_integration_tests
        ;;
    *)
        echo -e "${RED}Unknown test type: $TEST_TYPE${NC}"
        echo "Usage: $0 [unit|integration|all]"
        exit 1
        ;;
esac

# Deactivate virtual environment only if we created it
if [[ "$VIRTUAL_ENV" == "" ]]; then
    deactivate 2>/dev/null || true
fi

echo ""
if [ "$ALL_TESTS_PASSED" = true ]; then
    echo -e "${GREEN}All tests completed successfully!${NC}"
    exit 0
else
    echo -e "${RED}Some tests FAILED!${NC}"
    exit 1
fi
