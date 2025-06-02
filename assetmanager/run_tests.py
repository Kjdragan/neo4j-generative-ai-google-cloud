#!/usr/bin/env python3
"""
Test runner script for Neo4j Asset Manager.
"""
import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_tests(test_path=None, verbose=True, coverage=False):
    """
    Run tests using pytest.
    
    Args:
        test_path: Optional path to specific test file or directory
        verbose: Whether to run tests in verbose mode
        coverage: Whether to generate coverage report
    """
    # Determine command to run
    cmd = ["uv", "run", "pytest"]
    
    # Add options
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=src", "--cov-report=term", "--cov-report=html"])
    
    # Add test path if specified
    if test_path:
        cmd.append(test_path)
    
    # Run command
    logger.info(f"Running tests with command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Tests failed with exit code: {e.returncode}")
        sys.exit(e.returncode)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run tests for Neo4j Asset Manager")
    parser.add_argument("test_path", nargs="?", help="Path to specific test file or directory")
    parser.add_argument("-q", "--quiet", action="store_true", help="Run tests in quiet mode")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    
    args = parser.parse_args()
    
    # Ensure we're in the correct directory
    os.chdir(Path(__file__).parent)
    
    # Run tests
    run_tests(
        test_path=args.test_path,
        verbose=not args.quiet,
        coverage=args.coverage
    )


if __name__ == "__main__":
    main()
