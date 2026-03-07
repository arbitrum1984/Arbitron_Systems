"""AI service integrating model calls, data enrichment, and response generation.

This module wraps a lightweight pipeline that interprets a user query,
optionally enriches it with market data and news, and generates a
final textual response using a generative model backend. The pipeline
is intentionally pragmatic: it first attempts to extract a ticker and
intent, then conditionally aggregates structured context (finance
technicals and news) before prompting the model for the final answer.

Optimization notes:
 - Sync blocking calls (yfinance, DDGS) are offloaded via asyncio.to_thread.
 - Independent data fetches run in parallel via asyncio.gather.
 - FRED context is cached in memory and refreshed periodically.
"""

import json
import asyncio
import time
from datetime import datetime
from google import genai
from app.core.config import settings
from app.core.prompts import FINANCE_PROMPT

# Top-level imports (Issue #5 — no lazy imports inside functions)
from app.services.finance_service import finance_engine
from app.services.search_service import search_engine
from app.services.trends_service import trends_engine
from app.services.opensky_service import flight_tracker
from app.database import crud

# --- Issue #8: Unified asset map (replaces KNOWN_TICKERS + TICKER_READABLE) ---
ASSET_MAP = {
    # Commodities
    "brent": {"ticker": "BZ=F", "name": "Brent crude oil"},
    "brent oil": {"ticker": "BZ=F", "name": "Brent crude oil"},
    "brent crude": {"ticker": "BZ=F", "name": "Brent crude oil"},
    "crude oil": {"ticker": "CL=F", "name": "WTI crude oil"},
    "wti": {"ticker": "CL=F", "name": "WTI crude oil"},
    "wti oil": {"ticker": "CL=F", "name": "WTI crude oil"},
    "oil": {"ticker": "CL=F", "name": "WTI crude oil"},
    "gold": {"ticker": "GC=F", "name": "gold"},
    "silver": {"ticker": "SI=F", "name": "silver"},
    "platinum": {"ticker": "PL=F", "name": "platinum"},
    "copper": {"ticker": "HG=F", "name": "copper futures"},
    "natural gas": {"ticker": "NG=F", "name": "natural gas"},
    "nat gas": {"ticker": "NG=F", "name": "natural gas"},
    "wheat": {"ticker": "ZW=F", "name": "wheat futures"},
    "corn": {"ticker": "ZC=F", "name": "corn futures"},
    "soybeans": {"ticker": "ZS=F", "name": "soybean futures"},
    # Indices
    "s&p": {"ticker": "SPY", "name": "S&P 500"},
    "s&p 500": {"ticker": "SPY", "name": "S&P 500"},
    "sp500": {"ticker": "SPY", "name": "S&P 500"},
    "nasdaq": {"ticker": "QQQ", "name": "Nasdaq"},
    "dow": {"ticker": "DIA", "name": "Dow Jones"},
    "dow jones": {"ticker": "DIA", "name": "Dow Jones"},
    "russell": {"ticker": "IWM", "name": "Russell 2000"},
    "dax": {"ticker": "^GDAXI", "name": "DAX"},
    "nikkei": {"ticker": "^N225", "name": "Nikkei 225"},
    # Crypto
    "bitcoin": {"ticker": "BTC-USD", "name": "Bitcoin"},
    "btc": {"ticker": "BTC-USD", "name": "Bitcoin"},
    "ethereum": {"ticker": "ETH-USD", "name": "Ethereum"},
    "eth": {"ticker": "ETH-USD", "name": "Ethereum"},
    "solana": {"ticker": "SOL-USD", "name": "Solana"},
    "sol": {"ticker": "SOL-USD", "name": "Solana"},
    # Forex
    "euro": {"ticker": "EURUSD=X", "name": "EUR/USD forex"},
    "eur/usd": {"ticker": "EURUSD=X", "name": "EUR/USD forex"},
    "dollar": {"ticker": "DX-Y.NYB", "name": "US Dollar Index"},
    "dxy": {"ticker": "DX-Y.NYB", "name": "US Dollar Index"},
    "yen": {"ticker": "JPY=X", "name": "USD/JPY forex"},
    "usd/jpy": {"ticker": "JPY=X", "name": "USD/JPY forex"},
    "pound": {"ticker": "GBPUSD=X", "name": "GBP/USD forex"},
    "gbp": {"ticker": "GBPUSD=X", "name": "GBP/USD forex"},
    # VIX
    "vix": {"ticker": "^VIX", "name": "VIX volatility index"},
}

# Reverse lookup: ticker → readable name (auto-generated from ASSET_MAP)
TICKER_TO_NAME = {}
for _entry in ASSET_MAP.values():
    TICKER_TO_NAME[_entry["ticker"]] = _entry["name"]


class AIService:
    """High-level AI orchestration service.

    The service manages a configured generative model client and
    exposes an asynchronous `get_response` method that implements a
    three-stage pipeline: extraction, enrichment, and final generation.
    """

    def __init__(self):
        """Initialize the service and validate configuration."""
        if not settings.GEMINI_API_KEY:
            raise ValueError("API Key missing")

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = "gemini-flash-lite-latest"

        # Issue #7: In-memory FRED cache (refreshed every hour)
        self._fred_cache = ""
        self._fred_cache_time = 0
        self._FRED_CACHE_TTL = 3600  # 1 hour

    def _get_fred_context(self) -> str:
        """Return cached FRED macro context, refreshing if stale."""
        now = time.time()
        if now - self._fred_cache_time < self._FRED_CACHE_TTL and self._fred_cache:
            return self._fred_cache

        try:
            fred_series_ids = crud.get_saved_fred_series()
            if fred_series_ids:
                fred_summary = []
                for sid in fred_series_ids:
                    obs = crud.get_fred_observations(sid)
                    if obs:
                        last_pt = obs[-1]
                        fred_summary.append(f"{sid}: {last_pt['value']} (as of {last_pt['date']})")

                if fred_summary:
                    self._fred_cache = "\n--- MACROECONOMIC DATA (Official Cached) ---\n" + "\n".join(fred_summary)
                else:
                    self._fred_cache = ""
            else:
                self._fred_cache = ""

            self._fred_cache_time = now
        except Exception as e:
            print(f"Error fetching FRED context: {e}")

        return self._fred_cache

    def _get_edgar_context(self, ticker: str) -> str:
        """Fetch EDGAR SEC filing context for a ticker."""
        try:
            facts = crud.get_company_facts(ticker)
            if not facts:
                return ""

            KEY_TAGS = [
                "Revenues", "RevenueFromContractWithCustomer",
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenue", "NetIncomeLoss", "ProfitLoss", "NetInformation",
                "OperatingIncomeLoss", "EarningsPerShareBasic",
                "Assets", "Liabilities", "StockholdersEquity",
                "CashAndCashEquivalents", "CashAndCashEquivalentsAtCarryingValue"
            ]

            LABELS = {
                "Revenues": "Total Revenue",
                "RevenueFromContractWithCustomer": "Revenue",
                "RevenueFromContractWithCustomerExcludingAssessedTax": "Revenue",
                "Revenue": "Revenue",
                "NetIncomeLoss": "Net Income",
                "ProfitLoss": "Net Income",
                "OperatingIncomeLoss": "Operating Income",
                "EarningsPerShareBasic": "EPS",
                "Assets": "Total Assets",
                "Liabilities": "Total Liabilities",
                "StockholdersEquity": "Equity",
                "CashAndCashEquivalents": "Cash",
                "CashAndCashEquivalentsAtCarryingValue": "Cash"
            }

            relevant_facts = [
                f for f in facts
                if f['form'] in ('10-K', '10-Q')
                and any(tag in f['tag'] for tag in KEY_TAGS)
            ]
            relevant_facts.sort(key=lambda x: x['period'], reverse=True)

            grouped = {}
            for f in relevant_facts:
                p = f['period']
                if p not in grouped:
                    grouped[p] = []
                label = LABELS.get(f['tag'], f['tag'])
                entry = f"{label}: {f['value']} {f['unit']}"
                if not any(entry.startswith(label + ":") for entry in grouped[p]):
                    grouped[p].append(entry)

            edgar_summary = []
            for p in list(grouped.keys())[:3]:
                metrics_str = ", ".join(grouped[p])
                edgar_summary.append(f"Period {p}: {metrics_str}")

            if edgar_summary:
                return "\n--- SEC EDGAR OFFICIAL FILINGS (Cached) ---\n" + "\n".join(edgar_summary)
        except Exception as e:
            print(f"Error fetching EDGAR context: {e}")

        return ""

    async def get_response(self, user_query: str) -> dict:
        """Generate an informed assistant response for a user query.

        Optimized pipeline:
        - Issue #1: Sync calls wrapped in asyncio.to_thread
        - Issue #2: Independent fetches run in parallel via asyncio.gather
        - Issue #3: Uses consolidated get_full_analysis (single yfinance call)
        - Issue #7: FRED data cached in memory
        - Issue #8: Unified ASSET_MAP for ticker + readable name lookup
        """

        # --- Pre-detect ticker from known asset names ---
        query_lower = user_query.lower()
        pre_detected_ticker = None
        pre_detected_name = None
        for name, info in ASSET_MAP.items():
            if name in query_lower:
                pre_detected_ticker = info["ticker"]
                pre_detected_name = info["name"]
                break

        # --- Stage 1: Extraction of ticker/intent ---
        extraction_prompt = f"""
        Analyze this user query: "{user_query}"

        Task: Extract the financial ticker symbol. This can be a stock, commodity, index, crypto, or forex pair.
        Examples:
        - "Apple stock" → "AAPL"
        - "Brent oil prices" → "BZ=F"
        - "Gold price" → "GC=F"
        - "Bitcoin" → "BTC-USD"
        - "S&P 500" → "SPY"

        Output format (JSON only):
        {{"ticker": "AAPL" or null, "intent": "analysis" or "chat"}}
        """

        try:
            extraction_resp = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=extraction_prompt,
                config={'response_mime_type': 'application/json'}
            )
            data = json.loads(extraction_resp.text)
            detected_ticker = data.get("ticker")
        except Exception:
            detected_ticker = None

        # Fallback to pre-detected ticker from ASSET_MAP
        if not detected_ticker and pre_detected_ticker:
            detected_ticker = pre_detected_ticker

        # --- Stage 2: Context enrichment ---
        context_data = ""
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M")

        if detected_ticker:
            detected_ticker = detected_ticker.upper().strip()

            # Get readable name from unified map
            readable_name = TICKER_TO_NAME.get(detected_ticker, detected_ticker)

            # News search query uses the user's original intent
            news_query = f"{readable_name} {user_query}" if readable_name != user_query else f"{readable_name} news"

            # Issue #1 + #2 + #3: Parallel async execution of ALL data fetches
            # get_full_analysis does ONE yfinance call for fund+tech+patterns
            # search_news and get_vix run in parallel alongside it
            analysis_result, news_data, vix_val, edgar_context = await asyncio.gather(
                asyncio.to_thread(finance_engine.get_full_analysis, detected_ticker),
                asyncio.to_thread(search_engine.search_news, news_query),
                asyncio.to_thread(finance_engine.get_vix),
                asyncio.to_thread(self._get_edgar_context, detected_ticker),
            )

            if analysis_result:
                fund_data = analysis_result["fund"]
                tech_data = analysis_result["tech"]
                visual_patterns = analysis_result["patterns"]

                context_data = f"""
                --- GLOBAL MACRO ---
                VIX: {vix_val}

                --- LIVE MARKET DATA (Source: YFinance) ---
                Date: {current_date}
                Ticker: {detected_ticker}
                Current Price: {fund_data.get('price')} {fund_data.get('currency')}
                Sector: {fund_data.get('sector')}

                --- TECHNICAL INDICATORS ---
                RSI (14): {tech_data.get('rsi') if tech_data else 'N/A'}
                Trend (SMA200): {tech_data.get('trend') if tech_data else 'N/A'}
                Visual Patterns: {visual_patterns}

                {edgar_context}
                {news_data}
                """
            else:
                context_data = f"WARNING: Could not fetch real-time data for {detected_ticker}.\n{edgar_context}"

        # Issue #7: Use cached FRED context (no DB hit on every message)
        fred_context = self._get_fred_context()

        # Trends and flights are already cached in memory by background tasks
        trends_context = trends_engine.get_summary()
        flights_context = flight_tracker.get_summary()

        # Append global context
        context_data += f"\n{fred_context}\n\n{trends_context}\n\n{flights_context}"

        # --- Stage 3: Final prompt assembly and generation ---
        full_prompt = f"""
        Current Date: {current_date}

        {FINANCE_PROMPT}

        CONTEXT DATA:
        {context_data}

        USER QUERY: {user_query}
        """

        try:
            final_resp = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=full_prompt
            )
            return {
                "text": final_resp.text,
                "ticker": detected_ticker
            }
        except Exception as e:
            return {"text": f"System Error: {e}", "ticker": None}


ai_engine = AIService()