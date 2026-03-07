"""Service for fetching Google Trends data and computing an economic stress index.

This model provides a wrapper around `pytrends` to fetch search interest
for various economic and lifestyle terms. It caches the data to avoid
rate limits from Google. The most important metric it computes is the
Consumer Stress Index: a ratio of distress terms versus luxury terms.
"""

from pytrends.request import TrendReq
import pandas as pd
import asyncio
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class TrendsService:
    def __init__(self):
        # We use standard requests without custom retries to avoid urllib3 compatibility issues
        self.pytrends = TrendReq(hl='en-US', tz=360)
        
        self._cached_summary = "Google Trends data currently initializing..."
        self._last_update = None
        self._historical_data = None
        
        # Terms that indicate economic worry
        self.distress_terms = ["payday loan", "recession", "unemployment"]
        # Terms that indicate disposable income
        self.luxury_terms = ["business class", "luxury watches", "fine dining"]

        # If pytrends completely fails due to Google blocking, we'll store the error state here
        self._is_blocked = False

    def _fetch_data_sync(self):
        """Synchronously fetch data from Google Trends. Intended to be run in a thread."""
        all_terms = self.distress_terms + self.luxury_terms
        
        # Pytrends allows max 5 terms per request, so we chunk them
        trends_data = {}
        historical_buffer = None
        
        try:
            for i in range(0, len(all_terms), 5):
                chunk = all_terms[i:i+5]
                self.pytrends.build_payload(chunk, cat=0, timeframe='today 1-m', geo='US', gprop='')
                df = self.pytrends.interest_over_time()
                
                if df.empty:
                    continue
                
                # Drop overlapping partial indicator to avoid DataFrame column explosion on join
                if 'isPartial' in df.columns:
                    df = df.drop(columns=['isPartial'])
                    
                # Store the mean interest over the last month, and the very last value
                for term in chunk:
                    if term in df.columns:
                        recent_val = df[term].iloc[-1]
                        mean_val = df[term].mean()
                        trends_data[term] = {"recent": float(recent_val), "mean": float(mean_val)}
                
                # Construct fresh historical data buffer for this run
                if historical_buffer is None:
                    historical_buffer = df.copy()
                else:
                    historical_buffer = historical_buffer.join(df, how='outer')
                    
            if historical_buffer is not None:
                self._historical_data = historical_buffer
                
            return trends_data
            
        except Exception as e:
            logger.error(f"Error fetching Google Trends data: {e}")
            self._is_blocked = True
            return None

    async def update_trends_background(self):
        """Update trends data in the background and compute the Consumer Stress Index."""
        logger.info("[Trends Service] Fetching new Google Trends data...")
        
        # Run the synchronous pytrends call in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        trends_data = await loop.run_in_executor(None, self._fetch_data_sync)
        
        if trends_data is None:
            if self._is_blocked:
                 self._cached_summary = "Google Trends API is currently returning 429 Too Many Requests. Data unavailable."
            return

        self._is_blocked = False
        
        distress_score = 0
        luxury_score = 0
        
        summary_lines = []
        summary_lines.append("--- GOOGLE TRENDS CONSUMER OUTLOOK ---")
        
        for term, data in trends_data.items():
            # Compare recent value vs the 1-month mean to see the trend
            trend_str = "RISING" if data["recent"] > data["mean"] * 1.05 else ("FALLING" if data["recent"] < data["mean"] * 0.95 else "FLAT")
            summary_lines.append(f"Trend '{term}': {trend_str} (Score: {data['recent']:.1f})")
            
            if term in self.distress_terms:
                distress_score += data["recent"]
            elif term in self.luxury_terms:
                luxury_score += data["recent"]
                
        # Calculate Stress Index
        if luxury_score == 0:
            stress_index = 100.0 # Max stress if literally 0 luxury searches
        else:
            # We normalize this somewhat. Ratio of distress to luxury.
            stress_index = (distress_score / luxury_score) * 50
            
        # Cap at 100
        stress_index = min(100.0, stress_index)
        
        index_str = f"\nConsumer Stress Index: {stress_index:.1f}/100"
        if stress_index < 30:
            index_str += " (Very Healthy, Consumers are spending on luxury)"
        elif stress_index < 60:
            index_str += " (Normal/Neutral)"
        elif stress_index < 80:
            index_str += " (Elevated Stress, Consumers searching for loans/help)"
        else:
            index_str += " (SEVERE STRESS, Panic search behavior detected)"
            
        summary_lines.append(index_str)
        
        self._cached_summary = "\n".join(summary_lines)
        self._last_update = datetime.now()
        
        logger.info(f"[Trends Service] Update complete. Index: {stress_index:.1f}/100")

    def get_summary(self) -> str:
        """Get the latest cached summary for the AI prompt."""
        return self._cached_summary
        
    def get_historical_data(self):
        """Return the raw timeseries data formatted for Plotly."""
        if self._historical_data is None or self._historical_data.empty:
            return {"error": "Data not yet initialized or unavailable"}
            
        # pytrends returns a DataFrame with DatetimeIndex and columns for each term
        # Convert to dictionary of lists for JSON serialization
        df = self._historical_data.reset_index()
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        
        result = {
            "dates": df['date'].tolist(),
            "distress": {},
            "luxury": {}
        }
        
        for term in self.distress_terms:
            if term in df.columns:
                result["distress"][term] = df[term].fillna(0).tolist()
                
        for term in self.luxury_terms:
            if term in df.columns:
                result["luxury"][term] = df[term].fillna(0).tolist()
                
        return result

trends_engine = TrendsService()
