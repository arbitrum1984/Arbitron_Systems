"""Quantitative visualization utilities for Arbitron Systems.

This module implements a small service that constructs a 3D
volatility/density surface for a given market ticker. The surface is
represented as a Plotly figure dictionary (plain Python structures)
suitable for JSON serialization and client-side rendering with
Plotly.js. The implementation depends on historical price and
indicator data provided by `app.services.finance_service.finance_engine`.

The primary responsibilities are:
 - Fetch historical data (price, RSI, volume).
 - Compute a kernel density estimate (KDE) weighted by traded volume.
 - Produce a styled Plotly surface plot and return it as a dict.

The functions return simple, serializable dictionaries; on error or
when input data is insufficient, a minimal placeholder figure is
returned so that callers can display a graceful message.
"""

import plotly.graph_objects as go
import numpy as np
from scipy.stats import gaussian_kde
import json
from app.services.finance_service import finance_engine


class QuantService:
    """Service responsible for generating quantitative charts.

    The class encapsulates logic to compute a volatility or density
    surface using historical market data. Instances are lightweight
    and stateless; the primary public method is
    `generate_volatility_surface`.
    """

    def generate_volatility_surface(self, ticker: str = "BTC-USD"):
        """Compute a 3D volatility/density surface for a ticker.

        The method performs the following steps:
        1. Retrieve historical data using `finance_engine.get_historical_data`.
        2. Validate that sufficient data points exist (minimum ~30).
        3. Construct a 2D grid over Price (X) and RSI (Y) and compute a
           volume-weighted KDE to produce Z values.
        4. Build a styled Plotly `Surface` and return the figure as a
           plain dictionary (no numpy objects) suitable for JSON.

        Args:
            ticker (str): The market ticker symbol to analyze. Defaults
                to "BTC-USD".

        Returns:
            dict: A Plotly figure represented as native Python objects
                (dictionaries and lists). If data are missing or an
                internal error occurs, a small placeholder figure
                dictionary is returned with an explanatory message.
        """
        # 1. Retrieve historical data
        df = finance_engine.get_historical_data(ticker)

        # If data are missing or too few rows, return a placeholder
        if df is None or len(df) < 30:
            return self._get_empty_chart(f"NO DATA FOR {ticker}")

        # 2. Prepare vectors: Price (X) and RSI (Y)
        x = df['Close'].values
        y = df['RSI'].values

        # Normalize volume to use as weights for the KDE so large
        # numeric volumes do not destabilize the estimator.
        weights = df['Volume'].values.astype(float)
        weights = weights / weights.max()

        try:
            # 3. Kernel Density Estimation (KDE) over a 40x40 grid
            xi, yi = np.mgrid[x.min():x.max():40j, y.min():y.max():40j]
            positions = np.vstack([xi.flatten(), yi.flatten()])
            values = np.vstack([x, y])

            kernel = gaussian_kde(values, weights=weights)
            zi = kernel(positions).reshape(xi.shape)

        except Exception as e:
            # On numerical errors, return a descriptive placeholder.
            print(f"Math Error: {e}")
            return self._get_empty_chart("MATH ERROR")

        # 4. Construct Plotly Surface, converting numpy arrays to lists
        fig = go.Figure(data=[go.Surface(
            z=zi.tolist(), x=xi.tolist(), y=yi.tolist(),
            colorscale='Jet',
            opacity=0.9,
            contours=dict(
                x=dict(show=True, project_x=True, color="#333"),
                y=dict(show=True, project_y=True, color="#333"),
                z=dict(show=True, project_z=True, usecolormap=True)
            )
        )])

        # 5. Design and camera configuration for professional display
        fig.update_layout(
            title='',
            autosize=True,
            margin=dict(l=0, r=0, b=0, t=0),
            scene=dict(
                xaxis=dict(title='', backgroundcolor="#000", gridcolor="#222", showbackground=True),
                yaxis=dict(title='', backgroundcolor="#000", gridcolor="#222", showbackground=True),
                zaxis=dict(title='', backgroundcolor="#000", gridcolor="#222", showbackground=True),
                bgcolor='#0d0d0d',
                camera=dict(eye=dict(x=1.6, y=1.6, z=0.6))
            ),
            paper_bgcolor='#0d0d0d',
            font=dict(color='#808080', family="Roboto Mono")
        )

        # Return serializable structure
        return fig.to_dict()

    def _get_empty_chart(self, msg: str):
        """Return a minimal placeholder Plotly figure with a message.

        The placeholder is used when there is insufficient data or
        when an internal computation fails. The returned object is a
        Plotly figure represented as native Python types.

        Args:
            msg (str): Message to display as the figure title.

        Returns:
            dict: A minimal Plotly figure serialized to Python dicts.
        """
        fig = go.Figure()
        fig.update_layout(
            title=dict(text=msg, y=0.5, x=0.5, xanchor='center', yanchor='middle'),
            paper_bgcolor='#0d0d0d',
            font=dict(color='#cf6679', family="Roboto Mono"),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig.to_dict()


quant_engine = QuantService()