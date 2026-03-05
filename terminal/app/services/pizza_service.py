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

    async def get_index(self) -> list:
        """Fetch the latest cached scrape results from the scraper service."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(SCRAPER_URL)
                if r.status_code == 200:
                    data = r.json()
                    return data
        except Exception as e:
            logger.warning("Scraper error: %s", e)
        return []

pizza_service = PizzaService()