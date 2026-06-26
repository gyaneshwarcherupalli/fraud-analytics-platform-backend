#!/usr/bin/env python
"""
Setup and initialization script for development environment.
"""
import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description):
    """Run a shell command and report status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"{'='*60}")
    try:
        result = subprocess.run(command, shell=True, check=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed with error: {e}")
        return False


def main():
    """Main setup function."""
    print(f"\n{'='*60}")
    print("Fraud Analytics Platform - Setup Script")
    print(f"{'='*60}")
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    print(f"✓ Logs directory created: {log_dir}")
    
    # Install dependencies
    if not run_command(
        f"{sys.executable} -m pip install -r requirements.txt",
        "Installing dependencies"
    ):
        return False
    
    # Run database migrations
    if not run_command(
        f"{sys.executable} setup.py",
        "Initializing database"
    ):
        return False
    
    print(f"\n{'='*60}")
    print("Setup completed successfully!")
    print(f"{'='*60}")
    print("\nNext steps:")
    print("1. Update .env with your configuration")
    print("2. Run: python -m uvicorn app.main:app --reload")
    print("   Or: docker-compose up -d")
    print(f"{'='*60}\n")
    
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
