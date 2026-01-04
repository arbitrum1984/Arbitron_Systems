"""Simple CRUD helpers for chat sessions, messages, and favorites.

This module exposes a small collection of convenience functions
that wrap SQL statements against the application SQLite database.
Each function uses the module-level `db` helper to obtain a
connection and returns plain Python types (lists/dicts) appropriate
for JSON serialization by FastAPI handlers.

The functions intentionally perform minimal validation and are
designed to be called from higher-level service or API layers.
"""

from app.database.database import db


# --- Chats ---
def create_session(session_id: str, title: str = "New Chat") -> None:
    """Create a chat session if it does not already exist.

    Uses an "INSERT OR IGNORE" statement so calling this function is
    idempotent for an existing `session_id`.

    Args:
        session_id (str): Unique identifier for the chat session.
        title (str): Optional human-readable title.

    Returns:
        None
    """
    with db.get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO chat_sessions (id, title) VALUES (?, ?)", (session_id, title))
        conn.commit()


def get_all_sessions() -> list:
    """Return all chat sessions ordered by creation time.

    Returns a list of dictionaries where each dictionary corresponds
    to a row in the `chat_sessions` table.

    Returns:
        list: A list of session dictionaries.
    """
    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM chat_sessions ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def delete_session(session_id: str) -> None:
    """Delete a chat session and its messages.

    The function removes the session row and also removes any
    messages associated with the session for extra safety. The
    `chat_messages` table is defined with `ON DELETE CASCADE`, so
    the explicit message delete is redundant but harmless.

    Args:
        session_id (str): The identifier of the session to delete.

    Returns:
        None
    """
    with db.get_connection() as conn:
        conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        conn.commit()


# --- Messages ---
def add_message(session_id: str, role: str, content: str) -> None:
    """Append a message to a chat session, creating the session if needed.

    The function ensures the session exists by calling
    `create_session`, then inserts a new row into
    `chat_messages`.

    Args:
        session_id (str): Identifier of the session to which the
            message belongs.
        role (str): The message role, typically 'user' or 'assistant'.
        content (str): The textual content of the message.

    Returns:
        None
    """
    create_session(session_id, f"Chat {session_id[-4:]}")

    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        conn.commit()


def get_history(session_id: str) -> list:
    """Retrieve the chronological message history for a session.

    Returns a list of dictionaries with keys `role` and `content` in
    ascending order by message id.

    Args:
        session_id (str): The session identifier.

    Returns:
        list: A list of message dictionaries.
    """
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        return [dict(row) for row in rows]


# --- Favorites (Watchlist) ---
def add_favorite(ticker: str) -> None:
    """Add a ticker symbol to the favorites/watchlist.

    The insert is idempotent due to `INSERT OR IGNORE`. The ticker is
    normalized to upper case before insertion.

    Args:
        ticker (str): The ticker symbol to add (e.g., 'AAPL').

    Returns:
        None
    """
    with db.get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO favorites (ticker) VALUES (?)", (ticker.upper(),))
        conn.commit()


def get_favorites() -> list:
    """Return the list of favorite tickers ordered by recency.

    Returns a simple list of ticker strings suitable for JSON
    serialization.

    Returns:
        list: List of ticker symbols (strings).
    """
    with db.get_connection() as conn:
        rows = conn.execute("SELECT ticker FROM favorites ORDER BY added_at DESC").fetchall()
        return [row['ticker'] for row in rows]


def remove_favorite(ticker: str) -> None:
    """Remove a ticker from the favorites/watchlist.

    The ticker is normalized to upper case prior to deletion.

    Args:
        ticker (str): The ticker symbol to remove.

    Returns:
        None
    """
    with db.get_connection() as conn:
        conn.execute("DELETE FROM favorites WHERE ticker = ?", (ticker.upper(),))
        conn.commit()