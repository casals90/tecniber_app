#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
uv run streamlit run main.py