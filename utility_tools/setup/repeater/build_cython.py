"""
Cython Build Script for IQRight Repeater
=========================================

Compiles all Python source files (.py) to native shared libraries (.so)
using Cython. This protects the source code on deployed devices and can
improve performance slightly.

IMPORTANT — Cython enforces type annotations as strict C-level checks.
    In pure Python, `bytes` and `bytearray` are interchangeable, but
    Cython-compiled code will reject a `bytearray` where `bytes` is
    annotated. Always wrap external data with `bytes()` before passing
    it to functions with `: bytes` type hints (e.g. rfm9x.receive()
    returns bytearray → convert before calling deserialize()).

Prerequisites (installed by setup_repeater.sh):
    pip install cython setuptools
    sudo apt install -y python3-dev gcc

Full compilation (all files):
    python build_cython.py build_ext --inplace

    This will:
    1. Cythonize: convert .py → .c (Cython transpilation)
    2. Compile:   convert .c  → .so (gcc native compilation)
    3. Copy:      place .so files next to original .py files

    After successful compilation, remove source files manually:
        rm repeater.py
        rm lora/collision_avoidance.py lora/node_types.py lora/packet_handler.py
        rm utils/config.py utils/oled_display.py utils/waveshare_monitor.py utils/pisugar_monitor.py
        rm -rf build/ *.c lora/*.c utils/*.c

    Do NOT delete: __init__.py, run_repeater.py, build_cython.py, config.repeater.py

Single file recompilation (after patching a deployed repeater):
    # 1. Copy the updated .py file to the Pi
    scp lora/packet_handler.py iqright@<pi-ip>:/home/iqright/lora/

    # 2. On the Pi: cythonize, compile, clean up
    cd /home/iqright && source .venv/bin/activate
    cython -3 lora/packet_handler.py
    gcc -shared -fPIC -O2 -I/usr/include/python3.13 \\
        -o lora/packet_handler.cpython-313-aarch64-linux-gnu.so \\
        lora/packet_handler.c
    rm lora/packet_handler.py lora/packet_handler.c

    # 3. Restart the service
    sudo systemctl restart iqright-repeater

    The .so filename pattern is: <module>.cpython-<version>-<arch>.so
    To find the correct pattern on your Pi:
        ls *.so lora/*.so utils/*.so

Excluded files (never compiled):
    __init__.py         — Required for Python package imports
    build_cython.py     — This script
    run_repeater.py     — Launcher that imports the compiled repeater module
    config.repeater.py  — Config template (dots in filename break Cython naming)

Excluded directories:
    .venv, venv, __pycache__, configs, data, log, build

Notes:
    - Uses nthreads=1 because Pi Zero W (512MB RAM) runs out of memory
      with parallel compilation.
    - macOS resource fork files (._*) are skipped automatically.
    - If compilation fails, the repeater runs fine from .py source files.
"""
from setuptools import setup
from Cython.Build import cythonize
import os

# Files to exclude from compilation (must remain as .py)
EXCLUDE_FILES = {
    '__init__.py',          # Required for package imports
    'build_cython.py',     # This file
    'run_repeater.py',     # Launcher script
    'config.repeater.py',  # Config template (dots confuse Cython module naming)
}

# Directories to skip
EXCLUDE_DIRS = {'.venv', 'venv', '__pycache__', 'configs', 'data', 'log', 'build'}


def get_py_files():
    py_files = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f.endswith('.py') and f not in EXCLUDE_FILES and not f.startswith('._'):
                py_files.append(os.path.join(root, f))
    return py_files


py_files = get_py_files()
print(f"Compiling {len(py_files)} files:")
for f in sorted(py_files):
    print(f"  {f}")

setup(
    ext_modules=cythonize(
        py_files,
        compiler_directives={
            'language_level': 3,
        },
        nthreads=1,
    ),
)
