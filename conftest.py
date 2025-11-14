"""Root-level pytest configuration."""
import sys
from pathlib import Path


def pytest_configure(config):
    """Configure pytest - add demo directories to Python path."""
    root_dir = Path(__file__).parent
    demo_dirs = [
        root_dir / "idempotent-webhook",
        root_dir / "notification-fanout",
        root_dir / "rate-limiter",
        root_dir / "feature-flags",
    ]
    
    for demo_dir in demo_dirs:
        if demo_dir.exists():
            demo_path = str(demo_dir)
            if demo_path not in sys.path:
                sys.path.insert(0, demo_path)

