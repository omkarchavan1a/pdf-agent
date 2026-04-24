"""
Entrypoint that reuses the backend application.
"""

import os

from backend.main import app


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("IDP_BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("IDP_BACKEND_PORT", "8000"))
    print(f"IDP Intelligence Agent starting on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
