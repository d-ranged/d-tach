"""
Root conftest.py — adds the project root to sys.path so that pytest can
import the app package without needing to be invoked as 'python -m pytest'.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))