#!/usr/bin/env python3
"""Script to run all tests with proper configuration."""

import sys
import subprocess
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

def run_tests():
    """Run all tests."""
    test_dir = Path(__file__).parent
    
    # Run pytest with configuration
    cmd = [
        "pytest",
        str(test_dir),
        "-v",
        "--tb=short",
        "--color=yes"
    ]
    
    # Add coverage if requested
    if "--coverage" in sys.argv:
        cmd.extend([
            "--cov=backend",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    # Run specific test category
    if "--unit" in sys.argv:
        cmd.append(str(test_dir / "unit"))
    elif "--integration" in sys.argv:
        cmd.append(str(test_dir / "integration"))
    elif "--e2e" in sys.argv:
        cmd.append(str(test_dir / "e2e"))
    
    # Run tests
    result = subprocess.run(cmd)
    return result.returncode

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
