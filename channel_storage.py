"""
Channel-based session storage.
Sessions are saved as messages in a Telegram channel.
Each message contains user_id, phone, and encrypted session string.

Message format in channel:
🔐 SESSION
👤 User ID: {user_id}
📱 Phone: {phone}
📅 Date: {datetime}
🔑 Session:
{session_string}
"""

import logging
import json
import io
import asyncio
from datetime import datetime
from aiogram import Bot
from aiogram.types import Message as AiogramMessage, BufferedInputFile
from config import config
from database import db

logger = logging.getLogger(__name__)

# Session message tag — used to identify session messages in the channel
SESSION_TAG = "🔐 SESSION"


class ChannelSessionStorage:
    """Stores and retrieves user sessions from a Telegram channel as .session documents."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.channel_id = config.SESSION_CHANNEL_ID
        self._backup_lock = asyncio.Lock()

    def _format_session_caption(self, user_id: int, phone: str) -> str:
        """Format session document caption."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"{SESSION_TAG}\n"
            f"👤 User ID: {user_id}\n"
            f"📱 Phone: {phone}\n"
            f"📅 Date: {now}"
        )

    def _parse_session_message(self, text: str) -> dict | None:
        """Parse session metadata from text or caption."""
        if not text or SESSION_TAG not in text:
            return None

        try:
            lines = text.strip().split("\n")
            data = {}
            for line in lines:
                if line.startswith("👤 User ID:"):
                    data["user_id"] = int(line.split(":", 1)[1].strip())
                elif line.startswith("📱 Phone:"):
                    data["phone"] = line.split(":", 1)[1].strip()
                elif line.startswith("📅 Date:"):
                    data["date"] = line.split(":", 1)[1].strip()

            # For legacy text messages
            session_marker = "🔑 Session:\n"
            if session_marker in text:
                data["session_string"] = text.split(session_marker, 1)[1].strip()

            return data
        except Exception as e:
            logger.error(f"Failed to parse session message: {e}")

        return None

    async def save_session(
        self, user_id: int, phone: str, session_string: str
    ) -> int:
        """
        Save session to channel as a .session document file.
        Returns the channel message ID.
        """
        caption = self._format_session_caption(user_id, phone)
        session_bytes = session_string.encode("utf-8")
        input_file = BufferedInputFile(
            session_bytes, filename=f"user_{user_id}.session"
        )

        # Check if we already have a message for this user
        mapping = await db.get_session_mapping(user_id)

        if mapping and mapping.get("channel_message_id"):
            # Delete old session message first
            try:
                await self.bot.delete_message(
                    chat_id=self.channel_id,
                    message_id=mapping["channel_message_id"],
                )
            except Exception as e:
                logger.warning(f"Could not delete old session document: {e}")

        # Send new .session document to channel
        try:
            sent_msg = await self.bot.send_document(
                chat_id=self.channel_id,
                document=input_file,
                caption=caption,
            )
            msg_id = sent_msg.message_id

            # Save mapping in local DB
            await db.save_session_mapping(user_id, msg_id, phone)

            logger.info(
                f"Saved new session file user_{user_id}.session to channel "
                f"(msg_id: {msg_id})"
            )
            return msg_id
        except Exception as e:
            logger.error(f"Failed to save session file to channel: {e}")
            raise

    async def load_session(self, user_id: int) -> dict | None:
        """
        Load session from channel using stored message ID.
        Downloads the .session document and returns dict with user_id, phone, session_string or None.
        """
        mapping = await db.get_session_mapping(user_id)

        if not mapping or not mapping.get("channel_message_id"):
            logger.debug(f"No session mapping found for user {user_id}")
            return None

        msg_id = mapping["channel_message_id"]

        try:
            forwarded = await self.bot.forward_message(
                chat_id=self.channel_id,
                from_chat_id=self.channel_id,
                message_id=msg_id,
            )

            session_string = None
            phone = mapping.get("phone", "")

            # If document message (.session file)
            if forwarded.document:
                file_io = await self.bot.download(forwarded.document)
                session_string = file_io.read().decode("utf-8")

                if forwarded.caption:
                    caption_data = self._parse_session_message(forwarded.caption)
                    if caption_data:
                        phone = caption_data.get("phone", phone)

            # Fallback for old text messages
            elif forwarded.text:
                text_data = self._parse_session_message(forwarded.text)
                if text_data:
                    session_string = text_data.get("session_string")
                    phone = text_data.get("phone", phone)

            # Delete the temporary forwarded copy
            try:
                await self.bot.delete_message(
                    chat_id=self.channel_id,
                    message_id=forwarded.message_id,
                )
            except Exception:
                pass

            if session_string:
                logger.info(f"Loaded session file from channel for user {user_id}")
                return {
                    "user_id": user_id,
                    "phone": phone,
                    "session_string": session_string,
                }
            else:
                logger.warning(f"Session data could not be parsed for user {user_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to load session file from channel: {e}")
            return None

    async def save_chat_history_to_channel(self, user_id: int, session_id: int):
        """
        Fetch chat history for a session from DB and upload it as a numbered JS file (e.g. 1.js) to the Telegram channel.
        """
        try:
            # Fetch all messages for this session
            async with db._db.execute(
                """SELECT role, content, created_at FROM chat_history
                   WHERE user_id = ? AND session_id = ?
                   ORDER BY created_at ASC""",
                (user_id, session_id),
            ) as cursor:
                rows = await cursor.fetchall()
            
            if not rows:
                return
                
            # Build list of message dicts
            messages_list = []
            for role, content, created_at in rows:
                messages_list.append({
                    "role": role,
                    "content": content,
                    "created_at": created_at
                })
                
            # Convert to formatted JSON
            json_str = json.dumps(messages_list, ensure_ascii=False, indent=2)
            
            # Format the JavaScript file content
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            js_content = (
                f"// 🤖 AI CHAT HISTORY\n"
                f"// 👤 User ID: {user_id}\n"
                f"// 🔢 Session ID: {session_id}\n"
                f"// 📅 Last Updated: {now_str}\n\n"
                f"const chatHistory = {json_str};\n"
            )
            
            file_content = js_content.encode("utf-8")
            
            # Caption in channel
            caption = (
                f"📝 AI CHAT HISTORY (JS)\n"
                f"👤 User ID: {user_id}\n"
                f"🔢 Session ID: {session_id}\n"
                f"📅 Date: {now_str}"
            )
            
            # Create BufferedInputFile with filename as the session number (e.g. 1.js)
            input_file = BufferedInputFile(
                file_content, filename=f"{session_id}.js"
            )
            
            # Check if we already have a message mapping for this user's session history
            old_msg_id = await db.get_channel_chat_history_mapping(user_id, session_id)
            if old_msg_id:
                try:
                    await self.bot.delete_message(
                        chat_id=self.channel_id,
                        message_id=old_msg_id,
                    )
                except Exception:
                    pass
                    
            # Send new document message to channel
            msg = await self.bot.send_document(
                chat_id=self.channel_id,
                document=input_file,
                caption=caption
            )
            
            # Save new mapping
            await db.save_channel_chat_history_mapping(user_id, session_id, msg.message_id)
            logger.info(f"Saved session chat history as JS to channel: User {user_id}, Session {session_id}, msg_id {msg.message_id}")
            
        except Exception as e:
            logger.error(f"Error saving chat history as JS to channel: {e}", exc_info=True)

    async def restore_database_from_channel(self):
        """
        Scan the channel's pinned message (or search) for the database backup file 'database_backup.json',
        download it, and restore all user sessions and chat history mappings into the local SQLite database.
        """
        try:
            logger.info("Starting database restore process from channel...")
            try:
                chat = await self.bot.get_chat(self.channel_id)
            except Exception as chat_err:
                logger.error(f"Failed to get channel chat details: {chat_err}")
                return False
                
            pinned_msg = chat.pinned_message
            if not pinned_msg or not pinned_msg.document:
                logger.warning("No pinned database backup document found in the channel.")
                return False
                
            logger.info(f"Found pinned database backup document (msg_id: {pinned_msg.message_id}). Downloading...")
            
            file_io = await self.bot.download(pinned_msg.document)
            backup_bytes = file_io.read()
            backup_str = backup_bytes.decode("utf-8")
            
            try:
                backup_data = json.loads(backup_str)
            except Exception as parse_err:
                logger.error(f"Failed to parse database backup JSON: {parse_err}")
                return False
                
            users = backup_data.get("users", [])
            history_mappings = backup_data.get("history_mappings", [])
            
            logger.info(f"Restoring {len(users)} users and {len(history_mappings)} history mappings from backup...")
            
            for user in users:
                await db._db.execute(
                    """INSERT OR REPLACE INTO channel_sessions (
                        user_id, channel_message_id, phone, language, current_session_id, 
                        is_connected, username, name, auto_reply, is_blocked, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user.get("user_id"),
                        user.get("channel_message_id"),
                        user.get("phone", ""),
                        user.get("language", "uz"),
                        user.get("current_session_id", 1),
                        user.get("is_connected", 1),
                        user.get("username", ""),
                        user.get("name", ""),
                        user.get("auto_reply", 1),
                        user.get("is_blocked", 0),
                        user.get("created_at"),
                        user.get("updated_at")
                    )
                )
                
            for mapping in history_mappings:
                await db._db.execute(
                    """INSERT OR REPLACE INTO channel_chat_histories (
                        user_id, session_id, channel_message_id
                    ) VALUES (?, ?, ?)""",
                    (
                        mapping.get("user_id"),
                        mapping.get("session_id"),
                        mapping.get("channel_message_id")
                    )
                )
                
            await db.set_system_setting("db_backup_message_id", str(pinned_msg.message_id))
            await db._db.commit()
            
            logger.info("✅ Database restore process completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring database from channel: {e}", exc_info=True)
            return False

    async def backup_database_to_channel(self):
        """Export the database (channel_sessions & channel_chat_histories) as a JSON file and upload it to the channel, replacing the old backup and pinning it."""
        async with self._backup_lock:
            try:
                # 1. Query all user sessions from database
                async with db._db.execute(
                    """SELECT user_id, channel_message_id, phone, language, current_session_id, 
                              is_connected, username, name, auto_reply, is_blocked, created_at, updated_at 
                       FROM channel_sessions"""
                ) as cursor:
                    rows = await cursor.fetchall()
                    users_list = []
                    for row in rows:
                        users_list.append({
                            "user_id": row[0],
                            "channel_message_id": row[1],
                            "phone": row[2] or "",
                            "language": row[3] or "uz",
                            "current_session_id": row[4] or 1,
                            "is_connected": int(row[5]),
                            "username": row[6] or "",
                            "name": row[7] or "",
                            "auto_reply": int(row[8]) if row[8] is not None else 1,
                            "is_blocked": int(row[9]) if row[9] is not None else 0,
                            "created_at": row[10],
                            "updated_at": row[11]
                        })

                # 2. Query all channel chat history mappings
                async with db._db.execute(
                    "SELECT user_id, session_id, channel_message_id FROM channel_chat_histories"
                ) as cursor:
                    rows = await cursor.fetchall()
                    history_mappings_list = []
                    for row in rows:
                        history_mappings_list.append({
                            "user_id": row[0],
                            "session_id": row[1],
                            "channel_message_id": row[2]
                        })

                # 3. Create JSON payload
                backup_data = {
                    "users": users_list,
                    "history_mappings": history_mappings_list
                }
                json_str = json.dumps(backup_data, ensure_ascii=False, indent=2)
                file_content = json_str.encode("utf-8")
                
                input_file = BufferedInputFile(
                    file_content, filename="database_backup.json"
                )
                
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                caption = (
                    f"🗄 DATABASE BACKUP (JSON)\n"
                    f"👥 Total Users: {len(users_list)}\n"
                    f"📅 Date: {now_str}"
                )
                
                # 4. Retrieve the old backup message ID from database settings
                old_msg_id = await db.get_system_setting("db_backup_message_id")
                if old_msg_id:
                    try:
                        await self.bot.delete_message(
                            chat_id=self.channel_id,
                            message_id=int(old_msg_id)
                        )
                        logger.info(f"Deleted old database backup message (msg_id: {old_msg_id})")
                    except Exception as del_err:
                        logger.warning(f"Could not delete old backup message {old_msg_id}: {del_err}")
                        
                # 5. Send new document message to channel
                msg = await self.bot.send_document(
                    chat_id=self.channel_id,
                    document=input_file,
                    caption=caption
                )
                
                # 6. Pin this message to the channel so the bot can always retrieve it on startup via get_chat
                try:
                    await self.bot.pin_chat_message(
                        chat_id=self.channel_id,
                        message_id=msg.message_id,
                        disable_notification=True
                    )
                    logger.info("Pinned database backup message in channel")
                except Exception as pin_err:
                    logger.warning(f"Failed to pin database backup message: {pin_err}")
                
                # 7. Save the new message ID in database settings
                await db.set_system_setting("db_backup_message_id", str(msg.message_id))
                logger.info(f"Successfully backed up users database to channel as JSON (msg_id: {msg.message_id})")
                
            except Exception as e:
                logger.error(f"Error in backup_database_to_channel: {e}", exc_info=True)

    async def delete_session(self, user_id: int):
        """Delete session message from channel."""
        mapping = await db.get_session_mapping(user_id)

        if mapping and mapping.get("channel_message_id"):
            try:
                await self.bot.delete_message(
                    chat_id=self.channel_id,
                    message_id=mapping["channel_message_id"],
                )
                logger.info(
                    f"Deleted session from channel for user {user_id} "
                    f"(msg_id: {mapping['channel_message_id']})"
                )
            except Exception as e:
                logger.warning(f"Failed to delete session message: {e}")

        # Remove local mapping
        await db.delete_session_mapping(user_id)
        await db.disconnect_user(user_id)


# Singleton — initialized in bot.py after Bot is created
_channel_storage: ChannelSessionStorage | None = None


def init_channel_storage(bot: Bot):
    """Initialize channel storage with bot instance."""
    global _channel_storage
    _channel_storage = ChannelSessionStorage(bot)
    return _channel_storage


def get_channel_storage() -> ChannelSessionStorage | None:
    """Get initialized channel storage instance."""
    return _channel_storage

