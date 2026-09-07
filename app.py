"""Compatibility entry point for the backend API."""
import os

from backend.app import create_app

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
