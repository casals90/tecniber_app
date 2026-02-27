#!/usr/bin/env bash

echo "====================================="
echo "   FIRST RUN MAY TAKE A FEW MINUTES"
echo "====================================="
echo

# Go to project folder
cd "$(dirname "$0")"

# -----------------------------
# Check Python
# -----------------------------
if ! command -v python3 &> /dev/null
then
    echo "Python is not installed."
    echo
    echo "Please install Python from:"
    echo "https://www.python.org/downloads/"
    echo
    read -p "Press ENTER after installing Python..."
    exit 1
fi

# -----------------------------
# Check pip
# -----------------------------
if ! command -v pip3 &> /dev/null
then
    echo "pip is missing. Installing pip..."
    python3 -m ensurepip --upgrade
fi

# -----------------------------
# Install uv if missing
# -----------------------------
if ! command -v uv &> /dev/null
then
    echo "Installing uv..."
    pip3 install --user uv
    export PATH="$HOME/.local/bin:$PATH"
fi

# -----------------------------
# Create virtual environment
# -----------------------------
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv
fi

# -----------------------------
# Activate environment
# -----------------------------
source .venv/bin/activate

# -----------------------------
# Install dependencies
# -----------------------------
echo "Installing project dependencies..."
uv sync

# -----------------------------
# Run Streamlit
# -----------------------------
echo
echo "Starting application..."
echo

uv run streamlit run main.py