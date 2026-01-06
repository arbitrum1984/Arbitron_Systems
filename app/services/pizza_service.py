"""
app.services.pizza_service
--------------------------------

Utility service that synthesizes or retrieves "popular times" style
occupancy data for a small set of predefined targets (pizza outlets).

The module provides `PizzaService`, which can either generate
realistic mock data for UI demonstrations or (optionally) call a
real-world search API such as SerpApi. The generated structure is
intentionally simple: a 24-element `historical` array, a `live_value`
for the current hour, and a derived `spike_pct` with a human-readable
`status` label.

Docstrings are written in a professional, academic tone and in
English. The implementation preserves existing synchronous and
asynchronous boundaries used by callers in the codebase.
"""

import httpx
import asyncio
import logging
import random
from datetime import datetime
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PizzaIntel")

# When True, return simulated/mock results; set to False to enable
# real API calls (implementation placeholder present in `get_real_data`).
USE_SIMULATION = True

class PizzaService:
    """
    Small helper service that returns either simulated or real
    popularity/occupancy data for a curated list of pizza outlets.

    The class exposes a minimal asynchronous API so that callers can
    integrate the service into event loops or background tasks.
    """

    def __init__(self):
        """
        Initialize network settings and a small target registry.

        The `api_key` and `base_url` are configured for SerpApi but the
        real-query path is left as a placeholder; `USE_SIMULATION`
        controls whether mock data is used.
        """
        self.api_key = settings.SERPAPI_API_KEY
        self.base_url = "https://serpapi.com/search.json"

        self.targets = [
            {"id": "pentagon", "name": "DOMINO'S (PENTAGON)", "query": "Domino's Pizza 2800 S Joyce St, Arlington, VA"},
            {"id": "wh_house", "name": "PAPA JOHN'S (WHITE HOUSE)", "query": "Papa John's Pizza 1300 L St NW, Washington, DC"},
            {"id": "cia_hq", "name": "DOMINO'S (LANGLEY/CIA)", "query": "Domino's Pizza 1432 Chain Bridge Rd, McLean, VA"}
        ]

    async def get_real_data(self, query: str):
        """
        Placeholder for a real SerpApi (or similar) query implementation.

        In production this coroutine would assemble a request to the
        configured `base_url` with appropriate parameters and the
        service API key, then parse and normalise the response into the
        same structure produced by `generate_mock_data`.

        Args:
            query (str): Human-readable query string (e.g. address or
                place name) to pass to the search API.

        Returns:
            Optional[dict]: Normalized occupancy data or `None` if the
            feature is not implemented or the request fails.
        """
        # Implementation intentionally omitted for the MVP; return None
        # so callers can rely on the simulation path.
        return None

    def generate_mock_data(self, target_name: str) -> dict:
        """
        Generate synthetic "popular times" style data for a single target.

        The generated payload contains a 24-element `historical` list
        (values 0-100), a `live_value` for the current hour, a
        computed `spike_pct` and a textual `status` classification.

        A deliberate anomaly is introduced for targets whose name
        contains the token "PENTAGON" to demonstrate spike handling
        in the UI.

        Args:
            target_name (str): Display name for the target; used to
                determine anomalous behaviour for demo purposes.

        Returns:
            dict: Normalized occupancy structure with keys: `name`,
            `status`, `spike_pct`, `live_value`, `historical`, and
            `current_hour`.
        """

        # 1. Build a realistic-looking historical workload curve
        historical = []
        for h in range(24):
            if 0 <= h < 10:
                base = random.randint(5, 15)
            elif 10 <= h < 16:
                base = random.randint(20, 50)
            elif 16 <= h < 20:
                base = random.randint(50, 80)  # evening peak
            else:
                base = random.randint(10, 30)
            historical.append(base)

        # 2. Current hour and live measurement
        current_hour = datetime.now().hour

        # 3. Live value: inject an anomaly for the Pentagon target
        if "PENTAGON" in target_name:
            live_value = historical[current_hour] * 4
            if live_value > 100:
                live_value = 100
        else:
            live_value = historical[current_hour] * random.uniform(0.9, 1.1)

        # 4. Compute spike percentage and a status label
        baseline = historical[current_hour] or 1
        spike_pct = int(((live_value - baseline) / baseline) * 100)

        if spike_pct > 100:
            status = "SPIKE"
        elif spike_pct > 20:
            status = "BUSY"
        elif spike_pct < -20:
            status = "QUIET"
        else:
            status = "NOMINAL"

        return {
            "name": target_name,
            "status": status,
            "spike_pct": spike_pct,
            "live_value": int(live_value),
            "historical": historical,
            "current_hour": current_hour,
        }

    async def check_index(self) -> list:
        """
        Return occupancy information for all configured targets.

        Depending on the `USE_SIMULATION` flag, the function either
        synthesizes mock results via `generate_mock_data` or calls the
        placeholder `get_real_data` coroutine. The returned value is a
        list of normalized occupancy objects.

        Returns:
            list: A list of dictionaries, each conforming to the
                structure produced by `generate_mock_data`.
        """
        results = []

        for target in self.targets:
            if USE_SIMULATION:
                data = self.generate_mock_data(target["name"])
                results.append(data)
            else:
                # Real query path intentionally left as a future task.
                pass

        return results

pizza_service = PizzaService()