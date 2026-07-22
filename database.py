import aiosqlite
import json
import asyncio
from config import config


class Database:
    """SQLite database for chat history and command logs only.
    Sessions are stored in Telegram channel via ChannelSessionStorage."""

    def __init__(self):
        self.db_path = config.DB_PATH
        self._db = None

    async def connect(self):
        """Initialize database connection and create tables."""
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._create_tables()

    async def close(self):
        """Close database connection."""
        if self._db:
            await self._db.close()

    async def _create_tables(self):
        """Create required tables if they don't exist."""
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS channel_sessions (
                user_id INTEGER PRIMARY KEY,
                channel_message_id INTEGER NOT NULL,
                phone TEXT,
                language TEXT DEFAULT 'uz',
                current_session_id INTEGER DEFAULT 1,
                is_connected INTEGER DEFAULT 1,
                username TEXT,
                name TEXT,
                is_blocked INTEGER DEFAULT 0,
                auto_reply INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS command_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                result TEXT,
                status TEXT DEFAULT 'success',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                session_id INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS channel_chat_histories (
                user_id INTEGER,
                session_id INTEGER,
                channel_message_id INTEGER,
                PRIMARY KEY (user_id, session_id)
            );
        """)

        # Add auto_reply column to existing table if missing
        try:
            await self._db.execute("ALTER TABLE channel_sessions ADD COLUMN auto_reply INTEGER DEFAULT 1")
            await self._db.commit()
        except Exception:
            pass
        await self._db.commit()

        # Migrate existing DB: try to add language column
        try:
            await self._db.execute("ALTER TABLE channel_sessions ADD COLUMN language TEXT DEFAULT 'uz'")
            await self._db.commit()
        except Exception:
            pass

        # Migrate existing DB: try to add current_session_id column
        try:
            await self._db.execute("ALTER TABLE channel_sessions ADD COLUMN current_session_id INTEGER DEFAULT 1")
            await self._db.commit()
        except Exception:
            pass

        # Migrate existing DB: try to add session_id column to chat_history
        try:
            await self._db.execute("ALTER TABLE chat_history ADD COLUMN session_id INTEGER DEFAULT 1")
            await self._db.commit()
        except Exception:
            pass

        # Migrate existing DB: try to add created_at column to channel_sessions
        try:
            await self._db.execute("ALTER TABLE channel_sessions ADD COLUMN created_at TIMESTAMP")
            await self._db.commit()
            await self._db.execute("UPDATE channel_sessions SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
            await self._db.commit()
        except Exception:
            pass

        # Migrate existing DB: try to add username column to channel_sessions
        try:
            await self._db.execute("ALTER TABLE channel_sessions ADD COLUMN username TEXT")
            await self._db.commit()
        except Exception:
            pass

        # Migrate existing DB: try to add name column to channel_sessions
        try:
            await self._db.execute("ALTER TABLE channel_sessions ADD COLUMN name TEXT")
            await self._db.commit()
        except Exception:
            pass

        # Migrate existing DB: try to add is_blocked column to channel_sessions
        try:
            await self._db.execute("ALTER TABLE channel_sessions ADD COLUMN is_blocked INTEGER DEFAULT 0")
            await self._db.commit()
        except Exception:
            pass

    # ── Channel Session Mapping ──────────────────────────────────────
    # (tracks which channel message stores which user's session)

    async def save_session_mapping(
        self, user_id: int, channel_message_id: int, phone: str
    ):
        """Save mapping: user_id -> channel message ID."""
        await self._db.execute(
            """INSERT INTO channel_sessions (user_id, channel_message_id, phone, is_connected, updated_at)
               VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   channel_message_id = excluded.channel_message_id,
                   phone = excluded.phone,
                   is_connected = 1,
                   updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, channel_message_id, phone),
        )
        await self._db.commit()
        await self.trigger_backup()

    async def get_session_mapping(self, user_id: int) -> dict | None:
        """Get channel message ID for a user's session."""
        async with self._db.execute(
            "SELECT * FROM channel_sessions WHERE user_id = ? AND is_connected = 1",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
        return None

    async def disconnect_user(self, user_id: int):
        """Mark user session as disconnected."""
        await self._db.execute(
            "UPDATE channel_sessions SET is_connected = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,),
        )
        await self._db.commit()
        await self.trigger_backup()

    async def get_auto_reply(self, user_id: int) -> bool:
        """Check if AI auto-reply for PMs is enabled for user."""
        try:
            async with self._db.execute(
                "SELECT auto_reply FROM channel_sessions WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0] is not None:
                    return bool(row[0])
        except Exception:
            pass
        return True

    async def set_auto_reply(self, user_id: int, enabled: bool):
        """Set AI auto-reply for PMs state for user."""
        val = 1 if enabled else 0
        try:
            await self._db.execute(
                "UPDATE channel_sessions SET auto_reply = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (val, user_id)
            )
            await self._db.commit()
        except Exception as e:
            logger.error(f"Error setting auto_reply for user {user_id}: {e}")

    async def delete_session_mapping(self, user_id: int):
        """Delete session mapping entirely."""
        await self._db.execute("DELETE FROM channel_sessions WHERE user_id = ?", (user_id,))
        await self._db.commit()
        await self.trigger_backup()

    async def update_user_details(self, user_id: int, username: str | None, name: str | None):
        """Update username and name for a user session."""
        await self._db.execute(
            "UPDATE channel_sessions SET username = ?, name = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (username, name, user_id),
        )
        await self._db.commit()
        await self.trigger_backup()

    async def set_user_block_status(self, user_id: int, is_blocked: bool):
        """Block or unblock a user."""
        await self._db.execute(
            """INSERT INTO channel_sessions (user_id, channel_message_id, phone, is_blocked, updated_at)
               VALUES (?, 0, '', ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   is_blocked = excluded.is_blocked,
                   updated_at = CURRENT_TIMESTAMP""",
            (user_id, 1 if is_blocked else 0),
        )
        await self._db.commit()
        await self.trigger_backup()

    async def is_user_blocked(self, user_id: int) -> bool:
        """Check if a user is blocked."""
        try:
            async with self._db.execute("SELECT is_blocked FROM channel_sessions WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return bool(row[0]) if row and row[0] is not None else False
        except Exception:
            return False

    async def trigger_backup(self):
        """Triggers asynchronous database backup to Telegram channel."""
        try:
            from channel_storage import get_channel_storage
            storage = get_channel_storage()
            if storage:
                asyncio.create_task(storage.backup_database_to_channel())
        except Exception:
            pass

    async def get_system_setting(self, key: str) -> str | None:
        """Get a setting value by key."""
        async with self._db.execute("SELECT value FROM system_settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_system_setting(self, key: str, value: str):
        """Set or update a setting value."""
        await self._db.execute(
            """INSERT INTO system_settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, value),
        )
        await self._db.commit()

    async def save_user_language(self, user_id: int, language: str):
        """Save/update language choice for a user."""
        await self._db.execute(
            """INSERT INTO channel_sessions (user_id, channel_message_id, phone, language, is_connected, updated_at)
               VALUES (?, 0, '', ?, 1, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   language = excluded.language,
                   updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, language),
        )
        await self._db.commit()
        await self.trigger_backup()

    async def get_user_language(self, user_id: int) -> str:
        """Get user's language choice, default to 'uz'."""
        try:
            async with self._db.execute(
                "SELECT language FROM channel_sessions WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return row[0]
        except Exception:
            pass
        return "uz"


    # ── Chat History ─────────────────────────────────────────────────

    async def get_current_session_id(self, user_id: int) -> int:
        """Get the current active session ID for a user."""
        try:
            async with self._db.execute(
                "SELECT current_session_id FROM channel_sessions WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0] is not None:
                    return row[0]
        except Exception:
            pass
        return 1

    async def save_current_session_id(self, user_id: int, session_id: int):
        """Save/update the current active session ID for a user."""
        await self._db.execute(
            """INSERT INTO channel_sessions (user_id, channel_message_id, phone, current_session_id, is_connected, updated_at)
               VALUES (?, 0, '', ?, 1, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   current_session_id = excluded.current_session_id,
                   updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, session_id),
        )
        await self._db.commit()

    async def get_user_sessions(self, user_id: int) -> list[int]:
        """Get list of distinct session IDs that have messages for this user."""
        try:
            async with self._db.execute(
                "SELECT DISTINCT session_id FROM chat_history WHERE user_id = ? ORDER BY session_id ASC",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                sessions = [row[0] for row in rows if row[0] is not None]
                if not sessions:
                    return [1]
                return sessions
        except Exception:
            return [1]

    async def create_new_session(self, user_id: int) -> int:
        """Create a new session by finding the max session ID and incrementing it."""
        try:
            async with self._db.execute(
                "SELECT MAX(session_id) FROM chat_history WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                max_id = row[0] if (row and row[0] is not None) else 0
                new_id = max_id + 1
                await self.save_current_session_id(user_id, new_id)
                return new_id
        except Exception:
            return 1

    async def add_chat_message(self, user_id: int, role: str, content: str):
        """Add a message to chat history under the current session ID."""
        session_id = await self.get_current_session_id(user_id)
        await self._db.execute(
            "INSERT INTO chat_history (user_id, role, content, session_id) VALUES (?, ?, ?, ?)",
            (user_id, role, content, session_id),
        )
        await self._db.commit()

    async def get_chat_history(
        self, user_id: int, limit: int = 20
    ) -> list[dict]:
        """Get recent chat history for a user's current session."""
        session_id = await self.get_current_session_id(user_id)
        async with self._db.execute(
            """SELECT role, content FROM chat_history
               WHERE user_id = ? AND session_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, session_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

    async def get_chat_history_for_session(self, user_id: int, session_id: int, limit: int = 50) -> list[dict]:
        """Get chat history for a specific session ID."""
        try:
            async with self._db.execute(
                """SELECT role, content FROM chat_history
                   WHERE user_id = ? AND session_id = ?
                   ORDER BY created_at ASC
                   LIMIT ?""",
                (user_id, session_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"role": row[0], "content": row[1]} for row in rows]
        except Exception:
            return []

    async def clear_chat_history(self, user_id: int):
        """Clear chat history for a user's active session."""
        session_id = await self.get_current_session_id(user_id)
        await self._db.execute(
            "DELETE FROM chat_history WHERE user_id = ? AND session_id = ?",
            (user_id, session_id),
        )
        await self._db.commit()

    # ── Command Log ──────────────────────────────────────────────────

    async def log_command(self, user_id: int, command: str, result: str, status: str):
        """Log a command execution."""
        await self._db.execute(
            "INSERT INTO command_log (user_id, command, result, status) VALUES (?, ?, ?, ?)",
            (user_id, command, result, status),
        )
        await self._db.commit()

    async def save_channel_chat_history_mapping(self, user_id: int, session_id: int, channel_message_id: int):
        """Save the channel message ID of a user's session chat history."""
        await self._db.execute(
            """INSERT INTO channel_chat_histories (user_id, session_id, channel_message_id)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, session_id) DO UPDATE SET
                   channel_message_id = excluded.channel_message_id
            """,
            (user_id, session_id, channel_message_id),
        )
        await self._db.commit()

    async def get_channel_chat_history_mapping(self, user_id: int, session_id: int) -> int | None:
        """Get the channel message ID of a user's session chat history."""
        try:
            async with self._db.execute(
                "SELECT channel_message_id FROM channel_chat_histories WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
        except Exception:
            pass
        return None


# Singleton instance
db = Database()
