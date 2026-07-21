import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import (
    User, Chat, Channel,
    MessageMediaPhoto, MessageMediaDocument,
    InputMediaPoll, Poll, PollAnswer, ReactionEmoji, InputChatUploadedPhoto,
    PhoneCallProtocol
)
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.messages import CreateChatRequest, SendReactionRequest, EditChatTitleRequest, EditChatAboutRequest, EditChatPhotoRequest
from telethon.tl.functions.channels import CreateChannelRequest, EditTitleRequest, EditPhotoRequest
from telethon.tl.functions.phone import RequestCallRequest, CreateGroupCallRequest
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PhoneNumberInvalidError,
    PasswordHashInvalidError,
    FloodWaitError,
    AuthKeyUnregisteredError,
)
from config import config
from database import db
from channel_storage import get_channel_storage

logger = logging.getLogger(__name__)


class UserSession:
    """Manages a single user's Telethon client session."""

    def __init__(self, user_id: int, session_string: str = ""):
        self.user_id = user_id
        self.client = TelegramClient(
            StringSession(session_string),
            config.API_ID,
            config.API_HASH,
            device_model="Desktop",
            system_version="Windows 11",
            app_version="4.16.8",
            lang_code="en",
            system_lang_code="en",
            connection_retries=3,
            retry_delay=1,
            timeout=30,
        )

    async def connect(self):
        """Connect the client, reconnecting if TCP dropped."""
        if not self.client.is_connected():
            await self.client.connect()
        self._setup_auto_reply_listener()

    def _setup_auto_reply_listener(self):
        """Register PM auto-reply event listener if not already registered."""
        if getattr(self, "_listener_registered", False):
            return
        self._listener_registered = True

        @self.client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and not e.via_bot_id))
        async def _on_private_message(event):
            try:
                # Check if user has auto_reply enabled in DB
                is_enabled = await db.get_auto_reply(self.user_id)
                if not is_enabled:
                    return

                sender = await event.get_sender()
                if not sender or getattr(sender, "bot", False) or getattr(sender, "is_self", False):
                    return

                sender_id = event.sender_id
                incoming_text = event.raw_text.strip()
                if not incoming_text:
                    return

                logger.info(f"Auto-reply triggered for user {self.user_id} from sender {sender_id}: '{incoming_text[:40]}'")

                # Fetch last 5 messages in this private chat
                messages = await self.client.get_messages(sender_id, limit=5)
                context_lines = []
                for m in reversed(messages):
                    if m.text:
                        s_name = "Siz" if m.out else (getattr(sender, "first_name", "") or "Foydalanuvchi")
                        context_lines.append(f"{s_name}: {m.text}")

                context_text = "\n".join(context_lines)
                user_lang = await db.get_user_language(self.user_id)

                sender_name = getattr(sender, 'first_name', '') or "do'st"
                prompt = (
                    f"Sening Telegram akkaunttinga '{sender_name}' ismli foydalanuvchidan shaxsiy xabar (lichka) keldi.\n"
                    f"Muloqot tarixi:\n{context_text}\n\n"
                    f"Oxirgi kelgan xabar: '{incoming_text}'\n\n"
                    f"VAZIFA: Foydalanuvchi nomidan unga do'stona, samimiy, tushunarli va qisqa javob yoz. "
                    f"Faqat javob matnini qaytar (JSON emas, ortiqcha izohsiz)."
                )

                from ai_handler import ask_ai
                ai_resp = await ask_ai(prompt, [], language=user_lang)
                reply_text = ai_resp.get("message", "").strip()

                if reply_text:
                    await event.reply(reply_text)
                    logger.info(f"Auto-reply successfully sent to {sender_id}: '{reply_text[:40]}'")
            except Exception as e:
                logger.error(f"Auto-reply listener error for user {self.user_id}: {e}", exc_info=True)

    async def disconnect(self):
        """Disconnect the client."""
        if self.client.is_connected():
            await self.client.disconnect()

    async def ensure_connected(self):
        """Force reconnect if connection is dead."""
        try:
            if not self.client.is_connected():
                await self.client.connect()
                return
            # Ping to verify connection is alive
            await self.client.get_me()
        except Exception:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            await self.client.connect()

    async def is_authorized(self) -> bool:
        """Check if the session is authorized."""
        await self.connect()
        return await self.client.is_user_authorized()

    def get_session_string(self) -> str:
        """Get the current session string for persistence."""
        return self.client.session.save()

    # ── Authentication ───────────────────────────────────────────────

    async def send_code(self, phone: str):
        """Send verification code to phone number."""
        await self.connect()
        result = await self.client.send_code_request(phone)
        return result

    async def sign_in(self, phone: str, code: str, phone_code_hash: str):
        """Sign in with phone and code. Handles reconnection gracefully."""
        # Ensure we're connected (reconnect if TCP dropped while user typed code)
        await self.connect()

        # Use low-level API directly to avoid Telethon's internal hash lookup
        # which can fail after reconnection
        try:
            result = await self.client(
                functions.auth.SignInRequest(
                    phone_number=phone,
                    phone_code_hash=phone_code_hash,
                    phone_code=str(code),
                )
            )
            # Update internal state
            if hasattr(result, 'user') and result.user:
                self.client._self_input_peer = types.InputPeerUser(
                    result.user.id,
                    result.user.access_hash or 0,
                )
            return result
        except SessionPasswordNeededError:
            raise  # Let caller handle 2FA


    async def sign_in_2fa(self, password: str):
        """Sign in with 2FA password."""
        await self.connect()
        return await self.client.sign_in(password=password)

    # ── Messaging ────────────────────────────────────────────────────

    async def send_message(self, chat_id, text: str, reply_to: int = None) -> dict:
        """Send a text message to a chat/user."""
        await self.connect()
        msg = await self.client.send_message(
            chat_id, text, reply_to=reply_to
        )
        return {
            "success": True,
            "message_id": msg.id,
            "chat": str(chat_id),
            "text": text[:100],
        }

    async def send_and_get_reply(self, chat_id, text: str, wait_seconds: float = 2.0) -> dict:
        """Send a message to a chat/bot and wait for reply messages."""
        await self.connect()
        sent_msg = await self.client.send_message(chat_id, text)
        await asyncio.sleep(wait_seconds)
        messages = await self.client.get_messages(chat_id, limit=3)
        reply_texts = []
        for msg in messages:
            if msg.id != sent_msg.id:
                reply_texts.append(msg.text or "")
        return {
            "success": True,
            "sent_text": text,
            "replies": reply_texts,
            "latest_reply": reply_texts[0] if reply_texts else "",
        }

    async def get_bot_token(self, bot_username: str) -> dict:
        """Retrieve bot API token from @BotFather for a given bot username."""
        await self.connect()
        bot_username = bot_username.strip()
        if not bot_username.startswith("@"):
            bot_username = f"@{bot_username}"

        # Send /token command to @BotFather
        sent_msg = await self.client.send_message("@BotFather", "/token")
        await asyncio.sleep(1.5)

        # Get response messages from @BotFather
        messages = await self.client.get_messages("@BotFather", limit=5)
        target_msg = None
        for msg in messages:
            if msg.buttons:
                target_msg = msg
                break

        if target_msg and target_msg.buttons:
            # Click button for bot_username
            clicked = False
            for row in target_msg.buttons:
                for btn in row:
                    if bot_username.lower() in btn.text.lower():
                        await btn.click()
                        clicked = True
                        break
                if clicked:
                    break
            
            if clicked:
                await asyncio.sleep(1.5)
                messages = await self.client.get_messages("@BotFather", limit=5)
                for msg in messages:
                    if msg.text and (":" in msg.text or "API" in msg.text or "token" in msg.text):
                        target_msg = msg
                        break

        # Fallback: check if @BotFather already sent token message directly
        if not target_msg:
            messages = await self.client.get_messages("@BotFather", limit=5)
            for msg in messages:
                if msg.text and bot_username.lower().replace("@", "") in msg.text.lower():
                    target_msg = msg
                    break

        if target_msg and target_msg.text:
            import re
            text = target_msg.text
            tokens = re.findall(r'\b\d{8,11}:[A-Za-z0-9_-]{35,}\b', text)
            if tokens:
                return {
                    "success": True,
                    "bot_username": bot_username,
                    "token": tokens[0],
                    "message": text,
                }
            return {
                "success": True,
                "bot_username": bot_username,
                "text": text,
            }

        return {
            "success": False,
            "error": f"{bot_username} uchun token topilmadi yoki u @BotFather da mavjud emas."
        }

    async def get_my_bots(self) -> dict:
        """Get list of user's bots created via @BotFather."""
        await self.connect()
        await self.client.send_message("@BotFather", "/mybots")
        await asyncio.sleep(1.5)
        messages = await self.client.get_messages("@BotFather", limit=5)
        
        bot_usernames = []
        for msg in messages:
            if msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        txt = btn.text.strip()
                        if txt and (txt.startswith("@") or "bot" in txt.lower()):
                            if txt not in bot_usernames:
                                bot_usernames.append(txt)
                        
        if not bot_usernames:
            history = await self.client.get_messages("@BotFather", limit=50)
            import re
            for msg in history:
                if msg.text:
                    found = re.findall(r't\.me/([A-Za-z0-9_]+bot)', msg.text, re.IGNORECASE)
                    for f in found:
                        u = f"@{f}"
                        if u not in bot_usernames:
                            bot_usernames.append(u)

        return {
            "success": True,
            "count": len(bot_usernames),
            "bots": bot_usernames,
        }

    # ── Profile Management ───────────────────────────────────────────

    async def update_profile(
        self, first_name: str = None, last_name: str = None, about: str = None
    ) -> dict:
        """Update user's profile first_name, last_name, or bio (about)."""
        await self.connect()
        kwargs = {}
        if first_name is not None:
            kwargs["first_name"] = first_name
        if last_name is not None:
            kwargs["last_name"] = last_name
        if about is not None:
            kwargs["about"] = about
        await self.client(UpdateProfileRequest(**kwargs))
        return {"success": True, "updated": kwargs}

    async def update_profile_photo(self, file_path: str) -> dict:
        """Upload a new profile picture."""
        await self.connect()
        file = await self.client.upload_file(file_path)
        await self.client(UploadProfilePhotoRequest(file=file))
        return {"success": True, "file_path": file_path}

    # ── Groups, Channels & Admin ─────────────────────────────────────

    async def create_group(self, title: str, users: list = None) -> dict:
        """Create a new basic Telegram group."""
        await self.connect()
        users = users or []
        result = await self.client(CreateChatRequest(users=users, title=title))
        chat_id = getattr(result.chats[0], "id", None) if getattr(result, "chats", None) else None
        return {"success": True, "title": title, "chat_id": chat_id}

    async def create_channel(
        self, title: str, about: str = "", is_megagroup: bool = False
    ) -> dict:
        """Create a new Telegram Channel or Supergroup."""
        await self.connect()
        result = await self.client(CreateChannelRequest(title=title, about=about, megagroup=is_megagroup))
        chat_id = getattr(result.chats[0], "id", None) if getattr(result, "chats", None) else None
        return {"success": True, "title": title, "chat_id": chat_id, "is_megagroup": is_megagroup}

    async def kick_chat_member(self, chat_id, user_id) -> dict:
        """Kick/Remove a participant from a group or channel."""
        await self.connect()
        await self.client.kick_participant(chat_id, user_id)
        return {"success": True, "chat": str(chat_id), "kicked_user": str(user_id)}

    async def promote_admin(self, chat_id, user_id, custom_title: str = "Admin") -> dict:
        """Promote a user to Admin in a group or channel."""
        await self.connect()
        await self.client.edit_admin(chat_id, user_id, is_admin=True, custom_title=custom_title)
        return {"success": True, "chat": str(chat_id), "promoted_user": str(user_id), "custom_title": custom_title}

    # ── Interactive Features ──────────────────────────────────────────

    async def send_reaction(self, chat_id, message_id: int, emoji: str = "👍") -> dict:
        """Send an emoji reaction to a message."""
        await self.connect()
        try:
            await self.client(SendReactionRequest(
                peer=chat_id,
                msg_id=message_id,
                reaction=[ReactionEmoji(emoticon=emoji)]
            ))
        except Exception:
            if hasattr(self.client, 'send_reaction'):
                await self.client.send_reaction(chat_id, message_id, emoji)
            else:
                raise
        return {"success": True, "chat": str(chat_id), "message_id": message_id, "emoji": emoji}

    async def create_poll(
        self, chat_id, question: str, options: list[str], is_quiz: bool = False, correct_option_id: int = 0
    ) -> dict:
        """Create a Poll or Quiz in a chat."""
        await self.connect()
        poll_answers = [PollAnswer(text=opt, option=bytes([i])) for i, opt in enumerate(options)]
        poll = Poll(
            id=0,
            question=question,
            answers=poll_answers,
            quiz=is_quiz,
            closed=False,
        )
        if is_quiz:
            solution = "To'g'ri javob!"
            correct_answers = [bytes([correct_option_id])]
            media = InputMediaPoll(
                poll=poll,
                correct_answers=correct_answers,
                solution=solution
            )
        else:
            media = InputMediaPoll(poll=poll)

        await self.client.send_file(chat_id, media)
        return {"success": True, "chat": str(chat_id), "question": question, "is_quiz": is_quiz}

    async def update_chat_title(self, chat_id, new_title: str) -> dict:
        """Update title/name of a group or channel."""
        await self.connect()
        try:
            await self.client(EditTitleRequest(channel=chat_id, title=new_title))
        except Exception:
            await self.client(EditChatTitleRequest(chat_id=chat_id, title=new_title))
        return {"success": True, "chat": str(chat_id), "new_title": new_title}

    async def update_chat_about(self, chat_id, new_about: str) -> dict:
        """Update description/about of a group or channel."""
        await self.connect()
        peer = await self.client.get_input_entity(chat_id)
        await self.client(EditChatAboutRequest(peer=peer, about=new_about))
        return {"success": True, "chat": str(chat_id), "new_about": new_about}

    async def update_chat_photo(self, chat_id, file_path: str) -> dict:
        """Update photo of a group or channel."""
        await self.connect()
        file = await self.client.upload_file(file_path)
        try:
            await self.client(EditPhotoRequest(channel=chat_id, photo=InputChatUploadedPhoto(file=file)))
        except Exception:
            await self.client(EditChatPhotoRequest(chat_id=chat_id, photo=InputChatUploadedPhoto(file=file)))
        return {"success": True, "chat": str(chat_id), "file_path": file_path}

    async def send_file(self, chat_id, file_path: str, caption: str = "") -> dict:
        """Send a file to a chat/user."""
        await self.connect()
        msg = await self.client.send_file(
            chat_id, file_path, caption=caption
        )
        return {
            "success": True,
            "message_id": msg.id,
            "chat": str(chat_id),
        }

    async def send_sticker(self, chat_id, sticker: str = "👍") -> dict:
        """Send a sticker to a chat (by emoji, keyword, file path, URL, or file_id)."""
        await self.connect()
        try:
            if "/" in sticker or "\\" in sticker or sticker.endswith(".webp"):
                msg = await self.client.send_file(chat_id, sticker)
                return {"success": True, "chat": str(chat_id), "message_id": msg.id}
            
            # Use inline query @sticker
            query = sticker if sticker else "smile"
            results = await self.client.inline_query("@sticker", query)
            if results:
                msg = await results[0].send(chat_id)
                return {"success": True, "chat": str(chat_id), "message_id": msg.id}
            else:
                msg = await self.client.send_file(chat_id, sticker)
                return {"success": True, "chat": str(chat_id), "message_id": msg.id}
        except Exception as e:
            logger.warning(f"send_sticker fallback: {e}")
            msg = await self.client.send_message(chat_id, sticker)
            return {"success": True, "chat": str(chat_id), "message_id": msg.id}

    async def send_gif(self, chat_id, gif: str = "happy") -> dict:
        """Send a GIF to a chat (by keyword, file path, URL, or file_id)."""
        await self.connect()
        try:
            if "/" in gif or "\\" in gif or gif.endswith(".gif") or gif.endswith(".mp4"):
                msg = await self.client.send_file(chat_id, gif)
                return {"success": True, "chat": str(chat_id), "message_id": msg.id}
            
            # Use inline query @gif
            query = gif if gif else "funny"
            results = await self.client.inline_query("@gif", query)
            if results:
                msg = await results[0].send(chat_id)
                return {"success": True, "chat": str(chat_id), "message_id": msg.id}
            else:
                msg = await self.client.send_file(chat_id, gif)
                return {"success": True, "chat": str(chat_id), "message_id": msg.id}
        except Exception as e:
            logger.warning(f"send_gif fallback: {e}")
            msg = await self.client.send_message(chat_id, gif)
            return {"success": True, "chat": str(chat_id), "message_id": msg.id}

    # ── Voice & Group Calls ──────────────────────────────────────────

    async def request_voice_call(self, user_id) -> dict:
        """Initiate a 1-on-1 Telegram voice call to a user."""
        await self.connect()
        peer = await self.client.get_input_user(user_id)
        import os, random
        g_a_hash = os.urandom(256)
        protocol = PhoneCallProtocol(
            min_layer=92,
            max_layer=92,
            udp_p2p=True,
            udp_reflector=True,
            library_versions=["2.4.0"]
        )
        await self.client(RequestCallRequest(
            user_id=peer,
            random_id=random.randint(1, 2147483647),
            g_a_hash=g_a_hash,
            protocol=protocol
        ))
        return {"success": True, "target_user": str(user_id), "message": "Ovozli qo'ng'iroq so'rovi yuborildi"}

    async def create_group_call(self, chat_id, title: str = "Ovozli muloqot") -> dict:
        """Start a Voice/Video Chat in a group or channel."""
        await self.connect()
        peer = await self.client.get_input_entity(chat_id)
        import random
        await self.client(CreateGroupCallRequest(
            peer=peer,
            random_id=random.randint(1, 2147483647),
            title=title
        ))
        return {"success": True, "chat": str(chat_id), "title": title}

    async def forward_message(
        self, from_chat, to_chat, message_ids: list[int]
    ) -> dict:
        """Forward messages from one chat to another."""
        await self.connect()
        result = await self.client.forward_messages(
            to_chat, message_ids, from_chat
        )
        count = len(result) if isinstance(result, list) else 1
        return {
            "success": True,
            "forwarded_count": count,
            "from": str(from_chat),
            "to": str(to_chat),
        }

    async def delete_messages(self, chat_id, message_ids: list[int]) -> dict:
        """Delete messages in a chat."""
        await self.connect()
        result = await self.client.delete_messages(chat_id, message_ids)
        return {
            "success": True,
            "deleted_count": len(message_ids),
            "chat": str(chat_id),
        }

    async def edit_message(self, chat_id, message_id: int, new_text: str) -> dict:
        """Edit a message."""
        await self.connect()
        msg = await self.client.edit_message(chat_id, message_id, new_text)
        return {
            "success": True,
            "message_id": msg.id,
            "new_text": new_text[:100],
        }

    async def pin_message(self, chat_id, message_id: int) -> dict:
        """Pin a message in a chat."""
        await self.connect()
        await self.client.pin_message(chat_id, message_id)
        return {"success": True, "pinned_message_id": message_id}

    async def unpin_message(self, chat_id, message_id: int = None) -> dict:
        """Unpin a message (or all if message_id is None)."""
        await self.connect()
        await self.client.unpin_message(chat_id, message_id)
        return {"success": True}

    # ── Reading ──────────────────────────────────────────────────────

    async def get_messages(
        self, chat_id, limit: int = 20, offset_id: int = 0
    ) -> list[dict]:
        """Get messages from a chat."""
        await self.connect()
        messages = await self.client.get_messages(
            chat_id, limit=limit, offset_id=offset_id
        )
        result = []
        for msg in messages:
            sender_name = ""
            if msg.sender:
                if hasattr(msg.sender, "first_name"):
                    sender_name = msg.sender.first_name or ""
                    if msg.sender.last_name:
                        sender_name += f" {msg.sender.last_name}"
                elif hasattr(msg.sender, "title"):
                    sender_name = msg.sender.title or ""

            btn_list = []
            if msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        if btn.text:
                            btn_list.append(btn.text)

            result.append({
                "id": msg.id,
                "sender": sender_name,
                "sender_id": msg.sender_id,
                "text": msg.text or "",
                "buttons": btn_list,
                "date": str(msg.date),
                "has_media": msg.media is not None,
                "reply_to_msg_id": msg.reply_to.reply_to_msg_id if msg.reply_to else None,
            })
        return result

    async def get_unread_messages(self, chat_id, limit: int = 50) -> list[dict]:
        """Get unread messages from a chat."""
        await self.connect()
        dialog = await self.client.get_entity(chat_id)
        # Get dialogs to find unread count
        dialogs = await self.client.get_dialogs()
        unread_count = 0
        for d in dialogs:
            if d.entity.id == dialog.id:
                unread_count = d.unread_count
                break

        if unread_count == 0:
            return []

        return await self.get_messages(chat_id, limit=min(unread_count, limit))

    async def mark_as_read(self, chat_id) -> dict:
        """Mark all messages in a chat as read."""
        await self.connect()
        await self.client.send_read_acknowledge(chat_id)
        return {"success": True, "chat": str(chat_id)}

    # ── Chats & Dialogs ──────────────────────────────────────────────

    async def get_dialogs(self, limit: int = 30) -> list[dict]:
        """Get list of chats/dialogs."""
        await self.connect()
        dialogs = await self.client.get_dialogs(limit=limit)
        result = []
        for d in dialogs:
            chat_type = "unknown"
            if isinstance(d.entity, User):
                chat_type = "user"
            elif isinstance(d.entity, Chat):
                chat_type = "group"
            elif isinstance(d.entity, Channel):
                chat_type = "channel" if d.entity.broadcast else "supergroup"

            result.append({
                "id": d.entity.id,
                "name": d.name or "Unknown",
                "type": chat_type,
                "unread_count": d.unread_count,
                "last_message": (d.message.text or "")[:80] if d.message else "",
                "date": str(d.date),
            })
        return result

    async def search_chats(self, query: str, limit: int = 10) -> list[dict]:
        """Search for chats/users by name."""
        await self.connect()
        result = await self.client.get_dialogs()
        matches = []
        for d in result:
            if query.lower() in (d.name or "").lower():
                chat_type = "user"
                if isinstance(d.entity, Chat):
                    chat_type = "group"
                elif isinstance(d.entity, Channel):
                    chat_type = "channel" if d.entity.broadcast else "supergroup"
                matches.append({
                    "id": d.entity.id,
                    "name": d.name,
                    "type": chat_type,
                })
                if len(matches) >= limit:
                    break
        return matches

    async def search_global(self, query: str, limit: int = 10) -> list[dict]:
        """Search globally for users/chats."""
        await self.connect()
        result = await self.client(functions.contacts.SearchRequest(
            q=query, limit=limit
        ))
        matches = []
        for user in result.users:
            matches.append({
                "id": user.id,
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                "username": user.username,
                "type": "user",
            })
        for chat in result.chats:
            matches.append({
                "id": chat.id,
                "name": chat.title,
                "username": getattr(chat, "username", None),
                "type": "channel" if getattr(chat, "broadcast", False) else "group",
            })
        return matches

    # ── Group/Channel Operations ─────────────────────────────────────

    async def join_chat(self, link_or_username: str) -> dict:
        """Join a group or channel by link or username."""
        await self.connect()
        if "joinchat/" in link_or_username or "+" in link_or_username:
            # Invite link
            hash_part = link_or_username.split("/")[-1].replace("+", "")
            result = await self.client(
                functions.messages.ImportChatInviteRequest(hash_part)
            )
        else:
            result = await self.client(
                functions.channels.JoinChannelRequest(link_or_username)
            )
        return {"success": True, "joined": link_or_username}

    async def leave_chat(self, chat_id) -> dict:
        """Leave a group or channel."""
        await self.connect()
        entity = await self.client.get_entity(chat_id)
        if isinstance(entity, Channel):
            await self.client(functions.channels.LeaveChannelRequest(entity))
        elif isinstance(entity, Chat):
            await self.client(functions.messages.DeleteChatUserRequest(
                entity.id, await self.client.get_me()
            ))
        return {"success": True, "left": str(chat_id)}

    async def get_chat_members(self, chat_id, limit: int = 50) -> list[dict]:
        """Get members of a group/channel."""
        await self.connect()
        participants = await self.client.get_participants(chat_id, limit=limit)
        return [
            {
                "id": p.id,
                "name": f"{p.first_name or ''} {p.last_name or ''}".strip(),
                "username": p.username,
                "is_bot": p.bot,
            }
            for p in participants
        ]

    # ── Profile / Account ───────────────────────────────────────────

    async def get_me(self) -> dict:
        """Get current user info."""
        await self.connect()
        me = await self.client.get_me()
        return {
            "id": me.id,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "username": me.username,
            "phone": me.phone,
        }

    async def get_user_info(self, user_id) -> dict:
        """Get info about a user/chat."""
        await self.connect()
        entity = await self.client.get_entity(user_id)
        if isinstance(entity, User):
            return {
                "id": entity.id,
                "first_name": entity.first_name,
                "last_name": entity.last_name,
                "username": entity.username,
                "phone": entity.phone,
                "is_bot": entity.bot,
                "type": "user",
            }
        elif isinstance(entity, (Chat, Channel)):
            return {
                "id": entity.id,
                "title": entity.title,
                "username": getattr(entity, "username", None),
                "type": "channel" if getattr(entity, "broadcast", False) else "group",
                "members_count": getattr(entity, "participants_count", None),
            }
        return {"id": entity.id, "type": "unknown"}

    # ── Contact Management ───────────────────────────────────────────

    async def add_contact(self, phone: str, first_name: str, last_name: str = "") -> dict:
        """Add a contact."""
        await self.connect()
        result = await self.client(functions.contacts.ImportContactsRequest(
            [types.InputPhoneContact(
                client_id=0,
                phone=phone,
                first_name=first_name,
                last_name=last_name,
            )]
        ))
        return {
            "success": True,
            "imported": len(result.imported),
        }

    async def get_contacts(self) -> list[dict]:
        """Get all contacts."""
        await self.connect()
        result = await self.client(functions.contacts.GetContactsRequest(hash=0))
        return [
            {
                "id": u.id,
                "name": f"{u.first_name or ''} {u.last_name or ''}".strip(),
                "username": u.username,
                "phone": u.phone,
            }
            for u in result.users
        ]


class SessionManager:
    """Manages multiple user sessions. Sessions stored in Telegram channel."""

    def __init__(self):
        self._sessions: dict[int, UserSession] = {}
        self._pending_auth: dict[int, dict] = {}  # Stores auth state during login

    async def get_session(self, user_id: int) -> UserSession | None:
        """Get an active session for a user, loading from channel if needed."""
        # Check memory cache first
        if user_id in self._sessions:
            session = self._sessions[user_id]
            try:
                if await session.is_authorized():
                    return session
            except (AuthKeyUnregisteredError, ConnectionError):
                del self._sessions[user_id]
                await db.disconnect_user(user_id)
                return None

        # Try loading from Telegram channel
        storage = get_channel_storage()
        if storage is None:
            logger.warning("Channel storage not initialized")
            return None

        try:
            session_data = await storage.load_session(user_id)
            if session_data and session_data.get("session_string"):
                session = UserSession(user_id, session_data["session_string"])
                try:
                    auth_status = await session.is_authorized()
                    logger.info(f"is_authorized check for user {user_id}: {auth_status}")
                    if auth_status:
                        self._sessions[user_id] = session
                        logger.info(f"Loaded session from channel for user {user_id}")
                        return session
                    else:
                        logger.warning(f"session.is_authorized() returned False for user {user_id}")
                except (AuthKeyUnregisteredError, ConnectionError) as exp_err:
                    logger.warning(f"Session from channel expired for user {user_id}: {exp_err}")
                    await db.disconnect_user(user_id)
                except Exception as auth_err:
                    logger.error(f"Error checking is_authorized for user {user_id}: {auth_err}", exc_info=True)
        except Exception as e:
            logger.error(f"Failed to load session from channel: {e}")

        return None

    def create_pending_session(self, user_id: int) -> UserSession:
        """Create a new session for authentication."""
        session = UserSession(user_id)
        self._pending_auth[user_id] = {"session": session}
        return session

    def get_pending_auth(self, user_id: int) -> dict | None:
        """Get pending authentication state."""
        return self._pending_auth.get(user_id)

    def update_pending_auth(self, user_id: int, **kwargs):
        """Update pending auth state."""
        if user_id in self._pending_auth:
            self._pending_auth[user_id].update(kwargs)

    async def finalize_session(self, user_id: int):
        """Finalize authentication and save session to Telegram channel."""
        pending = self._pending_auth.pop(user_id, None)
        if pending:
            session = pending["session"]
            session_string = session.get_session_string()
            phone = pending.get("phone", "")

            # Save to Telegram channel
            storage = get_channel_storage()
            if storage:
                try:
                    await storage.save_session(user_id, phone, session_string)
                    logger.info(f"Session saved to channel for user {user_id} ({phone})")
                except Exception as e:
                    logger.error(f"Failed to save session to channel: {e}")
                    raise

            self._sessions[user_id] = session

    async def remove_session(self, user_id: int):
        """Remove session from memory and delete from channel."""
        session = self._sessions.pop(user_id, None)
        if session:
            try:
                await session.client.log_out()
            except Exception:
                pass
            await session.disconnect()
        self._pending_auth.pop(user_id, None)

        # Delete from channel
        storage = get_channel_storage()
        if storage:
            try:
                await storage.delete_session(user_id)
            except Exception as e:
                logger.error(f"Failed to delete session from channel: {e}")

    async def cleanup_all(self):
        """Disconnect all active sessions (doesn't delete from channel)."""
        for session in self._sessions.values():
            try:
                await session.disconnect()
            except Exception:
                pass
        self._sessions.clear()
        self._pending_auth.clear()


# Singleton instance
session_manager = SessionManager()
