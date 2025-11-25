#!/bin/bash
# Test script for syft-flwr project

echo "Running tests for syft-flwr..."

# Track overall test status
ALL_TESTS_PASSED=true

# Function to run tests
run_tests() {
    echo ""
    echo "========================================="
    echo "Testing syft-flwr"
    echo "========================================="

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
            echo -e "\033[0;31mFailed to create virtual environment\033[0m"
            ALL_TESTS_PASSED=false
            return 1
        fi

        # Activate virtual environment based on OS
        echo "Activating virtual environment..."
        if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
            # Windows
            source .venv/Scripts/activate
        else
            # Unix-like (Linux, macOS)
            source .venv/bin/activate
        fi
    fi

    # Install the package in editable mode with dependencies
    echo "Installing syft-flwr and dependencies..."
    if ! uv pip install -e .; then
        echo -e "\033[0;31mFailed to install syft-flwr\033[0m"
        ALL_TESTS_PASSED=false
        if [[ "$VIRTUAL_ENV" == "" ]]; then
            deactivate
        fi
        return 1
    fi

    # Install test dependencies
    echo "Installing test dependencies..."
    if ! uv pip install pytest pytest-cov pytest-xdist pytest-asyncio; then
        echo -e "\033[0;31mFailed to install test dependencies\033[0m"
        ALL_TESTS_PASSED=false
        if [[ "$VIRTUAL_ENV" == "" ]]; then
            deactivate
        fi
        return 1
    fi

    # Run tests if they exist
    if [ -d "tests" ]; then
        echo "Running tests in parallel..."
        if uv run pytest tests/ -v -n auto --cov=syft_flwr --cov-report=term-missing --cov-report=xml --ignore=tests/integration/syft-client; then
            echo -e "\033[0;32mTests PASSED for syft-flwr\033[0m"
        else
            echo -e "\033[0;31mTests FAILED for syft-flwr\033[0m"
            ALL_TESTS_PASSED=false
        fi
    else
        echo "No tests directory found, skipping tests"
    fi

    # Deactivate virtual environment only if we created it
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        deactivate
    fi
}

# Main script
echo "Starting syft-flwr test suite..."

# Run tests
run_tests

echo ""
if [ "$ALL_TESTS_PASSED" = true ]; then
    echo -e "\033[0;32mAll tests completed successfully!\033[0m"
    exit 0
else
    echo -e "\033[0;31mSome tests FAILED!\033[0m"
    exit 1
fi