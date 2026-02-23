import os
import httpx
import asyncio
from datetime import datetime, timedelta
from app.database import crud
from app.core.config import settings

class EdgarService:
    """Service for interacting with SEC EDGAR API and managing financial data cache."""

    def __init__(self):
        self.cik_map = {}
        self.base_url = "https://data.sec.gov"
        self.headers = {
            "User-Agent": os.getenv("EDGAR_API_KEY", "ArbitronTerminal contact@example.com"),
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov"
        }

    async def _fetch_cik_map(self):
        """Fetch and cache the official Ticker -> CIK mapping from SEC."""
        if self.cik_map:
            return

        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            async with httpx.AsyncClient() as client:
                # Different host for tickers json
                headers = self.headers.copy()
                headers["Host"] = "www.sec.gov"
                
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                
                # Structure is {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
                for item in data.values():
                    self.cik_map[item["ticker"].upper()] = item["cik_str"]
                
                print(f" [Edgar Service] Loaded {len(self.cik_map)} tickers from SEC.")
        except Exception as e:
            print(f" [Edgar Service] Failed to load CIK map: {e}")

    def _is_cache_fresh(self, ticker: str) -> bool:
        """Check if cached data is less than 5 days old."""
        last_update_str = crud.get_last_update_time(ticker)
        if not last_update_str:
            return False
        
        try:
            # SQLite current_timestamp format: "YYYY-MM-DD HH:MM:SS"
            last_update = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M:%S")
            return datetime.now() - last_update < timedelta(days=5)
        except ValueError:
            # Handle potential format mismatch if any
            return False

    async def get_financials(self, ticker: str):
        """Get company facts. Returns cached data if fresh, otherwise fetches from SEC."""
        ticker = ticker.upper()
        
        # 1. Check cache freshness
        if self._is_cache_fresh(ticker):
            print(f" [Edgar Service] Returning cached data for {ticker}")
            return crud.get_company_facts(ticker)

        # 2. Need to fetch. Ensure we have CIK map.
        await self._fetch_cik_map()
        
        cik = self.cik_map.get(ticker)
        if not cik:
            print(f" [Edgar Service] CIK not found for {ticker}")
            return []

        # 3. Fetch from SEC
        print(f" [Edgar Service] Fetching facts for {ticker} (CIK: {cik}) from SEC...")
        padded_cik = str(cik).zfill(10)
        url = f"{self.base_url}/api/xbrl/companyfacts/CIK{padded_cik}.json"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                data = resp.json()
                
                facts_list = self._parse_api_response(data, cik, ticker)
                
                # 4. Save to DB
                if facts_list:
                    crud.upsert_company_facts(ticker, facts_list)
                    print(f" [Edgar Service] Saved {len(facts_list)} facts for {ticker}")
                
                return facts_list

        except Exception as e:
            print(f" [Edgar Service] Error fetching data for {ticker}: {e}")
            # Fallback to whatever we have in cache if fetch fails
            return crud.get_company_facts(ticker)

    def _parse_api_response(self, data: dict, cik: int, ticker: str) -> list:
        """Flatten the complex SEC JSON structure into a flat list of facts."""
        facts = []
        if "facts" not in data:
            return []

        # SEC JSON structure: facts -> us-gaap (or ifrs-full) -> ConceptName -> units -> Currency -> [list of facts]
        # We will iterate through all taxonomies (us-gaap, dei, etc.)
        for taxonomy, concepts in data["facts"].items():
            for tag, details in concepts.items():
                if "units" not in details:
                    continue
                
                for unit, measurements in details["units"].items():
                    for m in measurements:
                        # We only care about data with value, period and form
                        if "val" not in m or "end" not in m:
                            continue
                            
                        facts.append({
                            "cik": cik,
                            "ticker": ticker,
                            "tag": tag,
                            "value": m["val"],
                            "period": m["end"],
                            "form": m.get("form", "Unknown"),
                            "unit": unit
                        })
        return facts

# Global instance
edgar_service = EdgarService()