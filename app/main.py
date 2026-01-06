"""
app.main
--------------------------------

Application entrypoint and background task orchestration for the
Arbitron Systems backend. This module constructs the FastAPI
application, mounts static assets, exposes a small set of frontend
endpoints used by the single-page application, and schedules
lightweight background loops that poll intelligence services.

The module intentionally keeps background tasks simple: they are
fire-and-forget asyncio tasks suitable for development and low-load
 deployments. Production deployments should consider robust
 process supervision and resilient task frameworks.
"""

import uvicorn
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Configuration and routers
from app.core.config import settings
from app.api import chat

# Intelligence service instances (polling targets)
from app.services.twitter_service import twitter_service
from app.services.rss_service import rss_service
from app.services.pizza_service import pizza_service

# 1. Poject app instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Professional Financial AI Backend with OSINT Integration"
)

# 2. Statistics (CSS/JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Pizza rout ---
@app.get("/api/pizza")
async def get_pizza_index():
    """
    Retrieve the current pizza occupancy index for all configured targets.

    This endpoint simply proxies the normalized structure returned by
    `PizzaService.check_index` and is intended for UI consumption.

    Returns:
        list: A list of occupancy objects as produced by the service.
    """
    return await pizza_service.check_index()
# -------------------------------------------

# 3. Chat router
app.include_router(chat.router, prefix="/api", tags=["Chat"])

# --- FRONTEND ENDPOINTS ---
@app.get("/")
async def read_root():
    """
    Serve the single-page application's shell.

    Returns the static `index.html` file that bootstraps the client
    application. The response is a direct file proxy so the frontend
    can be served from the same process during development.

    Returns:
        fastapi.responses.FileResponse: The SPA HTML file.
    """
    return FileResponse("static/index.html")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """
    Serve the application favicon.

    This endpoint is excluded from the OpenAPI schema and returns a
    small icon used by browsers and operating systems.

    Returns:
        fastapi.responses.FileResponse: The favicon image.
    """
    return FileResponse("static/assets/logo.ico")
# ------------------------------------------------------------------

# --- Data flow ---
@app.on_event("startup")
async def start_intel_engine():
    """
    Initialize and schedule background intelligence polling loops.

    The function creates three independent asyncio tasks that poll
    Twitter, RSS feeds, and the Pizza index service at conservative
    intervals. Tasks are created with `asyncio.create_task` so they
    execute concurrently without blocking the FastAPI startup
    sequence. Exceptions within each loop are logged to stdout to
    avoid terminating the scheduler prematurely.

    Notes:
        - This simplistic scheduling strategy is suitable for
          development and light-duty deployments. For production use
          consider a dedicated task scheduler or external worker
          processes for robustness and observability.
    """

    async def twitter_loop():
        """
        Poll the Twitter service periodically and persist results.

        Sleeps for 900 seconds (15 minutes) between iterations.
        Exceptions are caught and printed to stdout.
        """
        print(" [Twitter Service] Started polling...")
        while True:
            try:
                await twitter_service.fetch_and_process()
            except Exception as e:
                print(f" [Twitter Error]: {e}")
            await asyncio.sleep(900)

    async def rss_loop():
        """
        Poll RSS/alerts feeds and ingest results into the alerting
        pipeline.

        Sleeps for 300 seconds (5 minutes) between iterations.
        """
        print(" [RSS/Alerts Service] Started polling...")
        while True:
            try:
                await rss_service.poll_feeds()
            except Exception as e:
                print(f" [RSS Error]: {e}")
            await asyncio.sleep(300)

    async def pizza_loop():
        """
        Refresh the Pizza index periodically.

        Sleeps for 1800 seconds (30 minutes) between iterations. The
        underlying service can operate in simulation mode for demo
        scenarios.
        """
        print(" [Pizza Index Service] Started polling...")
        while True:
            try:
                await pizza_service.check_index()
            except Exception as e:
                print(f" [Pizza Error]: {e}")
            await asyncio.sleep(1800)

    # Schedule concurrent background tasks
    asyncio.create_task(twitter_loop())
    asyncio.create_task(rss_loop())
    asyncio.create_task(pizza_loop())

    print(" All Intelligence Systems are ONLINE.")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)