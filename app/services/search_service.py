"""News search utilities used to enrich AI responses.

This module provides a thin wrapper around the DuckDuckGo
`ddgs` client to retrieve recent news items matching a query. The
service focuses on returning readable snippets (title and short
body) concatenated into a single string suitable for inclusion in a
textual prompt or UI display.

The implementation is intentionally lightweight: failures return a
short explanatory string rather than raising an exception so that
callers can integrate the result into prompts without complex error
handling.
"""

from ddgs import DDGS


class SearchService:
    """Simple search service that retrieves recent news snippets.

    The service uses the `DDGS` context manager to stream results
    from DuckDuckGo's news endpoint. Results are formatted as
    human-readable strings containing a title and a snippet and are
    returned concatenated by double newlines.
    """

    def search_news(self, query: str, limit: int = 5) -> str:
        """Search for recent news items matching `query`.

        The function streams up to `limit` news results and formats
        each result as:

            Title: <title>\nSnippet: <body>

        Multiple results are joined with a blank line. On error the
        function returns an explanatory string with the error
        information.

        Args:
            query (str): The search query (for example,
                "AAPL stock news").
            limit (int): Maximum number of news items to retrieve.

        Returns:
            str: A textual aggregation of news titles and snippets, or
                an error message if the search fails.
        """
        try:
            results = []
            with DDGS() as ddgs:
                # Request news-specific results in US English region
                ddgs_gen = ddgs.news(query, region="us-en", safesearch="off", max_results=limit)
                for r in ddgs_gen:
                    results.append(f"Title: {r['title']}\nSnippet: {r['body']}")

            if not results:
                return "No recent news found."

            return "\n\n".join(results)
        except Exception as e:
            return f"Search Error: {e}"


search_engine = SearchService()