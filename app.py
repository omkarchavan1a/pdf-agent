"""
Entrypoint that reuses the backend application.
"""

from backend.main import app


if __name__ == "__main__":
    import uvicorn

    print("IDP Intelligence Agent starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
