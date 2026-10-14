"""Initialize the local FI'L AI SQLite database."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fil_ai.storage import TaskStore  # noqa: E402

if __name__ == "__main__":
    store = TaskStore()
    print(f"Initialized database: {store.path}")
