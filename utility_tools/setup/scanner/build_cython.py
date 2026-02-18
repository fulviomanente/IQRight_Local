"""
Cython build script for IQRight Scanner.
Compiles all .py files to native .so extensions.
Run on the Raspberry Pi during setup.

Usage:
    python build_cython.py build_ext --inplace
"""
from setuptools import setup
from Cython.Build import cythonize
import os

# Files to exclude from compilation (must remain as .py)
EXCLUDE_FILES = {
    '__init__.py',       # Required for package imports
    'build_cython.py',  # This file
    'run_scanner.py',   # Launcher script
}

# Directories to skip
EXCLUDE_DIRS = {'.venv', 'venv', '__pycache__', 'configs', 'data', 'log', 'build'}


def get_py_files():
    py_files = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f.endswith('.py') and f not in EXCLUDE_FILES:
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
        nthreads=4,
    ),
)
