import feedparser
import httpx
import asyncio
import logging
import hashlib
from app.database.crud import add_message, get_history # Используем get_history для проверки дублей (или свой метод)
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RSS_Intel")

class RSSService:
    def __init__(self):
        # СПИСОК ИСТОЧНИКОВ (Сюда вставляешь свои URL)
        self.feeds = [
            # 1. Google Alerts (Вставь сюда свой RSS линк, который ты создал в google.com/alerts)
            # "https://www.google.com/alerts/feeds/YOUR_ID/...", 
            
            # 2. Maritime / Energy (Реальные источники)
            "https://gcaptain.com/feed/",                # Главный морской логистический ресурс
            "https://oilprice.com/rss/main",             # Цены на нефть и аналитика
            "https://www.defenseone.com/rss/all/",       # ВПК и Пентагон
        ]

        # Ключевые слова для подсветки важности
        self.ALPHA_KEYWORDS = [
            "TANKER", "SEIZED", "SANCTION", "HORMUZ", "PIPELINE", "EXPLOSION",
            "PENTAGON", "OPEC", "BARREL", "OFFSHORE", "INTERCEPT", "MISSILE"
        ]

        # В памяти храним хеши последних 100 новостей, чтобы не долбить БД лишний раз
        self.seen_hashes = set()

    def _get_hash(self, text: str) -> str:
        """Создает уникальный отпечаток новости"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def is_alpha(self, text: str) -> bool:
        """Проверка на годноту"""
        text_upper = text.upper()
        return any(word in text_upper for word in self.ALPHA_KEYWORDS)

    async def fetch_feed(self, client, url):
        try:
            # Скачиваем XML асинхронно
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            
            # Парсим контент
            feed = feedparser.parse(resp.text)
            return feed.entries
        except Exception as e:
            logger.error(f"Feed Error {url}: {e}")
            return []

    async def poll_feeds(self):
        """Главный цикл опроса"""
        logger.info("Starting RSS Polling...")
        
        while True:
            async with httpx.AsyncClient(timeout=30) as client:
                tasks = [self.fetch_feed(client, url) for url in self.feeds]
                results = await asyncio.gather(*tasks)

                new_intel_count = 0
                
                # Проходим по всем фидам
                for entries in results:
                    for entry in entries:
                        title = entry.get('title', '')
                        link = entry.get('link', '')
                        
                        # 1. Проверка на дубликат (в памяти)
                        msg_hash = self._get_hash(link)
                        if msg_hash in self.seen_hashes:
                            continue
                        
                        # Добавляем в память (ограничиваем размер сета, чтобы не текла память)
                        if len(self.seen_hashes) > 1000:
                            self.seen_hashes.clear()
                        self.seen_hashes.add(msg_hash)

                        # 2. Фильтрация (Google Alerts часто шлет мусор, проверяем на Alpha)
                        # Если это спец-источник типа gCaptain - берем все.
                        # Если Google Alerts - фильтруем строже.
                        if "google" in link and not self.is_alpha(title):
                            continue

                        # 3. Сохраняем в БД (INTEL_STREAM)
                        # Форматируем красиво
                        source_name = entry.get('source', {}).get('title', 'RSS Feed')
                        clean_msg = f" **RSS ({source_name}):** {title} \n🔗 [Read]({link})"
                        
                        # Проверка через БД (на случай перезагрузки сервера)
                        # Тут можно добавить SQL проверку, но для MVP хватит хешей в памяти
                        
                        add_message("INTEL_STREAM", "system", clean_msg)
                        new_intel_count += 1

                if new_intel_count > 0:
                    logger.info(f"RSS: {new_intel_count} new articles ingested.")

            # RSS не обновляется мгновенно, 5 минут (300 сек) - оптимально
            await asyncio.sleep(300)

rss_service = RSSService()