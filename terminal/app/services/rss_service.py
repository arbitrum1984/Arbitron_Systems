import feedparser
import httpx
import asyncio
import logging
import hashlib
from collections import OrderedDict
from app.database.crud import add_message, get_history
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RSS_Intel")

class RSSService:
    def __init__(self):
        self.feeds = [
            # High-volume financial and political news
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",  # Finance
            "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",  # Wall Street Journal Markets
            "https://finance.yahoo.com/news/rss", # Yahoo Finance (often includes Bloomberg/Reuters)
            
            # Defense & Energy (Existing working feeds)
            "https://www.defenseone.com/rss/all/",
            "https://oilprice.com/rss/main",
        ]

        self.ALPHA_KEYWORDS = [
            "TANKER", "SEIZED", "SANCTION", "HORMUZ", "PIPELINE", "EXPLOSION",
            "PENTAGON", "OPEC", "BARREL", "OFFSHORE", "INTERCEPT", "MISSILE"
        ]

        self._seen_hashes = OrderedDict()
        self._client = httpx.AsyncClient(timeout=30)

    def _get_hash(self, text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def is_alpha(self, text: str) -> bool:
        text_upper = text.upper()
        return any(word in text_upper for word in self.ALPHA_KEYWORDS)

    async def fetch_feed(self, url):
        try:
            resp = await self._client.get(url)
            if resp.status_code != 200:
                return []
            feed = feedparser.parse(resp.text)
            return feed.entries
        except Exception as e:
            logger.error(f"Feed Error {url}: {e}")
            return []

    async def poll_feeds(self):
        """Single poll cycle. Called repeatedly by the lifespan loop in main.py."""
        logger.info("Starting RSS Polling...")

        tasks = [self.fetch_feed(url) for url in self.feeds]
        results = await asyncio.gather(*tasks)

        new_intel_count = 0

        for entries in results:
            for entry in entries:
                title = entry.get('title', '')
                link = entry.get('link', '')

                msg_hash = self._get_hash(link)
                if msg_hash in self._seen_hashes:
                    continue

                # FIFO eviction: remove oldest entries when over 1000
                self._seen_hashes[msg_hash] = True
                if len(self._seen_hashes) > 1000:
                    # Remove oldest 200 entries
                    for _ in range(200):
                        self._seen_hashes.popitem(last=False)

                if "google" in link and not self.is_alpha(title):
                    continue

                source_name = entry.get('source', {}).get('title', 'RSS Feed')
                pub_date = entry.get('published', '')
                # Shorten date: "Mon, 08 Mar 2026 12:00:00 GMT" → "08 Mar 2026"
                if pub_date:
                    parts = pub_date.split(',')
                    short_date = parts[-1].strip().rsplit(' ', 2)[0] if parts else pub_date[:16]
                    date_tag = f"<span style='color: #888;'>{short_date}</span> | "
                else:
                    date_tag = ""
                clean_msg = f"{date_tag}{title} \n🔗 [Read]({link})"

                add_message("INTEL_STREAM", "system", clean_msg)
                new_intel_count += 1

        if new_intel_count > 0:
            logger.info(f"RSS: {new_intel_count} new articles ingested.")

rss_service = RSSService()
