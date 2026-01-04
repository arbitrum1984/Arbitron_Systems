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

    def get_ticker_data(self, ticker: str):
        """Retrieve current ticker metadata and basic statistics.

        This method uses `yfinance.Ticker` to obtain a fast price value
        and supplemental metadata from the `info` mapping. The
        returned dictionary contains rounded price and several common
        informational fields; if the lookup fails the method returns
        `None`.

        Args:
            ticker (str): The ticker symbol to query (e.g. "AAPL").

        Returns:
            dict | None: A dictionary with keys `price`, `currency`,
                `sector`, `pe_ratio`, and `summary`, or `None` on
                failure.
        """
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
            # For reliability in higher-level code, failures return None
            return None

    def calculate_technicals(self, ticker: str):
        """Compute a small set of technical indicators for the ticker.

        The method downloads historical data, computes the latest RSI
        and a simple 200-day SMA to produce a nominal trend label.
        If historical data are unavailable the method returns `None`.

        Args:
            ticker (str): The ticker symbol to analyze.

        Returns:
            dict | None: A dictionary containing `rsi` (float),
                `trend` (str) and `price` (float), or `None` if the
                computation cannot be completed.
        """
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
        """Download and prepare historical daily price data.

        The function downloads daily OHLC data using `yfinance.download`
        with `auto_adjust=True` to account for dividends and splits
        and flattens multi-index output for compatibility. It computes
        a 14-period RSI and returns a pared-down DataFrame containing
        `Close`, `Volume`, and `RSI`. On error or if the result is
        empty the function returns `None`.

        Args:
            ticker (str): The market ticker symbol to download.
            period (str): The period string passed to `yfinance` (e.g.
                "1y", "6mo"). Defaults to "1y".

        Returns:
            pandas.DataFrame | None: DataFrame with columns `Close`,
                `Volume`, and `RSI`, indexed by date, or `None` on
                failure or when no data are available.
        """
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


finance_engine = FinanceService()