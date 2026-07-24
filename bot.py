import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    BotCommand,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    BufferedInputFile,
)
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PhoneNumberInvalidError,
    PasswordHashInvalidError,
    FloodWaitError,
)

from config import config
from database import db
from session_manager import session_manager
from channel_storage import init_channel_storage, get_channel_storage
from ai_handler import ask_ai, execute_actions, format_results, polish_text, synthesize_ai_response
from voice_handler import transcribe_voice
from voice_tts import text_to_voice_ogg, wants_voice_reply

# ── Logging ──────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── Router & States ──────────────────────────────────────────────────

router = Router()


class AuthStates(StatesGroup):
    """FSM states for account connection flow."""
    waiting_phone = State()
    waiting_code = State()
    waiting_2fa = State()
    waiting_language = State()


# ── Keyboards ────────────────────────────────────────────────────────

TEXTS = {
    "uz": {
        "history": "📜 Chatlar tarixi",
        "load_chat": "📥 #{session_id}-sonli suhbatni yuklash",
        "load": "📥 Yuklash",
        "new_chat": "➕ Yangi suhbat",
        "clear_history": "🗑 Tarixni o'chirish",
        "main_menu": "↩️ Asosiy menyu",
        "connect": "🔗 Akkauntni ulash",
        "cancel": "❌ Bekor qilish",
        "disconnect_confirm": "⚠️ Haqiqatan ham hisobni tizimdan uzishni istaysizmi?",
        "yes_disconnect": "✅ Ha, uzish",
        "no": "❌ Yo'q",
        "lang_changed": "✅ Muloqot tili o'zgartirildi!",
        "history_title": "🗂 <b>Suhbatlar Tarixi va Boshqaruv</b>\n\n<blockquote>Ushbu bo'limda siz sun'iy intellekt bilan olib borilgan suhbatlar tarixini boshqarishingiz, yangi suhbat ochishingiz yoki suhbatlar o'rtasida almashishingiz mumkin.</blockquote>\n\n",
        "connected_account": "✅ <b>Ulangan hisob:</b> <b>{name}</b>\n",
        "active_session": "\n🟢 <b>Hozirgi faol suhbat:</b> <b>#{session_id}-sonli suhbat</b>\n\n",
        "select_session_instruction": "<i>Quyidagi tugmalar orqali kerakli suhbatni tanlang yoki yangisini yarating:</i>",
        "session_activated": "\n🟢 <b>#{session_id}-sonli suhbat faollashtirildi!</b>\n💬 <b>TaskGramAiBot uchun buyruq yuboring:</b>",
        "new_session_title": "✨ <b>Yangi Suhbat Sessiyasi</b>\n\n<blockquote>Yangi toza suhbat sessiyasi boshlandi! Endi yuboradigan barcha buyruq va so'rovlaringiz ushbu yangi suhbat kontekstida bajariladi.</blockquote>\n\n",
        "new_session_active": "\n🟢 <b>Faol suhbat:</b> <b>#{session_id}-sonli yangi suhbat</b>\n💬 <b>TaskGramAiBot uchun buyruq yuboring:</b>",
        "must_connect": "📱 <b>Ishni boshlash uchun avval akkauntingizni ulang:</b>",
        "not_connected_warning": "⚠️ <b>Akkaunt ulanmagan.</b>\nUlash uchun /connect buyrug'ini yuboring.",
        "welcome_title": "🤖 <b>TaskGram AI Bot</b>\n\n<blockquote>Ushbu bot orqali siz o'z Telegram akkauntingizni <b>TaskGramAiBot</b> yordamida boshqarishingiz mumkin.</blockquote>\n\n",
        "welcome_instruction": "\n💬 <b>TaskGramAiBot uchun buyruq yuboring:</b>",
        "history_user": "👤 <b>Siz:</b>",
        "history_ai": "🤖 <b>AI:</b>",
        "history_empty": "📭 Suhbatlar tarixi bo'sh.",
        "load_question": "📊 <b>Suhbat tarixini qanday usulda yuklamoqchisiz?</b>",
        "btn_summary": "📊 AI Tahlili (Summary)",
        "btn_full": "💬 To'liq Tarix (Restore)",
    },
    "ru": {
        "history": "📜 История чатов",
        "load_chat": "📥 Загрузить чат №{session_id}",
        "load": "📥 Загрузить",
        "new_chat": "➕ Новый чат",
        "clear_history": "🗑 Очистить историю",
        "main_menu": "↩️ Главное меню",
        "connect": "🔗 Подключить аккаунт",
        "cancel": "❌ Отмена",
        "disconnect_confirm": "⚠️ Вы действительно хотите отключить аккаунт?",
        "yes_disconnect": "✅ Да, отключить",
        "no": "❌ Нет",
        "lang_changed": "✅ Язык общения успешно изменен!",
        "history_title": "🗂 <b>История чатов и управление</b>\n\n<blockquote>В этом разделе вы можете управлять историей ваших диалогов с ИИ, создавать новые чаты или переключаться между ними.</blockquote>\n\n",
        "connected_account": "✅ <b>Подключенный аккаунт:</b> <b>{name}</b>\n",
        "active_session": "\n🟢 <b>Текущий активный чат:</b> <b>Чат №{session_id}</b>\n\n",
        "select_session_instruction": "<i>Выберите нужный чат с помощью кнопок ниже или создайте новый:</i>",
        "session_activated": "\n🟢 <b>Чат №{session_id} активирован!</b>\n💬 <b>Отправьте команду для TaskGramAiBot:</b>",
        "new_session_title": "✨ <b>Новая сессия чата</b>\n\n<blockquote>Началась новая чистая сессия чата! Все ваши последующие команды будут выполняться в контексте этого нового чата.</blockquote>\n\n",
        "new_session_active": "\n🟢 <b>Активный чат:</b> <b>Новый чат №{session_id}</b>\n💬 <b>Отправьте команду для TaskGramAiBot:</b>",
        "must_connect": "📱 <b>Для начала работы необходимо подключить ваш аккаунт:</b>",
        "not_connected_warning": "⚠️ <b>Аккаунт не подключен.</b>\nОтправьте команду /connect для подключения.",
        "welcome_title": "🤖 <b>TaskGram AI Bot</b>\n\n<blockquote>Через этого бота вы можете управлять своим Telegram-аккаунтом с помощью <b>TaskGramAiBot</b>.</blockquote>\n\n",
        "welcome_instruction": "\n💬 <b>Отправьте команду для TaskGramAiBot:</b>",
        "history_user": "👤 <b>Вы:</b>",
        "history_ai": "🤖 <b>AI:</b>",
        "history_empty": "📭 История чата пуста.",
        "load_question": "📊 <b>Как вы хотите загрузить историю чата?</b>",
        "btn_summary": "📊 Анализ ИИ (Сводка)",
        "btn_full": "💬 Полная история (Восстановить)",
    },
    "en": {
        "history": "📜 Chat History",
        "load_chat": "📥 Load Chat #{session_id}",
        "load": "📥 Load",
        "new_chat": "➕ New Chat",
        "clear_history": "🗑 Clear History",
        "main_menu": "↩️ Main Menu",
        "connect": "🔗 Connect Account",
        "cancel": "❌ Cancel",
        "disconnect_confirm": "⚠️ Are you sure you want to disconnect account?",
        "yes_disconnect": "✅ Yes, Disconnect",
        "no": "❌ No",
        "lang_changed": "✅ Language successfully updated!",
        "history_title": "🗂 <b>Chat History & Management</b>\n\n<blockquote>In this section, you can manage your AI conversation history, open a new chat, or switch between chats.</blockquote>\n\n",
        "connected_account": "✅ <b>Connected Account:</b> <b>{name}</b>\n",
        "active_session": "\n🟢 <b>Current Active Chat:</b> <b>Chat #{session_id}</b>\n\n",
        "select_session_instruction": "<i>Choose the desired chat using the buttons below or create a new one:</i>",
        "session_activated": "\n🟢 <b>Chat #{session_id} activated!</b>\n💬 <b>Send a command for TaskGramAiBot:</b>",
        "new_session_title": "✨ <b>New Chat Session</b>\n\n<blockquote>A brand new clean chat session has started! All subsequent commands will execute within this new chat context.</blockquote>\n\n",
        "new_session_active": "\n🟢 <b>Active Chat:</b> <b>New Chat #{session_id}</b>\n💬 <b>Send a command for TaskGramAiBot:</b>",
        "must_connect": "📱 <b>You need to connect your account to get started:</b>",
        "not_connected_warning": "⚠️ <b>Account is not connected.</b>\nSend /connect to link your account.",
        "welcome_title": "🤖 <b>TaskGram AI Bot</b>\n\n<blockquote>Through this bot you can manage your Telegram account with the help of <b>TaskGramAiBot</b>.</blockquote>\n\n",
        "welcome_instruction": "\n💬 <b>Send a command for TaskGramAiBot:</b>",
        "history_user": "👤 <b>You:</b>",
        "history_ai": "🤖 <b>AI:</b>",
        "history_empty": "📭 Chat history is empty.",
        "load_question": "📊 <b>How would you like to load the chat history?</b>",
        "btn_summary": "📊 AI Analysis (Summary)",
        "btn_full": "💬 Full History (Restore)",
    }
}


async def main_menu_keyboard(
    is_connected: bool = False,
    user_id: int = None,
    show_sessions: bool = False,
    mode: str = "welcome",
) -> InlineKeyboardMarkup | None:
    """Generate main menu inline keyboard tailored to mode ('welcome', 'sessions', 'new_chat', 'selected_session')."""
    lang = "uz"
    if user_id is not None:
        lang = await db.get_user_language(user_id) or "uz"
    t = TEXTS.get(lang, TEXTS["uz"])

    buttons = []
    if is_connected:
        if mode == "new_chat":
            buttons.append([
                InlineKeyboardButton(text=t["history"], callback_data="manage_chat_sessions"),
            ])
        elif show_sessions and user_id is not None:
            sessions = await db.get_user_sessions(user_id)
            current_session = await db.get_current_session_id(user_id)
            
            # Create numbered buttons row for sessions
            session_row = []
            for s_id in sessions[:6]: # Limit to last 6 sessions to fit nicely in one row
                indicator = "🟢 " if s_id == current_session else ""
                session_row.append(
                    InlineKeyboardButton(text=f"{indicator}{s_id}", callback_data=f"select_session_{s_id}")
                )
            buttons.append(session_row)
            
            if mode == "selected_session":
                buttons.append([
                    InlineKeyboardButton(text=t["load_chat"].format(session_id=current_session), callback_data="load_chat_session"),
                ])
                buttons.append([
                    InlineKeyboardButton(text=t["new_chat"], callback_data="new_chat_session"),
                    InlineKeyboardButton(text=t["clear_history"], callback_data="clear_chat_history"),
                ])
                buttons.append([
                    InlineKeyboardButton(text=t["main_menu"], callback_data="back_to_welcome"),
                ])
            else:  # mode == "sessions" or default
                buttons.append([
                    InlineKeyboardButton(text=t["load"], callback_data="load_chat_session"),
                    InlineKeyboardButton(text=t["new_chat"], callback_data="new_chat_session"),
                ])
                buttons.append([
                    InlineKeyboardButton(text=t["clear_history"], callback_data="clear_chat_history"),
                    InlineKeyboardButton(text=t["main_menu"], callback_data="back_to_welcome"),
                ])
        else:
            buttons.append([
                InlineKeyboardButton(text=t["history"], callback_data="manage_chat_sessions"),
            ])
    else:
        buttons.append([
            InlineKeyboardButton(text=t["connect"], callback_data="connect"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel button keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])


def confirm_disconnect_keyboard() -> InlineKeyboardMarkup:
    """Confirm disconnect keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, uzish", callback_data="confirm_disconnect"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="cancel_disconnect"),
        ]
    ])


def phone_share_keyboard() -> ReplyKeyboardMarkup:
    """Phone number share keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def language_selection_keyboard() -> InlineKeyboardMarkup:
    """Generate keyboard for language selection."""
    buttons = [
        [
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        ],
        [
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)





# ── /start Command ───────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    await state.clear()
    user_id = message.from_user.id
    
    # Automatically create a brand new clean chat session for every /start
    new_session_id = await db.create_new_session(user_id)
    
    session = await session_manager.get_session(user_id)
    is_connected = session is not None

    welcome_text = (
        "🤖 <b>TaskGram AI Bot</b>\n\n"
        "<blockquote>Ushbu bot orqali siz o'z Telegram akkauntingizni <b>TaskGramAiBot</b> yordamida boshqarishingiz mumkin.</blockquote>\n\n"
    )

    if is_connected:
        try:
            me = await session.get_me()
            name = me.get("first_name", "")
            if me.get("last_name"):
                name += f" {me['last_name']}"
            welcome_text += f"✅ <b>Ulangan hisob:</b> <b>{name}</b>\n"
            if me.get("username"):
                welcome_text += f"   <code>@{me['username']}</code>\n"
            welcome_text += (
                f"\n🟢 <b>#{new_session_id}-sonli yangi toza suhbat boshlandi!</b>\n"
                f"💬 <b>TaskGramAiBot uchun buyruq yuboring:</b>"
            )
        except Exception:
            welcome_text += f"🟢 <b>#{new_session_id}-sonli yangi toza suhbat boshlandi!</b>\n💬 Buyruq yuboring:"
    else:
        welcome_text += "📱 Boshlash uchun hisobingizni (akkauntingizni) ulashingiz lozim:"

    msg = await message.answer(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=await main_menu_keyboard(is_connected, user_id, show_sessions=True, mode="new_chat"),
    )
    user_last_msg_id[user_id] = msg.message_id


async def safe_edit_text(message: Message, status_msg: Message, text: str, **kwargs):
    """Safely edit status_msg or send a new message if editing fails, falling back to plain text on HTML parse errors.

    Tracks the user's last message id so it stays correct even when the fallback
    path deletes the status message and resends the content.
    """
    user_id = message.from_user.id

    def _track(result):
        if result is not None:
            user_last_msg_id[user_id] = result.message_id
        return result

    try:
        return _track(await status_msg.edit_text(text, **kwargs))
    except Exception as e:
        logger.warning(f"safe_edit_text edit failed: {e}. Trying plain text fallback...")
        try:
            kwargs_plain = kwargs.copy()
            kwargs_plain.pop("parse_mode", None)
            return _track(await status_msg.edit_text(text, **kwargs_plain))
        except Exception:
            pass

        try:
            await status_msg.delete()
        except Exception:
            pass

        try:
            return _track(await message.answer(text, **kwargs))
        except Exception as e2:
            logger.warning(f"safe_edit_text answer failed: {e2}. Trying plain text answer fallback...")
            kwargs_plain = kwargs.copy()
            kwargs_plain.pop("parse_mode", None)
            return _track(await message.answer(text, **kwargs_plain))


# ── /help Command ────────────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    help_text = (
        "📖 <b>Yo'riqnoma va yordam</b>\n\n"
        "<b>Asosiy buyruqlar:</b>\n"
        "/start - Dasturni ishga tushirish\n"
        "/connect - Telegram hisobni ulash\n"
        "/disconnect - Telegram hisobni uzish\n"
        "/status - Hisob holatini tekshirish\n"
        "/cancel - Joriy amalni bekor qilish\n"
        "/clear - Suhbat tarixini tozalash\n\n"
        "<b>Sun'iy intellekt (AI) bilan ishlash:</b>\n"
        "Hisobingizni ulagandan so'ng, matn yoki ovoz shaklida buyruq yuboring, tizim uni avtomatik bajaradi:\n\n"
        "📌 <i>Misollar:</i>\n"
        "• <code>@username ga 'Salom' deb yoz</code>\n"
        "• <code>Oxirgi 5 ta xabarni ko'rsat</code>\n"
        "• <code>@channel_name kanaliga qo'shil</code>\n"
        "• <code>Chatlarimni ko'rsat</code>\n"
        "• <code>O'qilmagan xabarlarni ko'rsat</code>\n"
        "• <code>Xabarni forward qil</code>\n"
        "• <code>Kontaktlarimni ko'rsat</code>\n"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)


# ── /cancel Command ──────────────────────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel any active FSM state."""
    current = await state.get_state()
    if current is None:
        await message.answer("🤷 Bekor qilinadigan faol jarayon mavjud emas.")
        return
    await state.clear()
    await message.answer(
        "❌ Amaliyot bekor qilindi.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(F.text == "❌ Bekor qilish")
async def text_cancel(message: Message, state: FSMContext):
    """Handle cancel button text."""
    await state.clear()
    await message.answer(
        "❌ Amaliyot bekor qilindi.",
        reply_markup=ReplyKeyboardRemove(),
    )


# ── Account Connection Flow ──────────────────────────────────────────

@router.message(Command("connect"))
async def cmd_connect(message: Message, state: FSMContext):
    """Start account connection process."""
    user_id = message.from_user.id

    # Check if already connected
    session = await session_manager.get_session(user_id)
    if session:
        await message.answer(
            "✅ Hisobingiz allaqachon ulangan.\n"
            "Qayta ulanish uchun avval /disconnect buyrug'ini yuboring.",
        )
        return

    await state.set_state(AuthStates.waiting_phone)
    await message.answer(
        "📱 <b>Hisobni ulash</b>\n\n"
        "Iltimos, telefon raqamingizni yuboring yoki matn ko'rinishida kiriting.\n"
        "Format: <code>+998901234567</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=phone_share_keyboard(),
    )


@router.callback_query(F.data == "connect")
async def cb_connect(callback: CallbackQuery, state: FSMContext):
    """Connect button callback."""
    await callback.answer()
    user_id = callback.from_user.id
    session = await session_manager.get_session(user_id)
    if session:
        await callback.message.edit_text(
            "✅ Hisobingiz allaqachon ulangan.",
        )
        return

    await state.set_state(AuthStates.waiting_phone)
    await callback.message.edit_text(
        "📱 <b>Hisobni ulash</b>\n\n"
        "Iltimos, telefon raqamingizni yuboring.\n"
        "Format: <code>+998901234567</code>",
        parse_mode=ParseMode.HTML,
    )


# Handle phone number input
@router.message(AuthStates.waiting_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    """Handle phone from contact share."""
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"
    await _process_phone(message, state, phone)


@router.message(AuthStates.waiting_phone)
async def process_phone_text(message: Message, state: FSMContext):
    """Handle phone from text input."""
    phone = message.text.strip()
    if not phone.startswith("+"):
        phone = f"+{phone}"
    await _process_phone(message, state, phone)


async def _process_phone(message: Message, state: FSMContext, phone: str):
    """Process phone number and send verification code."""
    user_id = message.from_user.id

    # Remove reply keyboard first if present
    remove_msg = await message.answer(
        "⏳ Telegram serveriga ulanish amalga oshirilmoqda...",
        reply_markup=ReplyKeyboardRemove(),
    )

    try:
        # Create session and connect
        pending_session = session_manager.create_pending_session(user_id)

        # Step 1: Connect to Telegram (can be slow for first time)
        try:
            await asyncio.wait_for(
                pending_session.connect(),
                timeout=30,
            )
        except asyncio.TimeoutError:
            await remove_msg.delete()
            await message.answer(
                "❌ Telegram serveriga ulanib bo'lmadi (kutish vaqti tugadi).\n"
                "Iltimos, tarmoq ulanishini tekshiring va /connect buyrug'i orqali qayta urining.",
            )
            await state.clear()
            return

        # Step 2: Send verification code
        try:
            result = await asyncio.wait_for(
                pending_session.send_code(phone),
                timeout=30,
            )
        except asyncio.TimeoutError:
            await remove_msg.delete()
            await message.answer(
                "❌ Tasdiqlash kodini yuborishda kutish vaqti tugadi. Iltimos, /connect buyrug'i orqali qayta urining.",
            )
            await state.clear()
            return

        phone_code_hash = result.phone_code_hash

        # Store hash in BOTH pending_auth AND FSM state
        session_manager.update_pending_auth(
            user_id,
            phone=phone,
            phone_code_hash=phone_code_hash,
        )

        await state.set_state(AuthStates.waiting_code)
        await state.update_data(
            phone=phone,
            phone_code_hash=phone_code_hash,
        )

        # Clean up temp message and send new prompt
        try:
            await remove_msg.delete()
        except Exception:
            pass

        prompt_msg = await message.answer(
            "📩 <b>TASDIQLASH KODI YUBORILDI</b>\n\n"
            "⚠️ <b>DIQQAT! MUHIM YO'RIQNOMA:</b>\n"
            "Telegram xavfsizlik tizimi kodingizni bloklab qo'ymasligi uchun raqamlar orasiga <b>PROBEL (bo'shliq)</b> qo'yib yuboring!\n\n"
            "✅ <b>To'g'ri shakl:</b>\n"
            "<code>5 4 3 2 1</code>  👈 <i>(ushbu ko'rinishda yuboring)</i>\n\n"
            "❌ <b>Noto'g'ri shakl:</b>\n"
            "<s>54321</s>  👈 <i>(bloklanishiga sabab bo'ladi)</i>\n\n"
            "💡 <i>Tizim koddagi bo'shliqlarni avtomatik ravishda olib tashlaydi.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_keyboard(),
        )
        await state.update_data(prompt_message_id=prompt_msg.message_id)
        logger.info(f"Code sent to {phone} for user {user_id}, hash={phone_code_hash[:10]}...")

    except PhoneNumberInvalidError:
        try:
            await remove_msg.delete()
        except Exception:
            pass
        await message.answer(
            "❌ Telefon raqami noto'g'ri kiritildi.\n"
            "Format: <code>+998901234567</code>\n\n"
            "Iltimos, qaytadan kiriting:",
            parse_mode=ParseMode.HTML,
        )
    except FloodWaitError as e:
        try:
            await remove_msg.delete()
        except Exception:
            pass
        await message.answer(
            f"⏳ Telegram cheklovi o'rnatildi.\n"
            f"Iltimos, {e.seconds} soniya kutib, /connect buyrug'i orqali qayta urining.",
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Phone processing error for user {user_id}: {e}", exc_info=True)
        try:
            await remove_msg.delete()
        except Exception:
            pass
        await message.answer(
            f"❌ Tizimda xatolik yuz berdi: {str(e)}\n\n"
            f"Iltimos, /connect buyrug'i orqali qayta urining.",
        )
        await state.clear()


# Handle verification code from text input
@router.message(AuthStates.waiting_code)
async def process_code(message: Message, state: FSMContext):
    """Handle verification code from text input."""
    user_id = message.from_user.id
    raw_code = message.text.strip()
    code = "".join(c for c in raw_code if c.isdigit())

    if not code or len(code) < 3:
        await message.answer(
            "⚠️ Iltimos, faqat raqamlardan iborat tasdiqlash kodini kiriting.\n"
            "Masalan: <code>5 4 3 2 1</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        await message.delete()
    except Exception:
        pass

    fsm_data = await state.get_data()
    prompt_msg_id = fsm_data.get("prompt_message_id")

    async def update_status_msg(text: str, reply_markup=None):
        if prompt_msg_id:
            try:
                return await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=prompt_msg_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
            except Exception:
                pass
        return await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

    await update_status_msg("⏳ Tasdiqlash kodi tekshirilmoqda...")

    pending = session_manager.get_pending_auth(user_id)
    if not pending:
        await update_status_msg(
            "❌ Sessiya topilmadi yoki uning amal qilish muddati tugagan.\n"
            "Iltimos, /connect buyrug'i orqali jarayonni qaytadan boshlang.",
        )
        await state.clear()
        return

    session = pending["session"]
    phone = pending.get("phone", "")
    phone_code_hash = pending.get("phone_code_hash", "")

    if not phone_code_hash:
        phone_code_hash = fsm_data.get("phone_code_hash", "")
        phone = phone or fsm_data.get("phone", "")

    if not phone_code_hash:
        await update_status_msg(
            "❌ Tasdiqlash ma'lumotlari topilmadi.\n"
            "Iltimos, /connect buyrug'i orqali jarayonni qaytadan boshlang.",
        )
        await state.clear()
        return

    try:
        logger.info(f"Signing in user {user_id}, phone={phone}, code_len={len(code)}")

        await asyncio.wait_for(
            session.sign_in(phone, code, phone_code_hash),
            timeout=30,
        )

        # Success! Save session
        await session_manager.finalize_session(user_id)
        me = await session.get_me()
        name = me.get("first_name", "")
        if me.get("last_name"):
            name += f" {me['last_name']}"

        await state.update_data(name=name, phone=phone)
        await state.set_state(AuthStates.waiting_language)

        await update_status_msg(
            f"✅ <b>Hisobingiz muvaffaqiyatli ulandi!</b>\n\n"
            f"👤 {name}\n"
            f"📱 {phone}\n\n"
            f"🌐 <b>Muloqot tilini tanlang / Выберите язык общения / Select language:</b>",
            reply_markup=language_selection_keyboard(),
        )
        logger.info(f"User {user_id} successfully connected account: {phone}, prompting language")

    except SessionPasswordNeededError:
        # 2FA required
        await state.set_state(AuthStates.waiting_2fa)
        await update_status_msg(
            "🔐 <b>Ikki bosqichli tasdiqlash (2FA)</b>\n\n"
            "Ushbu hisobda ikki bosqichli tasdiqlash yoqilgan.\n"
            "Iltimos, parolingizni kiriting:",
            reply_markup=cancel_keyboard(),
        )

    except PhoneCodeInvalidError:
        await update_status_msg(
            "❌ <b>NOTO'G'RI KOD!</b>\n\n"
            "Iltimos, Telegram orqali yuborilgan kodni tekshirib, <b>probellar bilan</b> qaytadan kiriting:\n\n"
            "✅ <code>5 4 3 2 1</code>\n\n"
            "❌ <s>54321</s>",
            reply_markup=cancel_keyboard(),
        )

    except PhoneCodeExpiredError:
        await state.clear()
        await update_status_msg(
            "⏰ <b>TASDIQLASH KODINING AMAL QILISH MUDDATI TUGADI!</b>\n\n"
            "⚠️ Telegram xavfsizlik xizmati kodingizni chatda ochiq ko'rgani sababli uni bekor qildi.\n\n"
            "💡 Qayta urinish uchun /connect buyrug'ini yuboring va tasdiqlash kodini raqamlar orasiga <b>probel (bo'shliq)</b> qo'ygan holda, masalan <code>5 4 3 2 1</code> ko'rinishida yuboring.",
        )

    except asyncio.TimeoutError:
        await update_status_msg(
            "❌ Telegram serveridan javob olinmadi (vaqt tugadi).\n"
            "Iltimos, /connect buyrug'i orqali qayta urining.",
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Code verification error for user {user_id}: {e}", exc_info=True)
        await update_status_msg(
            f"❌ Xatolik yuz berdi: {str(e)}\n\n"
            f"Iltimos, /connect buyrug'i orqali qayta urining.",
        )
        await state.clear()


# Handle 2FA password
@router.message(AuthStates.waiting_2fa)
async def process_2fa(message: Message, state: FSMContext):
    """Handle 2FA password input."""
    user_id = message.from_user.id
    password = message.text.strip()

    pending = session_manager.get_pending_auth(user_id)
    if not pending:
        await message.answer("❌ Sessiya topilmadi. Iltimos, /connect buyrug'i orqali jarayonni qaytadan boshlang.")
        await state.clear()
        return

    session = pending["session"]
    phone = pending.get("phone", "")

    # Delete password message for security
    try:
        await message.delete()
    except Exception:
        pass

    fsm_data = await state.get_data()
    prompt_msg_id = fsm_data.get("prompt_message_id")

    async def update_status_msg(text: str, reply_markup=None):
        if prompt_msg_id:
            try:
                return await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=prompt_msg_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
            except Exception:
                pass
        return await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

    await update_status_msg("⏳ Parol tekshirilmoqda...")

    try:
        await session.sign_in_2fa(password)
        await session_manager.finalize_session(user_id)
        me = await session.get_me()
        name = me.get("first_name", "")
        if me.get("last_name"):
            name += f" {me['last_name']}"

        await state.update_data(name=name, phone=phone)
        await state.set_state(AuthStates.waiting_language)

        await update_status_msg(
            f"✅ <b>Hisobingiz muvaffaqiyatli ulandi!</b>\n\n"
            f"👤 {name}\n"
            f"📱 {phone}\n\n"
            f"🌐 <b>Muloqot tilini tanlang / Выберите язык общения / Select language:</b>",
            reply_markup=language_selection_keyboard(),
        )
    except PasswordHashInvalidError:
        await update_status_msg(
            "❌ Kiritilgan parol noto'g'ri. Iltimos, qaytadan kiriting.",
            reply_markup=cancel_keyboard(),
        )
    except Exception as e:
        logger.error(f"2FA error: {e}")
        await update_status_msg(f"❌ Xatolik yuz berdi: {str(e)}")
        await state.clear()


# ── Account Disconnect ────────────────────────────────────────────────

@router.message(Command("disconnect"))
async def cmd_disconnect(message: Message):
    """Start disconnect process."""
    user_id = message.from_user.id
    session = await session_manager.get_session(user_id)
    if not session:
        await message.answer("⚠️ Tizimga ulangan hisob mavjud emas.")
        return

    await message.answer(
        "⚠️ <b>Hisobni uzish</b>\n\n"
        "Haqiqatan ham hisobni tizimdan uzishni istaysizmi?\n"
        "Bu joriy sessiyani bekor qiladi.",
        parse_mode=ParseMode.HTML,
        reply_markup=confirm_disconnect_keyboard(),
    )


@router.callback_query(F.data == "disconnect")
async def cb_disconnect(callback: CallbackQuery):
    """Disconnect button callback."""
    await callback.answer()
    await callback.message.edit_text(
        "⚠️ <b>Hisobni uzish</b>\n\n"
        "Haqiqatan ham hisobni tizimdan uzishni istaysizmi?",
        parse_mode=ParseMode.HTML,
        reply_markup=confirm_disconnect_keyboard(),
    )


@router.callback_query(F.data == "confirm_disconnect")
async def cb_confirm_disconnect(callback: CallbackQuery):
    """Confirm disconnect."""
    await callback.answer()
    user_id = callback.from_user.id
    await session_manager.remove_session(user_id)
    await db.clear_chat_history(user_id)

    await callback.message.edit_text(
        "✅ Hisob tizimdan muvaffaqiyatli uzildi.\n"
        "Qayta ulanish uchun /connect buyrug'ini yuboring.",
        reply_markup=await main_menu_keyboard(is_connected=False, user_id=user_id),
    )


@router.callback_query(F.data == "cancel_disconnect")
async def cb_cancel_disconnect(callback: CallbackQuery):
    """Cancel disconnect."""
    await callback.answer("Bekor qilindi")
    user_id = callback.from_user.id
    await callback.message.edit_text(
        "👌 Amaliyot bekor qilindi. Hisob tizimga ulangan holda qoldi.",
        reply_markup=await main_menu_keyboard(is_connected=True, user_id=user_id),
    )


# ── Status & Info Callbacks ───────────────────────────────────────────

@router.message(Command("status"))
async def cmd_status(message: Message):
    """Show account status."""
    user_id = message.from_user.id
    session = await session_manager.get_session(user_id)

    if not session:
        await message.answer(
            "⚠️ Hisob tizimga ulanmagan.\nIltimos, uni /connect buyrug'i orqali ulang.",
            reply_markup=await main_menu_keyboard(is_connected=False, user_id=user_id),
        )
        return

    try:
        me = await session.get_me()
        name = f"{me.get('first_name', '')} {me.get('last_name', '')}".strip()
        username = f"@{me['username']}" if me.get("username") else "—"
        phone = me.get("phone", "—")

        await message.answer(
            f"👤 <b>Hisob holati (Akkaunt)</b>\n\n"
            f"📛 Ism va familiya: {name}\n"
            f"🔖 Foydalanuvchi nomi: {username}\n"
            f"📱 Telefon raqami: +{phone}\n"
            f"🟢 Holat: Faol (Ulangan)",
            parse_mode=ParseMode.HTML,
            reply_markup=await main_menu_keyboard(is_connected=True, user_id=user_id),
        )
    except Exception as e:
        await message.answer(f"❌ Hisob ma'lumotlarini yuklashda xatolik yuz berdi: {e}")


@router.message(Command("autoreply"))
async def cmd_autoreply(message: Message):
    """Toggle AI auto-reply for private messages."""
    user_id = message.from_user.id
    current = await db.get_auto_reply(user_id)
    new_state = not current
    await db.set_auto_reply(user_id, new_state)
    
    state_str = "🟢 <b>YOQILDI</b>\n\n<i>Endi shaxsiyingizga (lichka) kelgan xabarlarga AI avtomatik ravishda sizning nomingizdan samimiy javob beradi!</i>" if new_state else "🔴 <b>O'CHIRILDI</b>\n\n<i>Avto-javob funksiyasi to'xtatildi.</i>"
    await message.answer(
        f"🤖 <b>Shaxsiy xabarlarga AI avto-javob:</b> {state_str}",
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data == "account_info")
async def cb_account_info(callback: CallbackQuery):
    """Show account info."""
    await callback.answer()
    user_id = callback.from_user.id
    session = await session_manager.get_session(user_id)

    if not session:
        await callback.message.edit_text("⚠️ Hisob tizimga ulanmagan.")
        return

    try:
        me = await session.get_me()
        name = f"{me.get('first_name', '')} {me.get('last_name', '')}".strip()
        username = f"@{me['username']}" if me.get("username") else "—"
        phone = me.get("phone", "—")

        await callback.message.edit_text(
            f"👤 <b>Hisob ma'lumotlari</b>\n\n"
            f"📛 Ism va familiya: {name}\n"
            f"🔖 Foydalanuvchi nomi: {username}\n"
            f"📱 Telefon raqami: +{phone}\n"
            f"🆔 Identifikator (ID): {me.get('id', '—')}",
            parse_mode=ParseMode.HTML,
            reply_markup=await main_menu_keyboard(is_connected=True, user_id=user_id),
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Xatolik yuz berdi: {e}")


# ── Clear History ─────────────────────────────────────────────────────

@router.message(Command("clear"))
async def cmd_clear(message: Message):
    """Clear AI chat history."""
    user_id = message.from_user.id
    current_session = await db.get_current_session_id(user_id)
    await db.clear_chat_history(user_id)
    
    storage = get_channel_storage()
    if storage:
        old_msg_id = await db.get_channel_chat_history_mapping(user_id, current_session)
        if old_msg_id:
            try:
                await message.bot.delete_message(chat_id=storage.channel_id, message_id=old_msg_id)
            except Exception:
                pass
                
    await message.answer(f"🗑 {current_session}-sonli suhbat tarixi muvaffaqiyatli tozalandi.")


@router.callback_query(F.data == "clear_chat_history")
async def cb_clear_chat_history(callback: CallbackQuery):
    """Callback to clear chat history."""
    user_id = callback.from_user.id
    current_session = await db.get_current_session_id(user_id)
    await callback.answer(f"{current_session}-sonli suhbat tarixi tozalandi")
    await db.clear_chat_history(user_id)
    
    storage = get_channel_storage()
    if storage:
        old_msg_id = await db.get_channel_chat_history_mapping(user_id, current_session)
        if old_msg_id:
            try:
                await callback.bot.delete_message(chat_id=storage.channel_id, message_id=old_msg_id)
            except Exception:
                pass
                
    await callback.message.answer(f"🗑 {current_session}-sonli suhbat tarixi muvaffaqiyatli tozalandi.")


user_last_msg_id: dict[int, int] = {}


async def safe_edit_callback(callback: CallbackQuery, text: str, reply_markup=None):
    """Safely edit the clicked callback query message itself to avoid editing wrong messages."""
    user_id = callback.from_user.id
    try:
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
        user_last_msg_id[user_id] = callback.message.message_id
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            try:
                msg = await callback.message.answer(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
                user_last_msg_id[user_id] = msg.message_id
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error editing callback message: {e}")


@router.callback_query(F.data == "load_chat_session")
async def cb_load_chat_session(callback: CallbackQuery):
    """Present load options (Summary vs Full history)."""
    user_id = callback.from_user.id
    lang = await db.get_user_language(user_id) or "uz"
    t = TEXTS.get(lang, TEXTS["uz"])
    
    await callback.answer()
    
    # Show options keyboard
    buttons = [
        [
            InlineKeyboardButton(text=t["btn_summary"], callback_data="load_mode_summary"),
            InlineKeyboardButton(text=t["btn_full"], callback_data="load_mode_full"),
        ],
        [
            InlineKeyboardButton(text=t["cancel"], callback_data="back_to_welcome"),
        ]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(t["load_question"], parse_mode=ParseMode.HTML, reply_markup=markup)


@router.callback_query(F.data == "load_mode_summary")
async def cb_load_mode_summary(callback: CallbackQuery):
    """Load session history and run AI summary analysis on it showing last 2 messages."""
    user_id = callback.from_user.id
    current_session = await db.get_current_session_id(user_id)
    lang = await db.get_user_language(user_id) or "uz"
    t = TEXTS.get(lang, TEXTS["uz"])
    
    # Delete options message
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.answer()
    
    session = await session_manager.get_session(user_id)
    if not session:
        await callback.message.answer(t["not_connected_warning"])
        return
        
    # Get last 2 messages from history
    history = await db.get_chat_history_for_session(user_id, current_session, limit=50)
    last_two_lines = []
    if history:
        last_two = history[-2:] if len(history) >= 2 else history
        for msg in last_two:
            role_label = "Foydalanuvchi" if msg["role"] == "user" else "AI"
            last_two_lines.append(f"{role_label}: '{msg['content']}'")
            
    last_two_str = "\n".join(last_two_lines) if last_two_lines else "—"

    # Generate custom prompt with last 2 messages
    if lang == "ru":
        prompt_text = (
            f"Вот последние 2 сообщения из беседы #{current_session}:\n{last_two_str}\n\n"
            f"Пожалуйста, проанализируй эту беседу, объясни её пользователю чётко и понятно, "
            f"а также обязательно отобрази/укажи эти последние 2 сообщения в начале или конце своего ответа."
        )
    elif lang == "en":
        prompt_text = (
            f"Here are the last 2 messages from conversation #{current_session}:\n{last_two_str}\n\n"
            f"Please analyze this conversation, explain it clearly and understandably to the user, "
            f"and make sure to show/include these last 2 messages in your response."
        )
    else:  # uz
        prompt_text = (
            f"Mana #{current_session}-sonli suhbatdan oxirgi yuborilgan 2 ta xabar:\n{last_two_str}\n\n"
            f"Iltimos, ushbu suhbatni foydalanuvchiga juda aniq va tushunarli qilib tushuntirib ber "
            f"va o'sha oxirgi 2 ta yuborilgan xabarni ham o'z javobingda alohida ko'rsatib o't."
        )

    loading_text = {
        "uz": "⚡️ <b>TaskGramAiBot so'rovingizni o'rganmoqda</b> <code>[▱▱▱▱▱]</code>",
        "ru": "⚡️ <b>TaskGramAiBot изучает ваш запрос</b> <code>[▱▱▱▱▱]</code>",
        "en": "⚡️ <b>TaskGramAiBot is studying your request</b> <code>[▱▱▱▱▱]</code>"
    }.get(lang, "uz")

    status_msg = await callback.message.answer(
        loading_text,
        parse_mode=ParseMode.HTML,
    )
    user_last_msg_id[user_id] = status_msg.message_id
    await _process_ai_text(user_id, prompt_text, session, status_msg, callback.message)


@router.callback_query(F.data == "load_mode_full")
async def cb_load_mode_full(callback: CallbackQuery):
    """Load and restore actual chat history messages into the bot chat."""
    user_id = callback.from_user.id
    current_session = await db.get_current_session_id(user_id)
    lang = await db.get_user_language(user_id) or "uz"
    t = TEXTS.get(lang, TEXTS["uz"])
    
    # Delete options message
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.answer()
    
    history = await db.get_chat_history_for_session(user_id, current_session, limit=50)
    if not history:
        await callback.message.answer(t["history_empty"])
        return
        
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "").strip()
        if not content:
            continue
            
        if role == "user":
            prefix = t["history_user"]
            try:
                await callback.message.answer(f"{prefix}\n{content}", parse_mode=ParseMode.HTML)
            except TelegramBadRequest:
                await callback.message.answer(f"{prefix}\n{content}")
        else:
            prefix = t["history_ai"]
            if len(content) > 3800:
                chunks = smart_split_html(content, limit=3800)
                for i, chunk in enumerate(chunks):
                    prefix_chunk = prefix if i == 0 else ""
                    text_to_send = f"{prefix_chunk}\n{chunk}".strip()
                    try:
                        await callback.message.answer(text_to_send, parse_mode=ParseMode.HTML)
                    except TelegramBadRequest:
                        await callback.message.answer(text_to_send)
                    await asyncio.sleep(0.4)
            else:
                try:
                    await callback.message.answer(f"{prefix}\n{content}", parse_mode=ParseMode.HTML)
                except TelegramBadRequest:
                    await callback.message.answer(f"{prefix}\n{content}")
        
        # Pacing delay between sequential message prints to avoid phone freeze/lag
        await asyncio.sleep(0.6)


@router.callback_query(F.data.startswith("select_session_"))
async def cb_select_session(callback: CallbackQuery):
    """Switch the active chat session."""
    session_id = int(callback.data.replace("select_session_", ""))
    user_id = callback.from_user.id
    
    await db.save_current_session_id(user_id, session_id)
    lang = await db.get_user_language(user_id) or "uz"
    t = TEXTS.get(lang, TEXTS["uz"])
    
    await callback.answer(f"#{session_id}" if lang != "uz" else f"#{session_id}-sonli suhbat yuklandi")
    
    session = await session_manager.get_session(user_id)
    if session:
        try:
            me = await session.get_me()
            name = me.get("first_name", "")
            if me.get("last_name"):
                name += f" {me['last_name']}"
                
            welcome_text = t["history_title"] + t["connected_account"].format(name=name)
            if me.get("username"):
                welcome_text += f"   <code>@{me['username']}</code>\n"
            welcome_text += t["session_activated"].format(session_id=session_id)
        except Exception:
            welcome_text = t["history_title"] + t["session_activated"].format(session_id=session_id)
    else:
        welcome_text = t["must_connect"]
        
    markup = await main_menu_keyboard(is_connected=session is not None, user_id=user_id, show_sessions=True, mode="selected_session")
    await safe_edit_callback(callback, welcome_text, reply_markup=markup)


@router.callback_query(F.data == "new_chat_session")
async def cb_new_chat_session(callback: CallbackQuery):
    """Create a new chat session."""
    user_id = callback.from_user.id
    new_id = await db.create_new_session(user_id)
    lang = await db.get_user_language(user_id) or "uz"
    t = TEXTS.get(lang, TEXTS["uz"])
    
    await callback.answer(f"#{new_id}" if lang != "uz" else f"Yangi suhbat #{new_id} yaratildi")
    
    session = await session_manager.get_session(user_id)
    if session:
        try:
            me = await session.get_me()
            name = me.get("first_name", "")
            if me.get("last_name"):
                name += f" {me['last_name']}"
                
            welcome_text = t["new_session_title"] + t["connected_account"].format(name=name)
            if me.get("username"):
                welcome_text += f"   <code>@{me['username']}</code>\n"
            welcome_text += t["new_session_active"].format(session_id=new_id)
        except Exception:
            welcome_text = t["new_session_title"] + t["new_session_active"].format(session_id=new_id)
    else:
        welcome_text = t["must_connect"]
        
    markup = await main_menu_keyboard(is_connected=session is not None, user_id=user_id, show_sessions=True, mode="new_chat")
    await safe_edit_callback(callback, welcome_text, reply_markup=markup)


@router.callback_query(F.data == "manage_chat_sessions")
async def cb_manage_chat_sessions(callback: CallbackQuery):
    """Show the session management keyboard."""
    await callback.answer()
    user_id = callback.from_user.id
    lang = await db.get_user_language(user_id) or "uz"
    t = TEXTS.get(lang, TEXTS["uz"])
    
    session = await session_manager.get_session(user_id)
    if not session:
        markup = await main_menu_keyboard(is_connected=False, user_id=user_id, show_sessions=False, mode="welcome")
        await safe_edit_callback(callback, t["not_connected_warning"], reply_markup=markup)
        return
        
    try:
        me = await session.get_me()
        name = me.get("first_name", "")
        if me.get("last_name"):
            name += f" {me['last_name']}"
            
        welcome_text = t["history_title"] + t["connected_account"].format(name=name)
        if me.get("username"):
            welcome_text += f"   <code>@{me['username']}</code>\n"
    except Exception:
        welcome_text = t["history_title"]
        
    current_session = await db.get_current_session_id(user_id)
    welcome_text += t["active_session"].format(session_id=current_session) + t["select_session_instruction"]
    markup = await main_menu_keyboard(is_connected=True, user_id=user_id, show_sessions=True, mode="sessions")
    await safe_edit_callback(callback, welcome_text, reply_markup=markup)


@router.callback_query(F.data == "back_to_welcome")
async def cb_back_to_welcome(callback: CallbackQuery):
    """Go back to the welcome screen with only Chatlar tarixi button."""
    await callback.answer()
    user_id = callback.from_user.id
    lang = await db.get_user_language(user_id) or "uz"
    t = TEXTS.get(lang, TEXTS["uz"])
    
    session = await session_manager.get_session(user_id)
    if not session:
        markup = await main_menu_keyboard(is_connected=False, user_id=user_id, show_sessions=False)
        await safe_edit_callback(callback, t["not_connected_warning"], reply_markup=markup)
        return
        
    try:
        me = await session.get_me()
        name = me.get("first_name", "")
        if me.get("last_name"):
            name += f" {me['last_name']}"
            
        welcome_text = t["welcome_title"] + t["connected_account"].format(name=name)
        if me.get("username"):
            welcome_text += f"   <code>@{me['username']}</code>\n"
        welcome_text += t["welcome_instruction"]
    except Exception:
        welcome_text = t["welcome_title"] + t["welcome_instruction"]
        
    markup = await main_menu_keyboard(is_connected=True, user_id=user_id, show_sessions=False)
    await safe_edit_callback(callback, welcome_text, reply_markup=markup)


# ── Cancel Callback ───────────────────────────────────────────────────

@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel button callback."""
    await callback.answer("Bekor qilindi")
    await state.clear()
    await callback.message.edit_text("❌ Amaliyot bekor qilindi.")


# ── Help Callback ─────────────────────────────────────────────────────

@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    """Help button callback."""
    await callback.answer()
    help_text = (
        "📖 <b>Yordam bo'limi</b>\n\n"
        "1️⃣ /connect — Telegram hisobni ulash\n"
        "2️⃣ Istalgan buyruqni matn yoki ovoz shaklida yuboring — Tizim uni avtomatik ravishda bajaradi\n\n"
        "<b>Misollar:</b>\n"
        "• <code>@username ga salom yoz</code>\n"
        "• <code>Chatlarimni ko'rsat</code>\n"
        "• <code>Oxirgi xabarlarni o'qi</code>\n"
        "• <code>@channel ga qo'shil</code>\n"
    )
    await callback.message.edit_text(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=await main_menu_keyboard(is_connected=True, user_id=callback.from_user.id),
    )


# ── AI Chat Callback ─────────────────────────────────────────────────

@router.callback_query(F.data == "ai_chat")
async def cb_ai_chat(callback: CallbackQuery):
    """AI chat mode callback."""
    await callback.answer()
    await callback.message.edit_text(
        "🤖 <b>Sun'iy intellekt (AI) tizimi faol!</b>\n\n"
        "Iltimos, bajarilishi lozim bo'lgan buyruqni yuboring.\n\n"
        "<i>Masalan: 'Saved Messages ga salom yoz'</i>",
        parse_mode=ParseMode.HTML,
    )


# ── Language Settings ────────────────────────────────────────────────

@router.message(Command("language"))
@router.message(Command("lang"))
async def cmd_language(message: Message, state: FSMContext):
    """Command to change communication language."""
    user_id = message.from_user.id
    session = await session_manager.get_session(user_id)
    is_connected = session is not None
    
    name = message.from_user.first_name or "Foydalanuvchi"
    phone = ""
    if is_connected:
        mapping = await db.get_session_mapping(user_id)
        if mapping:
            phone = mapping.get("phone", "")
            
    await state.update_data(name=name, phone=phone)
    await state.set_state(AuthStates.waiting_language)
    
    await message.answer(
        "🌐 <b>Muloqot tilini tanlang / Выберите язык общения / Select language:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=language_selection_keyboard(),
    )


@router.callback_query(AuthStates.waiting_language, F.data.startswith("lang_"))
async def cb_select_language(callback: CallbackQuery, state: FSMContext):
    """Handle language selection."""
    await callback.answer()
    language = callback.data.replace("lang_", "")
    user_id = callback.from_user.id
    
    await db.save_user_language(user_id, language)
    
    fsm_data = await state.get_data()
    name = fsm_data.get("name", "Foydalanuvchi")
    phone = fsm_data.get("phone", "")
    
    await state.clear()
    
    if language == "ru":
        welcome_msg = (
            f"✅ <b>Язык общения изменен!</b>\n\n"
            f"👤 {name}\n"
            f"📱 {phone}\n"
            f"🌐 Установлен язык: 🇷🇺 Русский\n\n"
            f"Отправьте мне команду (текстом или голосом), и я ее выполню! 🚀"
        )
    elif language == "en":
        welcome_msg = (
            f"✅ <b>Language changed!</b>\n\n"
            f"👤 {name}\n"
            f"📱 {phone}\n"
            f"🌐 Set language: 🇬🇧 English\n\n"
            f"Send me a command (text or voice) and I will execute it! 🚀"
        )
    else:  # uz
        welcome_msg = (
            f"✅ <b>Muloqot tili muvaffaqiyatli o'zgartirildi!</b>\n\n"
            f"👤 {name}\n"
            f"📱 {phone}\n"
            f"🌐 O'rnatilgan til: 🇺🇿 O'zbekcha\n\n"
            f"Iltimos, buyruqni matn yoki ovoz ko'rinishida yuboring. Tizim uni avtomatik tarzda bajaradi! 🚀"
        )
        
    session = await session_manager.get_session(user_id)
    await callback.message.edit_text(
        welcome_msg,
        parse_mode=ParseMode.HTML,
        reply_markup=await main_menu_keyboard(is_connected=session is not None, user_id=user_id),
    )


# ── Live Loading Animation ────────────────────────────────────────────

class StatusAnimator:
    """Animated loading status indicator for Telegram messages."""
    def __init__(self, message: Message, lang: str = "uz"):
        self.message = message
        self.lang = lang
        self._task = None
        self._running = False

    async def _animate(self):
        frames_dict = {
            "uz": [
                "⚡️ <b>TaskGramAiBot so'rovingizni o'rganmoqda</b> <code>[▱▱▱▱▱]</code>",
                "✨ <b>TaskGramAiBot so'rovingizni tahlil qilmoqda</b> <code>[█▱▱▱▱]</code>",
                "🧠 <b>TaskGramAiBot fikrlamoqda va rejalashtirmoqda</b> <code>[██▱▱▱]</code>",
                "⚙️ <b>TaskGramAiBot amallarni bajarmoqda</b> <code>[███▱▱]</code>",
                "🔮 <b>TaskGramAiBot javobni tayyorlamoqda</b> <code>[████▱]</code>",
                "🚀 <b>TaskGramAiBot natijani shakllantirmoqda</b> <code>[█████]</code>",
            ],
            "ru": [
                "⚡️ <b>TaskGramAiBot изучает ваш запрос</b> <code>[▱▱▱▱▱]</code>",
                "✨ <b>TaskGramAiBot анализирует ваш запрос</b> <code>[█▱▱▱▱]</code>",
                "🧠 <b>TaskGramAiBot думает и планирует</b> <code>[██▱▱▱]</code>",
                "⚙️ <b>TaskGramAiBot выполняет действия</b> <code>[███▱▱]</code>",
                "🔮 <b>TaskGramAiBot готовит ответ</b> <code>[████▱]</code>",
                "🚀 <b>TaskGramAiBot формирует результат</b> <code>[█████]</code>",
            ],
            "en": [
                "⚡️ <b>TaskGramAiBot is studying your request</b> <code>[▱▱▱▱▱]</code>",
                "✨ <b>TaskGramAiBot is analyzing your request</b> <code>[█▱▱▱▱]</code>",
                "🧠 <b>TaskGramAiBot is thinking and planning</b> <code>[██▱▱▱]</code>",
                "⚙️ <b>TaskGramAiBot is executing actions</b> <code>[███▱▱]</code>",
                "🔮 <b>TaskGramAiBot is preparing response</b> <code>[████▱]</code>",
                "🚀 <b>TaskGramAiBot is generating result</b> <code>[█████]</code>",
            ]
        }
        frames = frames_dict.get(self.lang, frames_dict["uz"])
        idx = 0
        while self._running:
            await asyncio.sleep(1.4)
            if not self._running:
                break
            idx += 1
            frame = frames[idx % len(frames)]
            try:
                await self.message.edit_text(frame, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.debug(f"Animator edit skipped: {e}")

    async def __aenter__(self):
        self._running = True
        self._task = asyncio.create_task(self._animate())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


import re


def smart_split_html(text: str, max_len: int = 3800) -> list[str]:
    """
    Splits long HTML formatted text into chunks <= max_len.
    Splits at double newlines, single newlines, or spaces to avoid breaking words/HTML tags.
    Ensures HTML tags like <b>, <i>, <code>, <s>, <u>, <blockquote>, <a> are properly closed and reopened across chunks.
    """
    if len(text) <= max_len:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        cut_index = max_len

        # Prefer splitting at paragraph breaks \n\n
        p_break = remaining.rfind("\n\n", 0, max_len)
        if p_break > max_len // 2:
            cut_index = p_break + 2
        else:
            # Otherwise split at line breaks \n
            n_break = remaining.rfind("\n", 0, max_len)
            if n_break > max_len // 3:
                cut_index = n_break + 1
            else:
                # Otherwise split at space
                s_break = remaining.rfind(" ", 0, max_len)
                if s_break > max_len // 4:
                    cut_index = s_break + 1

        chunk = remaining[:cut_index]
        remaining = remaining[cut_index:]

        # Clean HTML tag balance in chunk
        tag_pattern = re.compile(r'</?(?:b|i|code|s|u|blockquote|a)[^>]*>')
        tags = tag_pattern.findall(chunk)
        
        active_tags = []
        for tag in tags:
            if tag.startswith("</"):
                tag_name = tag[2:-1].split()[0]
                for idx in range(len(active_tags) - 1, -1, -1):
                    if active_tags[idx].startswith(f"<{tag_name}"):
                        active_tags.pop(idx)
                        break
            elif not tag.endswith("/>"):
                active_tags.append(tag)

        closing_tags = ""
        reopen_tags = ""
        for tag in reversed(active_tags):
            tag_name = tag[1:-1].split()[0]
            closing_tags += f"</{tag_name}>"
            reopen_tags = tag + reopen_tags

        chunk += closing_tags
        chunks.append(chunk)

        if remaining:
            remaining = reopen_tags + remaining

    return chunks


# ── Main AI Message Handler ──────────────────────────────────────────
# This must be registered LAST to catch all unhandled text messages

async def _send_voice_reply(original_message: Message, response_text: str, language: str):
    """Synthesize the AI answer to speech and send it as a Telegram voice message.

    Best-effort: on any failure it stays silent (the text reply was already sent).
    """
    try:
        try:
            await original_message.bot.send_chat_action(original_message.chat.id, "record_voice")
        except Exception:
            pass

        ogg_bytes = await text_to_voice_ogg(response_text, language=language)
        if not ogg_bytes:
            logger.warning("Voice reply requested but TTS produced no audio.")
            return

        await original_message.answer_voice(
            BufferedInputFile(ogg_bytes, filename="voice.ogg")
        )
    except Exception as e:
        logger.warning(f"Failed to send voice reply: {e}")


async def _process_ai_text(
    user_id: int,
    user_text: str,
    session,
    status_msg: Message,
    original_message: Message,
    is_voice: bool = False,
    voice_bytes: bytes = None,
):
    """Core logic: forwards text to AI and executes returned actions via Telethon."""
    try:
        # Get chat history from DB
        chat_history = await db.get_chat_history(user_id)

        # Determine AI model to use
        ai_model = "mistral.voxtral-small-24b-2507" if (is_voice or voice_bytes) else None

        # Save user message
        chat_label = user_text if not voice_bytes else "[🗣 Ovozli buyruq]"
        await db.add_chat_message(user_id, "user", chat_label)

        # Get user language
        language = await db.get_user_language(user_id)

        # Start live animated progress
        action_results = []
        async with StatusAnimator(status_msg, lang=language):
            # Ask AI
            ai_response = await ask_ai(user_text, chat_history, language=language, model=ai_model, voice_bytes=voice_bytes)

            # Execute actions if any
            if ai_response.get("actions"):
                action_results = await execute_actions(session, ai_response["actions"])
                
                synthesized = await synthesize_ai_response(
                    user_text=chat_label,
                    ai_message=ai_response.get("message", ""),
                    action_results=action_results,
                    chat_history=chat_history,
                    language=language,
                    model=ai_model,
                    voice_bytes=voice_bytes,
                )
                if synthesized:
                    response_text = synthesized
                else:
                    response_text = format_results(ai_response, action_results)
            else:
                response_text = ai_response.get("message", "")

        # Save AI response
        await db.add_chat_message(user_id, "assistant", response_text)

        # Upload chat history to storage channel in background
        storage = get_channel_storage()
        if storage:
            session_id = await db.get_current_session_id(user_id)
            asyncio.create_task(storage.save_chat_history_to_channel(user_id, session_id))

        # Log command
        status = "success" if all(
            r.get("success") for r in action_results
        ) else "partial" if action_results else "chat"
        await db.log_command(user_id, user_text, response_text[:500], status)

        # Send response safely split into chunks if long
        chunks = smart_split_html(response_text or "✅ Bajarildi.", max_len=3800)
        
        # First chunk edits the status message
        await safe_edit_text(original_message, status_msg, chunks[0], parse_mode=ParseMode.HTML)
        user_last_msg_id[user_id] = status_msg.message_id
        
        # Subsequent chunks sent as new messages below
        for chunk in chunks[1:]:
            try:
                msg = await original_message.answer(chunk, parse_mode=ParseMode.HTML)
            except Exception:
                msg = await original_message.answer(chunk)
            user_last_msg_id[user_id] = msg.message_id

        # If the user asked the AI to reply with voice ("ovoz bilan yubor",
        # "gapir", "скажи голосом", "speak"...), also send a spoken version.
        if wants_voice_reply(user_text):
            await _send_voice_reply(original_message, response_text, language)

    except Exception as e:
        logger.error(f"AI handler error for user {user_id}: {e}", exc_info=True)
        await safe_edit_text(
            original_message,
            status_msg,
            f"❌ Tizimda xatolik yuz berdi: {str(e)}\n\n"
            "Iltimos, qaytadan urinib ko'ring yoki /clear buyrug'i yordamida suhbat tarixini tozalang.",
            parse_mode=ParseMode.HTML,
        )


@router.message(F.text)
async def handle_ai_message(message: Message, state: FSMContext):
    """Main handler for text messages."""
    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    if await db.is_user_blocked(user_id):
        await message.answer("🚫 <b>Sizning hisobingiz admin tomonidan bloklangan.</b>", parse_mode=ParseMode.HTML)
        return

    user_text = message.text.strip()

    session = await session_manager.get_session(user_id)
    if not session:
        await message.answer(
            "⚠️ Iltimos, avval hisobingizni (akkaunt) ulang.\n"
            "Buning uchun /connect buyrug'ini yuboring.",
            reply_markup=await main_menu_keyboard(is_connected=False),
        )
        return

    lang = await db.get_user_language(user_id) or "uz"
    loading_text = {
        "uz": "⚡️ <b>TaskGramAiBot so'rovingizni o'rganmoqda</b> <code>[▱▱▱▱▱]</code>",
        "ru": "⚡️ <b>TaskGramAiBot изучает ваш запрос</b> <code>[▱▱▱▱▱]</code>",
        "en": "⚡️ <b>TaskGramAiBot is studying your request</b> <code>[▱▱▱▱▱]</code>"
    }.get(lang, "uz")

    status_msg = await message.answer(
        loading_text,
        parse_mode=ParseMode.HTML,
    )
    user_last_msg_id[user_id] = status_msg.message_id
    await _process_ai_text(user_id, user_text, session, status_msg, message)


@router.message(F.voice | F.audio)
async def handle_voice_message(message: Message, state: FSMContext):
    """Handler for voice and audio messages (Speech-to-Text)."""
    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    if await db.is_user_blocked(user_id):
        await message.answer("🚫 <b>Sizning hisobingiz admin tomonidan bloklangan.</b>", parse_mode=ParseMode.HTML)
        return

    session = await session_manager.get_session(user_id)
    if not session:
        await message.answer(
            "⚠️ Iltimos, avval hisobingizni (akkaunt) ulang.\n"
            "Buning uchun /connect buyrug'ini yuboring.",
            reply_markup=await main_menu_keyboard(is_connected=False),
        )
        return

    status_msg = await message.answer("🎧 Ovozli xabar yuklanmoqda...")
    user_last_msg_id[user_id] = status_msg.message_id

    try:
        voice = message.voice or message.audio
        file_io = await message.bot.download(voice)
        voice_bytes = file_io.read()

        await status_msg.edit_text(
            "🤔 <b>Sun'iy intellekt ovozli xabarni eshitmoqda va tahlil qilmoqda...</b>",
            parse_mode=ParseMode.HTML,
        )

        await _process_ai_text(
            user_id=user_id,
            user_text="",
            session=session,
            status_msg=status_msg,
            original_message=message,
            voice_bytes=voice_bytes,
        )

    except Exception as e:
        logger.error(f"Voice message error for user {user_id}: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ovozli xabarni tahlil qilishda xatolik yuz berdi: {str(e)}")


@router.message(F.photo | F.document | F.sticker | F.animation)
async def handle_media_message(message: Message, state: FSMContext):
    """Handler for photos, documents, stickers, and GIFs sent to the bot."""
    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    if await db.is_user_blocked(user_id):
        await message.answer("🚫 <b>Sizning hisobingiz admin tomonidan bloklangan.</b>", parse_mode=ParseMode.HTML)
        return

    session = await session_manager.get_session(user_id)
    if not session:
        await message.answer(
            "⚠️ Iltimos, avval hisobingizni (akkaunt) ulang.\n"
            "Buning uchun /connect buyrug'ini yuboring.",
            reply_markup=await main_menu_keyboard(is_connected=False),
        )
        return

    status_msg = await message.answer("📸 <b>Media fayl yuklanmoqda...</b>", parse_mode=ParseMode.HTML)
    user_last_msg_id[user_id] = status_msg.message_id

    try:
        os.makedirs("temp_media", exist_ok=True)
        file_path = ""
        
        if message.photo:
            photo = message.photo[-1]
            file_path = f"temp_media/photo_{user_id}_{message.message_id}.jpg"
            await message.bot.download(photo.file_id, destination=file_path)
        elif message.document:
            file_path = f"temp_media/doc_{user_id}_{message.message_id}_{message.document.file_name or 'file'}"
            await message.bot.download(message.document.file_id, destination=file_path)
        elif message.sticker:
            file_path = message.sticker.file_id
        elif message.animation:
            file_path = message.animation.file_id

        caption = message.caption.strip() if message.caption else ""
        
        if message.photo or message.document:
            media_prompt = f"[Foydalanuvchi media fayl yubordi. Fayl yo'li: {file_path}] {caption}".strip()
        elif message.sticker:
            media_prompt = f"[Foydalanuvchi sticker yubordi (file_id: {file_path})]. {caption}".strip()
        else:
            media_prompt = f"[Foydalanuvchi GIF yubordi (file_id: {file_path})]. {caption}".strip()

        await status_msg.edit_text("⚡️ <b>TaskGramAiBot faylni tahlil qilmoqda...</b>", parse_mode=ParseMode.HTML)
        await _process_ai_text(user_id, media_prompt, session, status_msg, message)

    except Exception as e:
        logger.error(f"Media message error for user {user_id}: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Media faylni yuklashda xatolik: {str(e)}")


# ── Bot Setup ─────────────────────────────────────────────────────────

async def set_bot_commands(bot: Bot):
    """Set bot commands in Telegram."""
    commands = [
        BotCommand(command="start", description="Dasturni ishga tushirish"),
        BotCommand(command="connect", description="Telegram hisobni ulash"),
        BotCommand(command="disconnect", description="Telegram hisobni uzish"),
        BotCommand(command="language", description="Muloqot tilini o'zgartirish"),
        BotCommand(command="status", description="Hisob holatini tekshirish"),
        BotCommand(command="autoreply", description="Lichkaga AI avto-javobni yoqish/o'chirish"),
        BotCommand(command="clear", description="Suhbat tarixini tozalash"),
        BotCommand(command="help", description="Yo'riqnoma va yordam"),
        BotCommand(command="cancel", description="Amaliyotni bekor qilish"),
    ]
    await bot.set_my_commands(commands)


admin_runner = None


async def on_startup(bot: Bot):
    """Startup tasks."""
    global admin_runner
    await db.connect()
    storage = init_channel_storage(bot)
    
    # 1. Restore database mapping state from channel pinned backup document
    try:
        await storage.restore_database_from_channel()
    except Exception as rest_err:
        logger.error(f"Restore from channel failed on startup: {rest_err}")
        
    # 2. Auto-load and reconnect all active user sessions to keep Telethon listeners alive
    asyncio.create_task(session_manager.load_all_active_sessions())
    
    await set_bot_commands(bot)
    
    # Start admin server
    try:
        from admin.server import start_admin_server
        port = int(os.getenv("PORT", 8000))
        admin_runner = await start_admin_server(bot=bot, port=port)
    except Exception as e:
        logger.error(f"❌ Failed to start admin server: {e}", exc_info=True)
        
    logger.info(f"✅ Bot started! Sessions stored in channel: {config.SESSION_CHANNEL_ID}")


async def on_shutdown(bot: Bot):
    """Shutdown tasks."""
    global admin_runner
    await session_manager.cleanup_all()
    await db.close()
    if admin_runner:
        try:
            await admin_runner.cleanup()
        except Exception:
            pass
    logger.info("🔴 Bot stopped.")


async def main():
    """Main entry point."""
    if not config.BOT_TOKEN or config.BOT_TOKEN == "your_bot_token_here":
        print("❌ BOT_TOKEN sozlanmagan! .env faylini tekshiring.")
        return

    if not config.API_ID or not config.API_HASH or config.API_HASH == "your_api_hash_here":
        print("❌ API_ID yoki API_HASH sozlanmagan! .env faylini tekshiring.")
        return

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("🚀 Bot ishga tushmoqda...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
