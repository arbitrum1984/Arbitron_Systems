"""
app.services.twitter_service
--------------------------------

Lightweight service integration for fetching, filtering, and
persisting Twitter-derived intelligence using an Apify task.

This module provides a small `TwitterService` class which calls an
Apify task endpoint, applies simple keyword-based filters to
incoming tweets, and persists selected items into the application's
database as system messages. Filtering comprises two lists:
`GARBAGE_KEYWORDS` (items to ignore) and `ALPHA_KEYWORDS` (signals
worthy of storing).

All docstrings use a professional, academic tone and are written in
English. The module avoids altering application control flow and
preserves existing behavior (async fetching, volume-tolerant timeout,
and simple logging).
"""

import httpx
import logging
from app.database.crud import add_message
from app.core.config import settings

# Configure a dedicated logger for the twitter intelligence service
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TwitterIntel")

class TwitterService:
    """
    Service wrapper for retrieving and filtering tweets from Apify.

    The service invokes a configured Apify task to obtain recent
    tweets, applies two-stage keyword filtering, and persists any
    resulting intelligence records using the application's CRUD
    helpers. The filtering strategy is intentionally conservative:
    tweets that match any item in `GARBAGE_KEYWORDS` are discarded,
    while tweets containing any item from `ALPHA_KEYWORDS` are
    considered actionable and saved as a system message under the
    session id "INTEL_STREAM".

    Attributes:
        token (str): API token used to authenticate with Apify.
        task_id (str): Identifier of the Apify task to call.
        api_url (str): Fully-qualified URL used to run the task
            synchronously and retrieve dataset items.

    Notes:
        The class is designed for simple periodic polling from a
        background runner. It deliberately avoids retries and
        complex backoff logic; callers may wrap `fetch_and_process`
        if stronger reliability semantics are required.
    """

    def __init__(self):
        # API key and Apify task identifier are sourced from settings
        self.token = settings.APIFY_API_KEY
        self.task_id = "USERNAME/ARBI_WATCH"
        # The synchronous run endpoint returns dataset items directly.
        self.api_url = f"https://api.apify.com/v2/tasks/{self.task_id}/run-sync-get-dataset-items?token={self.token}"

    # Keywords that indicate content should be discarded as noise.
    GARBAGE_KEYWORDS = [
        "ACCIDENT", "CHILD", "KILLED", "INJURED", "DIED", "WATER TANKER",
        "DRIVER", "ARRESTED", "TRAGIC", "HIGH-SPEED"
    ]

    # Keywords that indicate content is potentially actionable/intel.
    ALPHA_KEYWORDS = [
        "SEIZED", "DETAINED", "SUPERTANKER", "BARREL", "SANCTION",
        "OFFSHORE", "PIPELINE", "STRAIT", "HORMUZ", "VENEZUELA",
        "IRAN", "GUYANA", "NAVY", "INTERCEPTED"
    ]

    def is_garbage(self, text: str) -> bool:
        """
        Determine whether the provided text matches any garbage keywords.

        The check is case-insensitive and performs a simple substring
        membership test against each item in `GARBAGE_KEYWORDS`.

        Args:
            text (str): The text to evaluate (tweet body).

        Returns:
            bool: `True` if the text contains any garbage keyword,
            otherwise `False`.
        """
        text_upper = text.upper()
        if any(word in text_upper for word in self.GARBAGE_KEYWORDS):
            return True
        return False

    def is_alpha(self, text: str) -> bool:
        """
        Check whether the provided text contains any alpha (signal) keywords.

        This method is case-insensitive and performs substring checks
        against `ALPHA_KEYWORDS`. It returns `True` when the text
        contains at least one signal token, indicating the tweet is
        likely of interest for intelligence purposes.

        Args:
            text (str): The text to inspect.

        Returns:
            bool: `True` if the text contains any alpha keyword,
            otherwise `False`.
        """
        text_upper = text.upper()
        if any(word in text_upper for word in self.ALPHA_KEYWORDS):
            return True
        return False

    async def fetch_and_process(self) -> int:
        """
        Execute the configured Apify task, filter results, and persist intel.

        The method performs an asynchronous POST to the Apify task run
        endpoint, parses the returned dataset items, applies the
        `is_garbage` and `is_alpha` filters in sequence, and persists
        any identified alpha items using `add_message` with the session
        id `INTEL_STREAM` and role `system`.

        Returns a simple integer count of how many alpha records were
        processed and stored. On errors the function logs the exception
        and returns `0` to indicate no items were processed.

        Returns:
            int: Number of processed (saved) alpha items.
        """
        logger.info("Connecting to Apify...")

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                # Call the Apify task; note this operation may take several seconds.
                response = await client.post(self.api_url)

                if response.status_code != 200:
                    logger.error(f"Apify Error: {response.status_code}")
                    return 0

                tweets = response.json()
                processed_count = 0

                for t in tweets:
                    text = t.get('text', '')
                    url = t.get('url', '')
                    author = t.get('twitterUrl', '').split('/')[3] if t.get('twitterUrl') else ''

                    # Stage 1: discard obvious garbage
                    if self.is_garbage(text):
                        logger.info(f"Skipped Garbage: {text[:30]}...")
                        continue

                    # Stage 2: detect alpha signals and persist them
                    if self.is_alpha(text):
                        clean_msg = f"🚨 **INTEL:** {text} \n\n🔗 [Source]({url})"
                        add_message("INTEL_STREAM", "system", clean_msg)

                        processed_count += 1
                        logger.info(f"✅ ALPHA DETECTED: {text[:30]}...")

                return processed_count

            except Exception as e:
                logger.error(f"Critical Error: {e}")
                return 0

# Инициализация
twitter_service = TwitterService()