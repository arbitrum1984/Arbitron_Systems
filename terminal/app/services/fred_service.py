"""FRED (Federal Reserve Economic Data) Service.

This module handles fetching and caching macroeconomic time-series data
from the St. Louis Fed API. It supports checking the local database cache
before hitting the remote API to respect rate limits and improve performance.
"""

import httpx
import asyncio
from datetime import datetime, timedelta
from app.core.config import settings
from app.database import crud

class FredService:
    """Service for interacting with the FRED API."""

    def __init__(self):
        self.api_key = settings.FRED_API_KEY
        self.base_url = "https://api.stlouisfed.org/fred"

    async def get_series_data(self, series_id: str):
        """Get data for a specific series (e.g., 'GDP', 'UNRATE').
        
        Logic:
        1. Check DB for cached data.
        2. If cached and fresh (< 5 days old), return DB data.
        3. Else, fetch from FRED API.
        4. Update DB.
        5. Return data.
        """
        series_id = series_id.upper()
        
        # 1. Check Cache
        last_update = crud.get_fred_last_update(series_id)
        if last_update:
            last_update_dt = datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S")
            if datetime.now() - last_update_dt < timedelta(days=5):
                print(f" [FRED] Serving {series_id} from cache.")
                return crud.get_fred_observations(series_id)

        # 2. Fetch from API
        if not self.api_key:
            return {"error": "No FRED API Key configured."}

        print(f" [FRED] Fetching {series_id} from remote...")
        try:
            async with httpx.AsyncClient() as client:
                # Fetch observations
                url = f"{self.base_url}/series/observations"
                params = {
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 100 # Get last 100 data points
                }
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                observations = data.get("observations", [])
                
                # 3. Cache to DB
                # Format: [{'date': '2025-01-01', 'value': '123.45'}, ...]
                clean_obs = []
                for obs in observations:
                    val = obs.get("value")
                    if val != ".": # FRED returns "." for missing data
                        clean_obs.append({
                            "date": obs.get("date"),
                            "value": float(val)
                        })
                
                crud.upsert_fred_data(series_id, clean_obs)
                
                return clean_obs

        except Exception as e:
            print(f" [FRED] Error: {e}")
            # Fallback to cache even if stale
            return crud.get_fred_observations(series_id)

fred_service = FredService()
