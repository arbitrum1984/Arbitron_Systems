"""Pizza Scraper Microservice.

Standalone Playwright-based Google Maps scraper.
Runs a background loop every 5 minutes to scrape Popular Times data
for configured targets. Exposes /status for the terminal to read.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PizzaScraper")

app = FastAPI(title="Pizza Scraper")

# ── Configuration ──────────────────────────────────────────────────
TARGETS = [
    {
        "id": "pentagon",
        "name": "DOMINO'S (PENTAGON)",
        "search": "Domino's Pizza Pentagon City Arlington VA",
        "match": "domino",
    },
    {
        "id": "glebe_rd",
        "name": "PAPA JOHN'S (GLEBE RD)",
        "search": "Papa John's Pizza 3312 S Glebe Rd Arlington VA",
        "match": "papa john",
    },
    {
        "id": "cia_hq",
        "name": "DOMINO'S (LANGLEY/CIA)",
        "search": "Domino's Pizza 1445 Laughlin Ave McLean VA",
        "match": "domino",
    },
]

SCRAPE_INTERVAL = 300  # 5 minutes

# ── Cache ──────────────────────────────────────────────────────────
_cached_results: list = []


# ── Scraping ───────────────────────────────────────────────────────

async def scrape_place(search_query: str, match_name: str = "") -> Optional[Dict]:
    """Scrape a single Google Maps place via search URL."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("playwright not installed")
        return None

    logger.info(f"Scraping: «{search_query}»")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = await browser.new_context(
            locale="ru-RU",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            geolocation={"latitude": 38.8687, "longitude": -77.0849},
            permissions=["geolocation"],
        )
        page = await context.new_page()

        try:
            # 1. Accept consent
            await page.goto(
                "https://www.google.com/maps?hl=ru",
                wait_until="domcontentloaded",
            )
            await page.wait_for_timeout(3000)

            consent_sel = 'form[action*="consent"] button:last-of-type'
            if await page.locator(consent_sel).count() > 0:
                await page.locator(consent_sel).first.click()
                logger.info("Consent accepted.")
                await page.wait_for_timeout(3000)

            # 2. Navigate to search URL
            encoded = quote_plus(search_query)
            search_url = f"https://www.google.com/maps/search/{encoded}/?hl=ru"
            await page.goto(search_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(8000)

            # 3. Click matching result
            results = page.locator('[role="article"]')
            result_count = await results.count()

            if result_count > 0:
                logger.info(f"Found {result_count} results.")
                clicked = False
                if match_name:
                    for i in range(result_count):
                        try:
                            link = results.nth(i).locator("a").first
                            label = await link.get_attribute("aria-label") or ""
                            if match_name in label.lower():
                                logger.info(f"Clicking [{i}]: «{label}»")
                                await results.nth(i).click()
                                clicked = True
                                break
                        except Exception:
                            continue
                if not clicked:
                    logger.info("No name match — clicking first.")
                    await results.first.click()
                await page.wait_for_timeout(5000)
            else:
                logger.warning("No results found.")
                return None

            # 4+5. Scroll and extract Popular Times
            logger.info("Scrolling + extracting …")
            bar_labels: List[str] = []
            pt_selectors = [
                '[aria-label*="Загруженность"]',
                '[aria-label*="загруженность"]',
                '[aria-label*="загружено"]',
                '[aria-label*="busy"]',
            ]

            for attempt in range(4):
                try:
                    place_card = page.locator(
                        'div[role="main"][aria-label]'
                    ).last
                    if await place_card.count() > 0:
                        await place_card.hover(timeout=5000)
                    else:
                        await page.locator('div[role="main"]').last.hover(
                            timeout=5000
                        )
                    for _ in range(4):
                        await page.mouse.wheel(0, 600)
                        await asyncio.sleep(0.3)
                except Exception:
                    for _ in range(4):
                        await page.keyboard.press("PageDown")
                        await asyncio.sleep(0.3)

                await page.wait_for_timeout(2000)

                for sel in pt_selectors:
                    cnt = await page.locator(sel).count()
                    if cnt > 0:
                        bars = await page.locator(sel).all()
                        for bar in bars:
                            label = await bar.get_attribute("aria-label")
                            if label:
                                bar_labels.append(label)
                        logger.info(
                            f"Found {len(bar_labels)} PT labels "
                            f"(attempt {attempt + 1})."
                        )
                        break
                if bar_labels:
                    break

            # JS fallback
            if not bar_labels:
                try:
                    js_labels = await page.evaluate("""
                        () => {
                            const els = document.querySelectorAll('[aria-label]');
                            const labels = [];
                            for (const el of els) {
                                const lbl = el.getAttribute('aria-label');
                                if (lbl && lbl.includes('%')) labels.push(lbl);
                            }
                            return labels;
                        }
                    """)
                    if js_labels:
                        bar_labels = [
                            l for l in js_labels
                            if "загруж" in l.lower()
                            or "busy" in l.lower()
                            or ":" in l
                        ]
                        if bar_labels:
                            logger.info(f"JS fallback: {len(bar_labels)} labels.")
                except Exception:
                    pass

            if not bar_labels:
                logger.warning("No Popular Times found.")
                return None

            logger.info(f"Collected {len(bar_labels)} labels.")
            return parse_labels(bar_labels)

        except Exception as e:
            logger.error(f"Error: {e}")
            return None
        finally:
            await browser.close()


# ── Parsing ────────────────────────────────────────────────────────

def parse_labels(labels: List[str]) -> Optional[Dict]:
    """Parse Russian aria-label strings from Google Maps."""
    live_val = None
    typical_val = None
    historical = [0] * 24

    for label in labels:
        if "Сейчас" in label or "сейчас" in label:
            m = re.search(r"(?:Сейчас|сейчас)\D*?(\d+)\s*%", label)
            if m:
                live_val = int(m.group(1))
            um = re.search(r"(?:Обычно|обычно)\D*?(\d+)\s*%", label)
            if um:
                typical_val = int(um.group(1))
            continue

        time_match = re.search(r"(?:в|В)\s+(\d{1,2}):00", label)
        pct_match = re.search(r"(\d+)\s*%", label)

        if time_match and pct_match:
            hour = int(time_match.group(1))
            pct = int(pct_match.group(1))
            if 0 <= hour < 24:
                historical[hour] = pct

    now_hour = datetime.now().hour
    if live_val is None and historical[now_hour] > 0:
        live_val = historical[now_hour]
        typical_val = historical[now_hour]

    if live_val is None:
        return None
    if typical_val is None:
        typical_val = live_val

    return {"live": live_val, "typical": typical_val, "historical": historical}


# ── Index calculation ──────────────────────────────────────────────

async def run_full_scrape() -> list:
    """Scrape all targets and return formatted results."""
    global _cached_results
    results = []
    now = datetime.now()
    current_hour = now.hour

    for target in TARGETS:
        logger.info("Processing %s …", target["name"])
        scraped = await scrape_place(target["search"], target.get("match", ""))

        if scraped is not None:
            live = scraped["live"]
            typical = scraped["typical"]
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

            hist = scraped.get("historical")
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
            results.append({
                "name": target["name"],
                "status": "UNAVAILABLE",
                "spike_pct": 0,
                "live_value": 0,
                "historical": [0] * 24,
                "current_hour": current_hour,
                "is_real": False,
                "message": "Не удалось загрузить данные",
            })

    _cached_results = results
    logger.info("Cache updated: %d locations.", len(results))
    return results


# ── Background loop ───────────────────────────────────────────────

async def scrape_loop():
    """Background task: scrape all targets every SCRAPE_INTERVAL seconds."""
    while True:
        try:
            await run_full_scrape()
        except Exception as e:
            logger.error(f"Scrape loop error: {e}")
        await asyncio.sleep(SCRAPE_INTERVAL)


@app.on_event("startup")
async def startup():
    logger.info("Pizza Scraper starting …")
    asyncio.create_task(scrape_loop())
    logger.info("Background scrape loop scheduled (every %ds).", SCRAPE_INTERVAL)


# ── API ────────────────────────────────────────────────────────────

@app.get("/status")
async def get_status():
    """Return cached scrape results."""
    return _cached_results


@app.get("/health")
async def health():
    return {"status": "ok", "cached": len(_cached_results)}
