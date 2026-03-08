"""
app.main
--------------------------------

Application entrypoint and background task orchestration for the
Arbitron Systems backend. This module constructs the FastAPI
application, mounts static assets, exposes a small set of frontend
endpoints used by the single-page application, and schedules
lightweight background loops that poll intelligence services.
"""

import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Configuration and routers
from app.core.config import settings
from app.api import chat, logs

# Intelligence service instances (polling targets)
from app.services.twitter_service import twitter_service
from app.services.rss_service import rss_service
from app.services.pizza_service import pizza_service
from app.services.core_engine_service import core_engine
from app.services.trends_service import trends_engine
from app.services.opensky_service import flight_tracker
from app.services.docker_service import DockerService

# Data layer (top-level import instead of lazy import inside functions)
from app.database import crud
from app.services.edgar_service import edgar_service
from app.services.fred_service import fred_service


# --- Lifespan context manager (replaces deprecated @app.on_event) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup/shutdown lifecycle."""

    async def twitter_loop():
        print(" [Twitter Service] Started polling...")
        while True:
            try:
                await twitter_service.fetch_and_process()
            except Exception as e:
                print(f" [Twitter Error]: {e}")
            await asyncio.sleep(900)

    async def rss_loop():
        print(" [RSS/Alerts Service] Started polling...")
        while True:
            try:
                await rss_service.poll_feeds()
            except Exception as e:
                print(f" [RSS Error]: {e}")
            await asyncio.sleep(300)

    async def trends_loop():
        print(" [Trends Service] Started polling...")
        while True:
            try:
                await trends_engine.update_trends_background()
            except Exception as e:
                print(f" [Trends Error]: {e}")
            await asyncio.sleep(14400)

    async def opensky_loop():
        print(" [OpenSky Service] Started polling...")
        while True:
            try:
                await flight_tracker.update_flights_background()
            except Exception as e:
                print(f" [OpenSky Error]: {e}")
            await asyncio.sleep(300)

    # Startup: create background tasks
    tasks = [
        asyncio.create_task(twitter_loop()),
        asyncio.create_task(rss_loop()),
        asyncio.create_task(trends_loop()),
        asyncio.create_task(opensky_loop()),
    ]
    print(" All Intelligence Systems are ONLINE.")

    yield  # Application runs here

    # Shutdown: cancel background tasks gracefully
    for task in tasks:
        task.cancel()
    print(" All Intelligence Systems shutting down.")


# 1. App instance with lifespan
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Professional Financial AI Backend with OSINT Integration",
    lifespan=lifespan,
)

# 2. Static files (CSS/JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 3. Routers
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(logs.router, prefix="/api", tags=["Docker Logs"])

# --- API Endpoints ---

@app.get("/api/pizza")
async def get_pizza_index():
    """Return the last cached pizza occupancy data."""
    return await pizza_service.get_index()


@app.get("/api/edgar/{ticker}")
async def get_company_financials(ticker: str):
    """Get company financial facts from SEC EDGAR."""
    return await edgar_service.get_financials(ticker)


@app.get("/api/edgar/saved/list")
async def get_saved_tickers():
    """Get list of companies with cached financial data."""
    tickers = crud.get_saved_tickers()
    return {"tickers": tickers}


@app.get("/api/fred/series/{series_id}")
async def get_fred_series(series_id: str):
    """Fetch FRED data (cached or remote)."""
    data = await fred_service.get_series_data(series_id)
    if "error" in data:
        return JSONResponse(status_code=400, content=data)
    return data


@app.get("/api/fred/saved")
async def get_saved_fred_series():
    """Get list of cached FRED series."""
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


@app.get("/api/trends")
async def get_trends_data():
    """Return historical JSON data for the Trends Dashboard."""
    return trends_engine.get_historical_data()


@app.get("/api/flights")
async def get_flight_data():
    """Return active flight tracking data from OpenSky."""
    return flight_tracker.get_raw_flights()



@app.delete("/api/intel/clear")
async def clear_intel_stream():
    """Clear old INTEL_STREAM messages."""
    from app.database.database import db
    from app.services.rss_service import rss_service
    
    with db.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = 'INTEL_STREAM'").fetchone()[0]
        conn.execute("DELETE FROM chat_messages WHERE session_id = 'INTEL_STREAM'")
        conn.commit()
        
    rss_service._seen_hashes.clear()
    
    return {"deleted": count}


# --- Frontend Endpoints ---

@app.get("/")
async def read_root():
    """Serve the single-page application HTML."""
    return FileResponse("static/index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve the application favicon."""
    return FileResponse("static/assets/logo.ico")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)