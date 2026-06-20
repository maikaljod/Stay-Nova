"""Compatibility entry point (kept at the project root).

Prefer `python run.py`. This file exists so `python app.py` also works.
"""
from run import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=app.config.get("DEBUG", False))
