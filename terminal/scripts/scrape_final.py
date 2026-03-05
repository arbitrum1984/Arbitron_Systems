"""Final attempt at real scraping using persistent Playwright context."""

import asyncio
from playwright.async_api import async_playwright
import os
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ScraperFinal")

async def scrape_location(query: str, session_dir: str):
    logger.info(f"Scraping: {query}")
    async with async_playwright() as p:
        # Use persistent context to handle session/cookies
        context = await p.chromium.launch_persistent_context(
            session_dir,
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()
        
        # Add common Google search params to look more human
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=en&gl=us&num=1"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            await context.close()
            return None

        await page.wait_for_timeout(3000)
        
        # Handle Consent
        try:
            # Try to find common consent buttons
            consent_selectors = [
                 'button:has-text("Accept all")',
                 'button:has-text("I agree")',
                 'button:has-text("Agree")',
                 '#L2AGLb' # Common ID for Google "Accept All" button
            ]
            for selector in consent_selectors:
                btn = page.locator(selector).first
                if await btn.is_visible():
                    logger.info(f"Clicking consent button: {selector}")
                    await btn.click()
                    await page.wait_for_timeout(3000)
                    break
        except Exception:
            pass

        # Check for CAPTCHA
        html = await page.content()
        if "captcha" in html.lower() or "not a robot" in html.lower():
            logger.warning("CAPTCHA DETECTED. Real scraping blocked by Google security.")
            await context.close()
            return "CAPTCHA"

        # Try to extract "Currently X% busy" or "Usually X% busy"
        live_match = re.search(r"Currently (\d+)% busy", html, re.IGNORECASE)
        usually_match = re.search(r"Usually (\d+)% busy", html, re.IGNORECASE)
        
        # Also look in aria-labels of popular times bars
        # The bars usually have aria-labels like "65% busy at 7 PM."
        busy_labels = await page.evaluate("""
            () => {
                const labels = [];
                const els = document.querySelectorAll('[aria-label*="busy"]');
                for (const el of els) {
                    labels.push(el.getAttribute('aria-label'));
                }
                return labels;
            }
        """)

        await context.close()
        
        return {
            "live": live_match.group(1) if live_match else None,
            "typical": usually_match.group(1) if usually_match else None,
            "labels": busy_labels[:10]
        }

async def main():
    queries = [
        "Domino's Pizza 2602 Columbia Pike, Arlington, VA 22204",
        "Papa John's Pizza 1014 S Glebe Rd Ste A, Arlington, VA 22204",
        "Domino's Pizza 1420 Chain Bridge Rd, McLean, VA 22101"
    ]
    
    session_root = os.path.join(os.getcwd(), "google_session_final")
    if not os.path.exists(session_root):
        os.makedirs(session_root)

    for i, q in enumerate(queries):
        # We use separate dirs if we want clean starts, or same for cookie accumulation
        res = await scrape_location(q, session_root)
        print(f"\nResult for {q}:")
        print(res)

if __name__ == "__main__":
    asyncio.run(main())
