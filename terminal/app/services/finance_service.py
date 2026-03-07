"""Finance service utilities for retrieving market data and indicators.

This module contains a small service class that exposes methods to
fetch current ticker metadata, compute simple technical indicators,
and download historical price data configured for compatibility with
modern versions of `yfinance`. Returned structures are pandas objects
or plain Python dictionaries intended for consumption by higher-level
services in the application.

The implementation is defensive: network or parsing failures return
`None` to signal the caller that data are unavailable. Consumers
should handle `None` accordingly.
"""

import yfinance as yf
import pandas as pd
import numpy as np


class FinanceService:
    """Service for retrieving basic market data and computing indicators.

    Instances of this class provide convenience methods around
    `yfinance` to obtain ticker metadata, compute common technicals
    (e.g., RSI, SMA trend comparison), and download cleaned
    historical data suitable for quantitative processing.
    """

    def get_full_analysis(self, ticker: str) -> dict | None:
        """Consolidated single-pass analysis of a ticker.

        Downloads data ONCE and computes all metrics (fundamentals,
        technicals, patterns) from the same data to avoid redundant
        HTTP requests to Yahoo Finance.

        Returns:
            dict | None: Combined analysis dict or None on failure.
        """
        try:
            stock = yf.Ticker(ticker)
            price = stock.fast_info.last_price
            info = stock.info

            fund_data = {
                "price": round(price, 2) if price else "N/A",
                "currency": info.get('currency', 'USD'),
                "sector": info.get('sector', 'N/A'),
                "pe_ratio": info.get('trailingPE', 'N/A'),
                "summary": info.get('longBusinessSummary', 'No summary available.')
            }
        except Exception:
            return None

        # Download historical data ONCE for both technicals and patterns
        hist = self.get_historical_data(ticker)

        tech_data = None
        if hist is not None and not hist.empty:
            try:
                last_close = hist['Close'].iloc[-1]
                last_rsi = hist['RSI'].iloc[-1]
                sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]

                trend = "Bullish (Uptrend)" if last_close > sma_200 else "Bearish (Downtrend)"

                tech_data = {
                    "rsi": round(last_rsi, 2),
                    "trend": trend,
                    "price": round(last_close, 2)
                }
            except Exception:
                tech_data = None

        # Pattern detection from same historical data
        patterns = self._detect_patterns_from_df(hist)

        return {
            "fund": fund_data,
            "tech": tech_data,
            "patterns": patterns,
        }

    def get_ticker_data(self, ticker: str):
        """Retrieve current ticker metadata and basic statistics."""
        try:
            stock = yf.Ticker(ticker)
            price = stock.fast_info.last_price
            info = stock.info

            return {
                "price": round(price, 2) if price else "N/A",
                "currency": info.get('currency', 'USD'),
                "sector": info.get('sector', 'N/A'),
                "pe_ratio": info.get('trailingPE', 'N/A'),
                "summary": info.get('longBusinessSummary', 'No summary available.')
            }
        except Exception:
            return None

    def calculate_technicals(self, ticker: str):
        """Compute a small set of technical indicators for the ticker."""
        try:
            hist = self.get_historical_data(ticker)
            if hist is None or hist.empty:
                return None

            last_close = hist['Close'].iloc[-1]
            last_rsi = hist['RSI'].iloc[-1]
            sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]

            trend = "Bullish (Uptrend)" if last_close > sma_200 else "Bearish (Downtrend)"

            return {
                "rsi": round(last_rsi, 2),
                "trend": trend,
                "price": round(last_close, 2)
            }
        except Exception:
            return None

    def get_historical_data(self, ticker: str, period: str = "1y"):
        """Download and prepare historical daily price data."""
        try:
            df = yf.download(
                ticker,
                period=period,
                interval="1d",
                progress=False,
                auto_adjust=True,
                multi_level_index=False
            )

            if df.empty:
                return None

            # Compute 14-period RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))

            df = df.dropna()

            return df[['Close', 'Volume', 'RSI']]

        except Exception as e:
            print(f"History Error ({ticker}): {e}")
            return None

    def _detect_patterns_from_df(self, df) -> str:
        """Detect patterns from an existing DataFrame (no extra download)."""
        try:
            if df is None or len(df) < 5:
                return "No definitive visual patterns detected in recent data."

            p_list = []
            last_close = df['Close'].iloc[-1]
            if last_close > df['Close'].iloc[-5]:
                p_list.append("Short-term bullish momentum")
            elif last_close < df['Close'].iloc[-5]:
                p_list.append("Short-term bearish pressure")

            avg_vol = df['Volume'].mean()
            last_vol = df['Volume'].iloc[-1]
            if last_vol > avg_vol * 1.5:
                p_list.append("High volume spike detected")

            return "; ".join(p_list) if p_list else "Neutral price action."
        except Exception:
            return "Unable to analyze visual patterns."

    def detect_patterns(self, ticker: str):
        """Perform simple text-based technical pattern detection."""
        df = self.get_historical_data(ticker, period="1mo")
        return self._detect_patterns_from_df(df)

    def get_vix(self):
        """Fetch the current VIX (Volatility Index) value."""
        try:
            vix = yf.Ticker("^VIX")
            price = vix.fast_info.last_price
            return round(price, 2) if price else "N/A"
        except Exception:
            return "N/A"


finance_engine = FinanceService()