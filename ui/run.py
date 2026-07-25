"""Single-file launcher for DEEPUTIN Pipeline Observatory.

Starts the FastAPI backend which also serves the built React frontend.
Usage:
    python run.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "dpo.main:app",
        app_dir="backend",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
