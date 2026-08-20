"""
Helper script: install all dependencies and run the full test suite.
Uses absolute paths so it works regardless of the shell's working directory.
"""
import subprocess
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR    = os.path.join(PROJECT_ROOT, 'tests')
VENV_PY      = sys.executable
REQS         = os.path.join(PROJECT_ROOT, 'requirements.txt')

# Install all dependencies (quiet — only shows errors)
subprocess.run(
    [VENV_PY, '-m', 'pip', 'install', '-r', REQS, '--quiet'],
    check=True
)

# Run pytest with verbose output
result = subprocess.run(
    [VENV_PY, '-m', 'pytest', TESTS_DIR, '-v', '--tb=short'],
)
sys.exit(result.returncode)
