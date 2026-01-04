"""Application entrypoint for the Arbitron Systems FastAPI server.

This module configures and exposes the FastAPI application instance
used by the project. It mounts static assets, registers the API
router, and provides a convenience `start_server` function to run a
development Uvicorn server. The `start_server` function is small and
documented to clarify runtime expectations for development and local
testing. In production deployments, a dedicated ASGI server/process
manager is recommended instead of `start_server`.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import application configuration and API router
from app.core.config import settings
from app.api import chat


# 1. Create the FastAPI application instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Professional Financial AI Backend"
)


# 2. Mount static assets. The `static` directory should be located
#    adjacent to this module when running the development server.
app.mount("/static", StaticFiles(directory="static"), name="static")


# 3. Register API router under the /api prefix
#    Example endpoint: http://localhost:8000/api/query
app.include_router(chat.router, prefix="/api", tags=["Chat"])


def start_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = True) -> None:
    """Start a development Uvicorn server hosting the FastAPI app.

    This convenience function prints brief startup information and
    runs the Uvicorn server. It is intended for local development
    and testing. For production use, prefer running Uvicorn/Gunicorn
    from the command line or using a process manager.

    Args:
        host (str): Host/interface to bind (default: "0.0.0.0").
        port (int): TCP port to listen on (default: 8000).
        reload (bool): If True, enables Uvicorn's auto-reload for
            development (default: True).

    Returns:
        None
    """
    print(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    print(f"Server running at: http://{host}:{port}")
    print(f"Docs available at: http://{host}:{port}/docs")

    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server()