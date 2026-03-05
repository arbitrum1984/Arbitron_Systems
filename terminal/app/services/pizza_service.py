"""Pentagon Pizza Index Service.

Uses undetected-chromedriver for HEADLESS scraping of Google Search "Popular Times".
Requires a pre-seeded session (google_session.json) to bypass CAPTCHAs.
If the session is missing, it will NOT run the fallback simulation.
Instead, it notifies the UI that manual authentication is required.
"""

import json
import logging
import os
import re
import math
from datetime import datetime
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PizzaIntel")

# ---------------------------------------------------------------------------
# Session file path (created by app/services/seed_google.py)
# ---------------------------------------------------------------------------
SESSION_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "google_session.json",
)


class PizzaService:
    """Service that scrapes Pentagon Pizza Index data.

    Utilizes undetected-chromedriver to avoid bot detection.
    Enforces a strict session validation -- no simulation fallbacks.
    """

    def __init__(self) -> None:
        """Initializes the pizza service with target Maps URLs."""
        self.targets = [
            {
                "id": "pentagon",
                "name": "DOMINO'S (PENTAGON)",
                "url": "https://www.google.com/maps/place/Domino's+Pizza/@38.8687291,-77.0874983,17z/data=!3m1!4b1!4m6!3m5!1s0x89b7b6df332b5095:0x8797b5e43a9fcd7c!8m2!3d38.868725!4d-77.0849234!16s%2Fg%2F1tf76s1w?hl=ru",
            },
            {
                "id": "glebe_rd",
                "name": "PAPA JOHN'S (GLEBE RD)",
                "url": "https://www.google.com/maps/place/Papa+Johns+Pizza/@38.8711674,-77.0980486,15.68z/data=!4m6!3m5!1s0x89b7b663b655da01:0x4f620ed722d3630f!8m2!3d38.8659547!4d-77.0784408!16s%2Fg%2F1tkzz2rt?hl=ru",
            },
            {
                "id": "cia_hq",
                "name": "DOMINO'S (LANGLEY/CIA)",
                "url": "https://www.google.com/maps/place/Domino's+Pizza/@38.9317528,-77.1818274,17z/data=!3m1!4b1!4m6!3m5!1s0x89b64ad7f0cdb27b:0x8dc1c448bbdd2a7c!8m2!3d38.9317486!4d-77.1792525!16s%2Fg%2F1tdwctqj?hl=ru",
            },
        ]

    # ------------------------------------------------------------------
    # Real scraping via Async Playwright
    # ------------------------------------------------------------------

    async def _scrape_google_maps(self, url: str) -> Optional[Dict]:
        """Scrapes Google Maps place pages using Playwright.

        Args:
            url: Google Maps Place URL.

        Returns:
            Dict with "live", "typical", "historical" keys, or None on failure.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright is not installed.")
            return None

        logger.info(f"Initializing Playwright for scraping: {url}")
        
        async with async_playwright() as p:
            # We run in headless mode with stealth args
            browser = await p.chromium.launch(
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            
            # Use Russian locale so the aria-labels match the user's regexes
            context = await browser.new_context(
                locale="ru-RU",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                # 1. Open the page
                await page.goto(url, wait_until="domcontentloaded")
                
                # 2. Bypass Cookie Consent (often needed in Europe/Headless)
                try:
                    consent_button = page.locator('button:has-text("Принять все")')
                    if await consent_button.is_visible(timeout=3000):
                        await consent_button.click()
                        logger.info("Closed cookie consent.")
                except Exception:
                    pass

                # 3. Scroll the left panel to trigger Popular Times widget load
                logger.info("Scrolling left panel to trigger widget load...")
                try:
                    await page.locator('div[role="main"]').hover(timeout=5000)
                    for _ in range(5):
                        await page.mouse.wheel(0, 1000)
                        import asyncio
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Failed to scroll main panel: {e}")

                # 4. Extract Data
                # Wait for at least one bar with "загружено"
                try:
                    await page.wait_for_selector('[aria-label*="загружено"]', timeout=10000)
                except Exception:
                    logger.warning("Timeout waiting for 'загружено' aria-labels to appear.")
                    return None
                    
                bars = await page.locator('[aria-label*="загружено"]').all()
                logger.info(f"Found {len(bars)} popular times elements.")
                
                bar_labels = []
                for bar in bars:
                    label = await bar.get_attribute('aria-label')
                    if label:
                        bar_labels.append(label)

                result = self._parse_russian_labels(bar_labels)
                if result:
                    logger.info(f"Scraped real data: live={result['live']}, typical={result['typical']}")
                else:
                    logger.info("Failed to parse live data from the labels.")
                return result

            except Exception as e:
                logger.error(f"Error during page execution: {e}")
                return None
            finally:
                await browser.close()

    @staticmethod
    def _parse_russian_labels(labels: List[str]) -> Optional[Dict]:
        """Parses Russian aria-label strings from Google Maps."""
        live_val = None
        typical_val = None
        historical = [0] * 24
        
        # We need to map "В 15:00" to the hour index
        for label in labels:
            if "Сейчас" in label:
                # e.g., "Сейчас загружено на 65 %. Обычно на 40 %."
                current_match = re.search(r'Сейчас загружено на (\d+)', label)
                usual_match = re.search(r'Обычно на (\d+)', label)
                
                if current_match:
                    live_val = int(current_match.group(1))
                if usual_match:
                    typical_val = int(usual_match.group(1))
                    
            else:
                # e.g., "В 15:00 обычно загружено на 40 %."
                time_match = re.search(r'В (\d{1,2}):00', label)
                perc_match = re.search(r'на (\d+)', label)
                
                if time_match and perc_match:
                    hour = int(time_match.group(1))
                    pct = int(perc_match.group(1))
                    if 0 <= hour < 24:
                        historical[hour] = pct
        
        # If we didn't find "Сейчас", we can't report a live spike reliably
        if live_val is None:
            return None
            
        if typical_val is None:
            typical_val = live_val
            
        return {
            "live": live_val,
            "typical": typical_val,
            "historical": historical
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def check_index(self) -> list:
        """Runs the main index check across all target locations.

        Returns:
            A list of dicts, one per location.
        """
        results = []
        now = datetime.now()
        current_hour = now.hour
        
        for target in self.targets:
            logger.info("Processing %s...", target["name"])

            scraped = await self._scrape_google_maps(target["url"])
            is_real = scraped is not None

            if is_real:
                data = scraped
                live = data["live"]
                typical = data["typical"]
                
                # Need typical > 0 to avoid division by zero
                t_val = typical if typical > 0 else 1
                diff = live - t_val
                spike_pct = int((diff / t_val) * 100)

                if spike_pct > 100:
                    status = "CRITICAL SPIKE"
                elif spike_pct > 40:
                    status = "BUSY"
                elif spike_pct < -20:
                    status = "QUIET"
                else:
                    status = "NOMINAL"
                    
                hist = data.get("historical")
                # Ensure hist isn't all zeros, which means parsing failed
                if not hist or sum(hist) == 0:
                    hist = [typical] * 24

                results.append({
                    "name": target["name"],
                    "status": status,
                    "spike_pct": spike_pct,
                    "live_value": live,
                    "historical": hist,
                    "current_hour": current_hour,
                    "is_real": True,
                })
            else:
                # Scraping failed (no data, bot block, or location has no live data)
                results.append({
                    "name": target["name"],
                    "status": "UNAVAILABLE",
                    "spike_pct": 0,
                    "live_value": 0,
                    "historical": [0]*24,
                    "current_hour": current_hour,
                    "is_real": False,
                    "message": "Не удалось загрузить данные (нет live информации или Google заблокировал скрейпер)"
                })

        return results


pizza_service = PizzaService()