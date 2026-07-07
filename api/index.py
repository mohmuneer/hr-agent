"""Vercel serverless entry point for FastAPI."""
import sys
from pathlib import Path

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app

# Vercel ASGI expects `app` to be the ASGI application
