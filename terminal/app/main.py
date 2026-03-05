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
from app.services.core_engine_service import core_engine

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
    Return the last cached pizza occupancy data from the scraper service.
    """
    return await pizza_service.get_index()
# -------------------------------------------

# 3. Chat router
from app.api import chat
app.include_router(chat.router, prefix="/api", tags=["Chat"])

# 3.1 Logs router
from app.api import logs
app.include_router(logs.router, prefix="/api", tags=["Docker Logs"])

# 4. EDGAR Service (Financials)
from app.services.edgar_service import edgar_service

@app.get("/api/edgar/{ticker}")
async def get_company_financials(ticker: str):
    """
    Get company financial facts from SEC EDGAR.
    Cached for 5 days.
    """
    return await edgar_service.get_financials(ticker)

@app.get("/api/edgar/saved/list")
async def get_saved_tickers():
    """
    Get list of companies that have cached financial data.
    """
    from app.database import crud
    tickers = crud.get_saved_tickers()
    return {"tickers": tickers}

# --- FRED API ---
@app.get("/api/fred/series/{series_id}")
async def get_fred_series(series_id: str):
    """Fetch FRED data (cached or remote)."""
    from app.services.fred_service import fred_service
    data = await fred_service.get_series_data(series_id)
    if "error" in data:
         return JSONResponse(status_code=400, content=data)
    return data

@app.get("/api/fred/saved")
async def get_saved_fred_series():
    """Get list of cached FRED series."""
    from app.database import crud
    ids = crud.get_saved_fred_series()
    return {"series": ids}

@app.get("/api/backtests")
async def get_backtests():
    return await core_engine.get_backtest_list()

@app.post("/api/train/trigger")
async def trigger_training():
    return await core_engine.trigger_training()

@app.post("/api/backtests/run")
async def run_backtest(req: dict):
    return await core_engine.run_custom_backtest(req.get("start_date"), req.get("end_date"))

@app.get("/api/backtests/{run_id}")
async def get_backtest_details(run_id: str):
    return await core_engine.get_backtest_results(run_id)

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

    # Schedule concurrent background tasks
    asyncio.create_task(twitter_loop())
    asyncio.create_task(rss_loop())

    print(" All Intelligence Systems are ONLINE.")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)