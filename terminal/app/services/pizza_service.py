"""Pentagon Pizza Index Service.

Fetches cached scrape results from the pizza_scraper microservice.
"""

import logging
from typing import List

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PizzaIntel")

SCRAPER_URL = "http://pizza_scraper:8002/status"


class PizzaService:
    """Reads Pentagon Pizza Index data from the pizza_scraper service."""

    def __init__(self) -> None:
        self._cached_results: list = []

    async def check_index(self) -> list:
        """Fetch the latest scrape results from the scraper service."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(SCRAPER_URL)
                if r.status_code == 200:
                    self._cached_results = r.json()
                    logger.info(
                        "Fetched %d locations from scraper.",
                        len(self._cached_results),
                    )
                else:
                    logger.warning("Scraper returned %d", r.status_code)
        except Exception as e:
            logger.warning("Scraper unreachable: %s", e)

        return self._cached_results

    def get_cached(self) -> list:
        """Return last fetched results instantly."""
        return self._cached_results


pizza_service = PizzaService()