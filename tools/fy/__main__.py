"""Lets `python tools/fy <command>` and `python -m fy <command>` both work."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fy.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
