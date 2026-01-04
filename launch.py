"""ASGI application wiring and minimal HTTP endpoints for the SPA.

This module constructs the FastAPI application used by the project,
mounts static assets, and registers the primary API router. It also
exposes two small endpoints used by the browser: the root HTML page
that bootstraps the client application, and the favicon endpoint to
prevent browser 404 noise. These endpoints are intentionally
lightweight and return `FileResponse` objects so that the ASGI
server can serve files efficiently.

Notes:
    - The module is designed for local development and simple
      deployments. For production use, run an ASGI server (Uvicorn,
      Gunicorn + Uvicorn workers) managed by a process supervisor.
"""
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.api import chat


# Create the FastAPI application instance with basic metadata
app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)


# Mount static assets (CSS, JS, images) served from the `static`
# directory adjacent to the project root.
app.mount("/static", StaticFiles(directory="static"), name="static")


# Register API router under the `/api` prefix so handlers in
# `app.api.chat` are available at `/api/...`.
app.include_router(chat.router, prefix="/api")


@app.get("/")
async def read_root():
    """Serve the single-page application HTML shell.

    This endpoint returns the `static/index.html` file that bootstraps
    the client-side application. The function returns a
    `fastapi.responses.FileResponse` object which allows the ASGI
    server to stream the file efficiently to the client.

    Returns:
        fastapi.responses.FileResponse: The HTML file response.
    """
    return FileResponse("static/index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return the site's favicon to avoid 404 logs in browsers.

    The endpoint is excluded from the OpenAPI schema (`include_in_schema=False`)
    as it is not part of the public API surface. It returns the
    static `logo.ico` file used as the favicon.

    Returns:
        fastapi.responses.FileResponse: The favicon file response.
    """
    return FileResponse("static/assets/logo.ico")


if __name__ == "__main__":
    print(f"{settings.PROJECT_NAME} is running on http://localhost:8000")
    uvicorn.run("launch:app", host="0.0.0.0", port=8000, reload=True)