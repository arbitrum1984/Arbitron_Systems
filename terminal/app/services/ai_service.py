"""AI service integrating model calls, data enrichment, and response generation.

This module wraps a lightweight pipeline that interprets a user query,
optionally enriches it with market data and news, and generates a
final textual response using a generative model backend. The pipeline
is intentionally pragmatic: it first attempts to extract a ticker and
intent, then conditionally aggregates structured context (finance
technicals and news) before prompting the model for the final answer.

The module depends on:
 - `google.genai` for model inference (async client usage).
 - `app.services.finance_service.finance_engine` for market data.
 - `app.services.search_service.search_engine` for simple news search.

Errors in external dependencies are handled conservatively; the
service returns explanatory text and a `None` ticker when failures
occur so callers can render an appropriate UI fallback.
"""

import json
from datetime import datetime
from google import genai
from app.core.config import settings
from app.core.prompts import FINANCE_PROMPT

# Tools and auxiliary services used to enrich the model context
from app.services.finance_service import finance_engine
from app.services.search_service import search_engine


class AIService:
    """High-level AI orchestration service.

    The service manages a configured generative model client and
    exposes an asynchronous `get_response` method that implements a
    three-stage pipeline: extraction, enrichment, and final
    generation. The constructor validates required configuration and
    initializes the model client.
    """

    def __init__(self):
        """Initialize the service and validate configuration.

        Raises:
            ValueError: If the required model API key is not configured.
        """
        if not settings.GEMINI_API_KEY:
            raise ValueError("API Key missing")

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = "gemini-2.5-flash-lite"

    async def get_response(self, user_query: str) -> dict:
        """Generate an informed assistant response for a user query.

        The method implements a pragmatic pipeline with three stages:

        1. Extraction: ask the model to return structured JSON that
           contains an extracted `ticker` and an `intent` label.
        2. Enrichment: if a ticker is detected, gather technical
           indicators, basic company/fundamental data, and recent
           news to build a contextual block that is passed to the
           final prompt.
        3. Generation: request the model to produce the final answer
           using the assembled context and application prompts.

        Args:
            user_query (str): The raw text issued by the user.

        Returns:
            dict: A mapping with keys `text` (the assistant response
                as string) and `ticker` (the detected ticker or None).

        Notes:
            - Network or model errors are caught; in error cases the
              method returns a dictionary with an explanatory `text`
              and `ticker` set to `None`.
            - The extraction step asks the model to produce JSON and
              expects to parse it; failures in parsing fall back to
              `detected_ticker = None`.
        """

        # --- Stage 1: Extraction of ticker/intent ---
        extraction_prompt = f"""
        Analyze this user query: "{user_query}"

        Task: Extract the stock ticker symbol if a company is mentioned.

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
            # If extraction fails, proceed without a detected ticker
            detected_ticker = None

        # --- Stage 2: Context enrichment (conditional on ticker) ---
        context_data = ""
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M")

        if detected_ticker:
            detected_ticker = detected_ticker.upper().strip()

            # Technical indicators and fundamental data
            tech_data = finance_engine.calculate_technicals(detected_ticker)
            fund_data = finance_engine.get_ticker_data(detected_ticker)

            # Recent news search
            news_data = search_engine.search_news(f"{detected_ticker} stock news")
            
            # --- EDGAR DATA INJECTION ---
            edgar_context = ""
            try:
                from app.database import crud
                facts = crud.get_company_facts(detected_ticker)
                
                if facts:
                    # Filter for Annual (10-K) data for key metrics
                    # Define key tags we want to feed the AI
                    KEY_TAGS = [
                        # Revenue variants
                        "Revenues", 
                        "RevenueFromContractWithCustomer", 
                        "RevenueFromContractWithCustomerExcludingAssessedTax", # AAPL specific
                        "Revenue",
                        # Net Income variants
                        "NetIncomeLoss", 
                        "ProfitLoss",
                        "NetInformation",
                        # Operating Income
                        "OperatingIncomeLoss",
                        # EPS
                        "EarningsPerShareBasic",
                        # Balance Sheet
                        "Assets", 
                        "Liabilities", 
                        "StockholdersEquity",
                        "CashAndCashEquivalents",
                        "CashAndCashEquivalentsAtCarryingValue" 
                    ]

                    # Filter: Must be 10-K/10-Q AND match one of our key tags
                    relevant_facts = [
                        f for f in facts 
                        if (f['form'] == '10-K' or f['form'] == '10-Q') 
                        and any(tag in f['tag'] for tag in KEY_TAGS)
                    ]
                    
                    # Sort recent first
                    relevant_facts.sort(key=lambda x: x['period'], reverse=True)
                    
                    # Human-readable label map
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

                    # Group by period
                    grouped = {}
                    for f in relevant_facts:
                        p = f['period']
                        if p not in grouped: grouped[p] = []
                        
                        # Use human label if available, else raw tag
                        raw_tag = f['tag']
                        label = LABELS.get(raw_tag, raw_tag)
                        
                        # Clean value (billions/millions for readability could be good, but raw numbers are safer for AI math)
                        entry = f"{label}: {f['value']} {f['unit']}"
                        
                        # Simple deduplication
                        if not any(entry.startswith(label + ":") for entry in grouped[p]):
                            grouped[p].append(entry)
                    
                    # Take top 3 periods
                    edgar_summary = []
                    for p in list(grouped.keys())[:3]:
                        # Join ALL relevant metrics for the period (we filtered them, so they are all important)
                        metrics_str = ", ".join(grouped[p]) 
                        edgar_summary.append(f"Period {p} ({grouped[p][0].split(':')[0] if grouped[p] else 'Report'}): {metrics_str}")
                    
                    if edgar_summary:
                        edgar_context = "\n--- SEC EDGAR OFFICIAL FILINGS (Cached) ---\n" + "\n".join(edgar_summary)
            except Exception as e:
                print(f"Error fetching EDGAR context: {e}")
            # ---------------------------

        # --- FRED (MACRO) CONTEXT INJECTION (Independent of Ticker) ---
        fred_context = ""
        try:
            from app.database import crud
            # Always load "important" series if they are in the DB
            fred_series_ids = crud.get_saved_fred_series() 
            
            if fred_series_ids:
                fred_summary = []
                for sid in fred_series_ids:
                    # Get last point
                    obs = crud.get_fred_observations(sid)
                    if obs:
                        last_pt = obs[-1]
                        fred_summary.append(f"{sid}: {last_pt['value']} (as of {last_pt['date']})")
                
                if fred_summary:
                    fred_context = "\n--- MACROECONOMIC DATA (Official Cached) ---\n" + "\n".join(fred_summary)

        except Exception as e:
            print(f"Error fetching FRED context: {e}")
        # --------------------------------------

        if detected_ticker and fund_data:
            # --- TEXT-BASED VISUAL PATTERN DETECTION ---
            visual_patterns = finance_engine.detect_patterns(detected_ticker)
            
            # --- GLOBAL VIX DATA FETCH ---
            vix_val = finance_engine.get_vix()

            # Assemble Context
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
        elif detected_ticker:
             context_data = f"WARNING: Could not fetch real-time data for {detected_ticker}.\n{edgar_context}"
        
        # Append FRED context globally
        context_data += f"\n{fred_context}"

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