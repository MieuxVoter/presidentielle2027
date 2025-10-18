"""Pytest configuration and shared fixtures."""
import sys
from pathlib import Path

# Add project root to path for easier imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
