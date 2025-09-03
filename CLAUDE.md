# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands
- Run Web App: `flask run` or `python -m flask run` (uses mqtt_grid_web.py)
- Run LoRa Integration: `python CaptureLora.py`
- Create New Key: `python create_key.py`
- Manage Queue: `./load_queue.sh` or `./release_queue.sh`
- Lint: `flake8 *.py utils/*.py configs/*.py`
- Type Check: `mypy *.py utils/*.py configs/*.py`

## Code Style Guidelines
- Python 3 with Flask and MQTT
- Functional, declarative programming; avoid classes except for Flask views
- Use type hints for all function signatures
- Lowercase with underscores for directories and files
- Early returns for error conditions (if-return pattern over nested if-else)
- Descriptive variable names with auxiliary verbs (is_active, has_permission)
- Error handling with try/except at start of functions
- JSON deserialization wrapped in exception handling
- Use defensive coding (None checks, type checks) 
- Secrets managed via Google Cloud Secret Manager
- Config values from environment variables or config.py
- Log errors with stack traces for debugging (debug vs info level)