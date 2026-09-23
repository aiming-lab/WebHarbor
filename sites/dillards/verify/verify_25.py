#!/usr/bin/env python3
"""Deterministic verifier for Dillards--25."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grade import grade

if __name__ == "__main__":
    grade(25)
