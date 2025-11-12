#!/usr/bin/env python3
"""
Simple test script for Heroku deployment.
This runs basic checks without requiring pytest.
"""

import os
import sys

def test_app_import():
    """Test that we can import the app."""
    try:
        from app import app
        print("✓ App import successful")
        return True
    except ImportError as e:
        print(f"✗ App import failed: {e}")
        return False

def test_env_file():
    """Test that .env.example exists."""
    if os.path.exists('.env.example'):
        print("✓ .env.example exists")
        return True
    else:
        print("✗ .env.example missing")
        return False

def test_requirements():
    """Test that requirements.txt exists."""
    if os.path.exists('requirements.txt'):
        print("✓ requirements.txt exists")
        return True
    else:
        print("✗ requirements.txt missing")
        return False

def main():
    """Run all tests."""
    print("Running basic deployment tests...")

    tests = [
        test_app_import,
        test_env_file,
        test_requirements,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
