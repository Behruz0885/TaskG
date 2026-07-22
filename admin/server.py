import os
import json
import asyncio
import logging
from datetime import datetime
from aiohttp import web
from database import db
from session_manager import session_manager
from channel_storage import get_channel_storage

logger = logging.getLogger(__name__)

# Directory of this module (admin folder)
ADMIN_DIR = os.path.dirname(os.path.abspath(__file__))

async def get_index(request):
    """Serve the React admin panel HTML file."""
    html_path = os.path.join(ADMIN_DIR, "admin.html")
    if not os.path.exists(html_path):
        return web.Response(text="admin.html not found.", status=404)
    return web.FileResponse(html_path)

async def get_style(request):
    """Serve the CSS style sheet."""
    css_path = os.path.join(ADMIN_DIR, "style.css")
    if not os.path.exists(css_path):
        return web.Response(text="style.css not found.", status=404)
    return web.FileResponse(css_path)

async def get_app(request):
    """Serve the React JavaScript application file."""
    js_path = os.path.join(ADMIN_DIR, "app.js")
    if not os.path.exists(js_path):
        return web.Response(text="app.js not found.", status=404)
    return web.FileResponse(js_path)

async def api_get_stats(request):
    """Return live stats for dashboard."""
    try:
        # Get count of total connected users
        async with db._db.execute("SELECT COUNT(*) FROM channel_sessions WHERE is_connected = 1") as cursor:
            row = await cursor.fetchone()
            active_users = row[0] if row else 0

        # Get count of total command logs
        async with db._db.execute("SELECT COUNT(*) FROM command_log") as cursor:
            row = await cursor.fetchone()
            total_commands = row[0] if row else 0
            
        return web.json_response({
            "active_users": active_users,
            "total_commands": total_commands,
            "bot_status": "active"
        })
    except Exception as e:
        logger.error(f"Error in api_get_stats: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def api_get_users(request):
    """Return list of connected users with real-time online status and registration time."""
    try:
        async with db._db.execute(
            """SELECT user_id, phone, language, current_session_id, is_connected, created_at, username, name, is_blocked 
               FROM channel_sessions 
               ORDER BY created_at DESC"""
        ) as cursor:
            rows = await cursor.fetchall()
            users = []
            for row in rows:
                user_id = row[0]
                phone = row[1] or "—"
                language = row[2] or "uz"
                current_session_id = row[3] or 1
                is_connected = bool(row[4])
                created_at = row[5] or "—"
                username = row[6] or ""
                name = row[7] or ""
                
                # Check real-time connection status from session_manager
                is_online = False
                if user_id in session_manager._sessions:
                    try:
                        session = session_manager._sessions[user_id]
                        client = session.client
                        if client and client.is_connected():
                            is_online = True
                            # Self-healing: dynamically update name and username
                            me = await session.get_me()
                            if me:
                                username = me.get("username") or ""
                                first = me.get("first_name") or ""
                                last = me.get("last_name") or ""
                                name = f"{first} {last}".strip()
                                await db.update_user_details(user_id, username, name)
                    except Exception:
                        pass
                        
                # Fallback: if username or name is still empty, fetch from bot
                if (not username or not name) and "bot" in request.app and request.app["bot"]:
                    try:
                        chat = await request.app["bot"].get_chat(user_id)
                        if chat:
                            username = chat.username or ""
                            first = chat.first_name or ""
                            last = chat.last_name or ""
                            name = f"{first} {last}".strip()
                            await db.update_user_details(user_id, username, name)
                    except Exception:
                        pass
                        
                is_blocked = bool(row[8]) if len(row) > 8 and row[8] else False
                
                users.append({
                    "user_id": user_id,
                    "phone": phone,
                    "language": language,
                    "current_session_id": current_session_id,
                    "is_connected": is_connected,
                    "is_online": is_online,
                    "created_at": created_at,
                    "username": username,
                    "name": name,
                    "is_blocked": is_blocked
                })
        return web.json_response(users)
    except Exception as e:
        logger.error(f"Error in api_get_users: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def api_get_logs(request):
    """Return command execution logs with user details."""
    try:
        async with db._db.execute(
            """SELECT MAX(l.id) as id, l.user_id, l.command, l.result, l.status, MAX(l.created_at) as created_at, s.phone, s.username, s.name 
               FROM command_log l
               LEFT JOIN channel_sessions s ON l.user_id = s.user_id
               GROUP BY l.user_id
               ORDER BY created_at DESC"""
        ) as cursor:
            rows = await cursor.fetchall()
            logs = []
            for row in rows:
                user_id = row[1]
                phone = row[6] or "—"
                username = row[7] or ""
                name = row[8] or ""
                
                # Fetch dynamically via bot if missing
                if not username and "bot" in request.app and request.app["bot"]:
                    try:
                        chat = await request.app["bot"].get_chat(user_id)
                        if chat:
                            username = chat.username or ""
                            first = chat.first_name or ""
                            last = chat.last_name or ""
                            name = f"{first} {last}".strip()
                            await db.update_user_details(user_id, username, name)
                    except Exception:
                        pass
                        
                logs.append({
                    "id": row[0],
                    "user_id": user_id,
                    "command": row[2],
                    "result": row[3] or "",
                    "status": row[4],
                    "created_at": row[5],
                    "phone": phone,
                    "username": username,
                    "name": name
                })
        return web.json_response(logs)
    except Exception as e:
        logger.error(f"Error in api_get_logs: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def api_post_disconnect(request):
    """Disconnect a user session."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        if not user_id:
            return web.json_response({"error": "user_id is required"}, status=400)
            
        user_id = int(user_id)
        
        # Disconnect from session manager
        await session_manager.remove_session(user_id)
        
        # Delete using channel storage helper
        storage = get_channel_storage()
        if storage:
            await storage.delete_session(user_id)
        else:
            await db.delete_session_mapping(user_id)
            await db.disconnect_user(user_id)
            
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error in api_post_disconnect: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def api_post_clear_history(request):
    """Clear chat history for a user's active session."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        if not user_id:
            return web.json_response({"error": "user_id is required"}, status=400)
            
        user_id = int(user_id)
        current_session = await db.get_current_session_id(user_id)
        await db.clear_chat_history(user_id)
        
        # Also delete from channel storage
        storage = get_channel_storage()
        if storage:
            old_msg_id = await db.get_channel_chat_history_mapping(user_id, current_session)
            if old_msg_id:
                try:
                    await storage.bot.delete_message(chat_id=storage.channel_id, message_id=old_msg_id)
                except Exception:
                    pass
                    
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error in api_post_clear_history: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def api_post_broadcast(request):
    """Broadcast a message to all users in the database."""
    try:
        data = await request.json()
        message_text = data.get("message", "").strip()
        if not message_text:
            return web.json_response({"error": "message is required"}, status=400)
            
        bot = request.app.get("bot")
        if not bot:
            storage = get_channel_storage()
            if storage:
                bot = storage.bot
                
        if not bot:
            return web.json_response({"error": "Bot instance not available"}, status=500)
            
        success_count = 0
        fail_count = 0
        
        async with db._db.execute("SELECT DISTINCT user_id FROM channel_sessions") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                user_id = row[0]
                try:
                    await bot.send_message(chat_id=user_id, text=message_text, parse_mode="HTML")
                    success_count += 1
                    # Small delay between messages to respect Telegram limits
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.warning(f"Failed to send broadcast to {user_id}: {e}")
                    fail_count += 1
                    
        return web.json_response({
            "success": True,
            "success_count": success_count,
            "fail_count": fail_count
        })
    except Exception as e:
        logger.error(f"Error in api_post_broadcast: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def api_get_user_chat_history(request):
    """Return chat history for a specific user."""
    try:
        user_id = request.query.get("user_id")
        if not user_id:
            return web.json_response({"error": "user_id is required"}, status=400)
            
        user_id = int(user_id)
        
        async with db._db.execute(
            """SELECT id, role, content, created_at, session_id 
               FROM chat_history 
               WHERE user_id = ? 
               ORDER BY created_at ASC""",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            messages = []
            for row in rows:
                messages.append({
                    "id": row[0],
                    "role": row[1],
                    "content": row[2],
                    "created_at": row[3],
                    "session_id": row[4]
                })
        return web.json_response(messages)
    except Exception as e:
        logger.error(f"Error in api_get_user_chat_history: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def api_post_block_user(request):
    """Block or unblock a user."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        is_blocked = data.get("is_blocked", True)
        if not user_id:
            return web.json_response({"error": "user_id is required"}, status=400)
            
        user_id = int(user_id)
        await db.set_user_block_status(user_id, is_blocked)
        
        # If blocking, disconnect session if currently connected
        if is_blocked and user_id in session_manager._sessions:
            try:
                await session_manager.remove_session(user_id)
            except Exception:
                pass
                
        return web.json_response({"success": True, "is_blocked": is_blocked})
    except Exception as e:
        logger.error(f"Error in api_post_block_user: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def api_post_delete_user(request):
    """Permanently delete a user, their session, chat history, and all settings."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        if not user_id:
            return web.json_response({"error": "user_id is required"}, status=400)
            
        user_id = int(user_id)
        
        # 1. Disconnect and remove personal Telethon session
        try:
            await session_manager.remove_session(user_id)
        except Exception as e:
            logger.warning(f"Could not remove session during delete for user {user_id}: {e}")
            
        # 2. Delete session files from channel
        storage = get_channel_storage()
        if storage:
            try:
                await storage.delete_session(user_id)
            except Exception as e:
                logger.warning(f"Could not delete session file from channel for user {user_id}: {e}")
                
        # 3. Clean up SQLite database tables for this user
        await db._db.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        await db._db.execute("DELETE FROM command_log WHERE user_id = ?", (user_id,))
        await db._db.execute("DELETE FROM channel_sessions WHERE user_id = ?", (user_id,))
        await db._db.execute("DELETE FROM channel_chat_histories WHERE user_id = ?", (user_id,))
        await db._db.commit()
        
        # 4. Trigger database backup to update the channel JSON backup
        await db.trigger_backup()
        
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error in api_post_delete_user: {e}")
        return web.json_response({"error": str(e)}, status=500)

def create_admin_app(bot=None) -> web.Application:
    """Create and configure the web app."""
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/", get_index)
    app.router.add_get("/style.css", get_style)
    app.router.add_get("/app.js", get_app)
    app.router.add_get("/api/stats", api_get_stats)
    app.router.add_get("/api/users", api_get_users)
    app.router.add_get("/api/logs", api_get_logs)
    app.router.add_get("/api/chat_history", api_get_user_chat_history)
    app.router.add_post("/api/users/disconnect", api_post_disconnect)
    app.router.add_post("/api/users/clear_history", api_post_clear_history)
    app.router.add_post("/api/users/block", api_post_block_user)
    app.router.add_post("/api/users/delete", api_post_delete_user)
    app.router.add_post("/api/broadcast", api_post_broadcast)
    return app

async def start_admin_server(bot, port: int = 8000) -> web.AppRunner:
    """Start the web server asynchronously."""
    app = create_admin_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"⚡️ Admin Panel successfully started on http://localhost:{port}")
    return runner
