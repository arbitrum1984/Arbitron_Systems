"""Pentagon Pizza Index Service.

Generates realistic, deterministic busyness data for pizza locations
near key government buildings (Pentagon, White House, CIA HQ).

Uses pre-defined hourly busyness patterns per location with
deterministic noise that changes every 5 minutes.

Note: Google Search scraping was removed because Google aggressively
blocks all automated requests (httpx, Playwright, stealth) with CAPTCHAs.
If real-time data is needed, consider a paid API (SerpApi, Outscraper,
or Google Places API with billing).
"""

import hashlib
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PizzaIntel")

# Unique hourly busyness patterns per location (hours 0-23, values 0-100%).
# Each location has distinct weekday/weekend profiles based on real-world
# ordering behavior near government facilities.
LOCATION_PATTERNS = {
    "pentagon": {
        # Pentagon: Sharp lunch spike (military/gov workers order en masse),
        # moderate evening, rapid drop-off after 20:00.
        "weekday": [
            3, 2, 1, 1, 1, 2, 5, 12, 20, 25,
            45, 80, 95, 70, 40, 30, 35, 55, 72, 65,
            40, 22, 12, 5,
        ],
        "weekend": [
            5, 3, 2, 1, 1, 1, 2, 5, 10, 18,
            30, 50, 65, 60, 50, 45, 50, 60, 70, 65,
            50, 35, 20, 10,
        ],
    },
    "wh_house": {
        # White House: Double peak — lunch + late dinner (lobbyists and
        # staffers working late), high evening activity, slow decline.
        "weekday": [
            8, 5, 3, 2, 2, 3, 5, 8, 15, 30,
            50, 70, 85, 65, 45, 40, 50, 75, 90, 95,
            88, 70, 45, 20,
        ],
        "weekend": [
            10, 8, 5, 3, 2, 2, 3, 5, 10, 20,
            35, 55, 70, 75, 65, 55, 50, 60, 75, 80,
            75, 60, 40, 18,
        ],
    },
    "cia_hq": {
        # CIA/Langley: Early morning activity (early birds), strong lunch
        # peak, sharp evening drop-off (suburban location, people leave).
        "weekday": [
            2, 1, 1, 1, 2, 5, 15, 30, 45, 40,
            50, 75, 90, 65, 45, 35, 30, 40, 50, 35,
            20, 10, 5, 3,
        ],
        "weekend": [
            3, 2, 1, 1, 1, 2, 5, 10, 20, 30,
            45, 60, 72, 68, 55, 45, 40, 50, 55, 42,
            28, 15, 8, 4,
        ],
    },
}


class PizzaService:
    """Service that generates Pentagon Pizza Index data.

    Provides deterministic busyness simulation for pizza locations
    near key US government buildings. Data changes every 5 minutes
    and follows realistic weekday/weekend patterns.
    """

    def __init__(self) -> None:
        """Initializes the pizza service with target locations."""
        self.targets = [
            {
                "id": "pentagon",
                "name": "DOMINO'S (PENTAGON)",
                "query": "Domino's Pizza 2800 S Joyce St, Arlington, VA",
            },
            {
                "id": "wh_house",
                "name": "PAPA JOHN'S (WHITE HOUSE)",
                "query": "Papa John's Pizza 1300 L St NW, Washington, DC",
            },
            {
                "id": "cia_hq",
                "name": "DOMINO'S (LANGLEY/CIA)",
                "query": "Domino's Pizza 1432 Chain Bridge Rd, McLean, VA",
            },
        ]

    def _get_deterministic_noise(self, seed_str: str, range_val: int = 10) -> int:
        """Generates deterministic noise from a seed string.

        Same seed always produces the same result. The seed typically
        includes a time bucket so the value changes every 5 minutes.

        Args:
            seed_str: String used to seed the hash.
            range_val: Maximum absolute deviation from zero.

        Returns:
            An integer in the range [-range_val, range_val].
        """
        h = hashlib.md5(seed_str.encode()).hexdigest()
        return (int(h[:8], 16) % (range_val * 2 + 1)) - range_val

    def _generate_realistic_data(self, target_id: str, now: datetime) -> Dict:
        """Generates realistic busyness data for a given location.

        Uses pre-defined hourly patterns unique to each location,
        with deterministic noise that changes every 5 minutes.

        Args:
            target_id: Location identifier (e.g. "pentagon").
            now: Current datetime for time-based calculations.

        Returns:
            Dict with keys: "live" (current busyness with noise),
            "typical" (baseline for this hour), "historical" (24-hour array).
        """
        is_weekend = now.weekday() >= 5
        pattern_key = "weekend" if is_weekend else "weekday"

        # Get the unique pattern for this specific location.
        location = LOCATION_PATTERNS.get(target_id, LOCATION_PATTERNS["pentagon"])
        historical = list(location[pattern_key])

        current_hour = now.hour
        typical = historical[current_hour]

        # Deterministic noise for the "live" value (changes every 5 min).
        time_bucket = now.strftime("%Y-%m-%d-%H") + f"-{now.minute // 5}"
        noise_seed = f"{target_id}:{time_bucket}"
        noise = self._get_deterministic_noise(noise_seed, range_val=12)

        live = max(0, min(100, typical + noise))

        return {
            "live": live,
            "typical": typical,
            "historical": historical,
        }

    def _calculate_spike(self, live: int, typical: int) -> tuple:
        """Calculates the anomaly percentage (Spike Index).

        Args:
            live: Current real-time busyness value (0-100).
            typical: Expected baseline busyness for this hour (0-100).

        Returns:
            A tuple of (spike_pct, status) where spike_pct is the
            percentage deviation and status is one of:
            "CRITICAL SPIKE", "BUSY", "QUIET", or "NOMINAL".
        """
        if typical == 0:
            typical = 1
        diff = live - typical
        spike_pct = int((diff / typical) * 100)

        if spike_pct > 100:
            status = "CRITICAL SPIKE"
        elif spike_pct > 40:
            status = "BUSY"
        elif spike_pct < -20:
            status = "QUIET"
        else:
            status = "NOMINAL"

        return spike_pct, status

    async def check_index(self) -> list:
        """Runs the main index check across all target locations.

        Iterates over all configured pizza locations, generates
        deterministic busyness data, and calculates spike indices.

        Returns:
            A list of dicts, one per location, each containing:
            "name", "status", "spike_pct", "live_value",
            "historical" (24-element list), "current_hour", "is_real".
        """
        results = []
        now = datetime.now()
        current_hour = now.hour

        for target in self.targets:
            logger.info("Generating data for %s...", target["name"])

            data = self._generate_realistic_data(target["id"], now)
            live = data["live"]
            typical = data["typical"]
            spike_pct, status = self._calculate_spike(live, typical)

            results.append({
                "name": target["name"],
                "status": status,
                "spike_pct": spike_pct,
                "live_value": live,
                "historical": data["historical"],
                "current_hour": current_hour,
                "is_real": False,
            })

        return results


pizza_service = PizzaService()