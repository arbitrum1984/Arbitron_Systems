"""SQLite database utilities and schema initialization.

This module provides a lightweight wrapper around SQLite used by the
application. It ensures the database directory exists, exposes a
`Database` helper for acquiring connections with sensible defaults
(named row access), and initializes the application's schema on
import. The module intentionally returns plain sqlite3 connections so
callers can use them contextually (e.g., `with db.get_connection()`).

Side effects:
 - Ensures the directory that will contain the database file exists.
 - Creates the default schema when the module is imported.

The schema contains three tables:
 - `chat_sessions`: stores chat session metadata.
 - `chat_messages`: stores individual messages linked to sessions.
 - `favorites`: stores user watchlist tickers.
"""

import sqlite3
import os
from app.core.config import settings

# Ensure the directory for the SQLite file exists
os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)


class Database:
    """Helper class for obtaining SQLite connections and initializing schema.

    The class is intentionally minimal: it stores the configured
    database path and exposes `get_connection` for callers that need
    a raw sqlite3 connection, and `init_db` to (re)create the
    required tables.
    """

    def __init__(self):
        """Initialize the Database helper using configured DB path.

        The constructor stores the resolved database path from
        application settings.

        Args:
            None

        Returns:
            None
        """
        self.db_path = settings.DB_PATH

    def get_connection(self) -> sqlite3.Connection:
        """Create and return a SQLite connection for the configured path.

        The returned connection is configured with `row_factory =
        sqlite3.Row` so consumers can access columns by name (e.g.
        `row['id']`). Callers are expected to manage the connection
        context (for example using `with db.get_connection() as conn`).

        Returns:
            sqlite3.Connection: A live connection to the SQLite database.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Create the application's database schema if it does not exist.

        The method executes a multi-statement SQL script that creates
        the `chat_sessions`, `chat_messages`, and `favorites` tables
        with appropriate primary keys and foreign key constraints.
        Any errors are printed to stdout; the function does not
        re-raise exceptions to keep module import idempotent during
        development.

        Returns:
            None
        """
        query = """
        -- Chat sessions table
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Chat messages table
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        );

        -- Favorites table (watchlist tickers)
        CREATE TABLE IF NOT EXISTS favorites (
            ticker TEXT PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        try:
            with self.get_connection() as conn:
                conn.executescript(query)
                print("Database initialized successfully.")
        except Exception as e:
            print(f"Database Error: {e}")


# Instantiate and initialize the database as a convenient module-level
# singleton. Importing this module will create the file and schema if
# necessary; consumers may import `db` and call `db.get_connection()`.
db = Database()
db.init_db()