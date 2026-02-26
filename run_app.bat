@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
uv run streamlit run main.py