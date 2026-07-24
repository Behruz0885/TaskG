import json
import logging
import aiohttp
import os
import html
from config import config

logger = logging.getLogger(__name__)

from datetime import datetime


def get_current_time_str(language: str = "uz") -> str:
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    days_uz = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
    months_uz = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
    
    days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    months_ru = ["Января", "Февраля", "Марта", "Апреля", "Мая", "Июня", "Июля", "Августа", "Сентября", "Октября", "Ноября", "Декабря"]

    if language == "ru":
        day_name = days_ru[now.weekday()]
        month_name = months_ru[now.month - 1]
        return (
            f"📅 Текущая точная дата и время: {now_str} ({day_name}, {now.day} {month_name} {now.year} года).\n"
            f"Все вычисления по датам и времени (сегодня, вчера, в этом месяце, в этом году и т.д.) производи строго на основе этой даты!"
        )
    elif language == "en":
        day_name = now.strftime("%A")
        month_name = now.strftime("%B")
        return (
            f"📅 Current exact date and time: {now_str} ({day_name}, {month_name} {now.day}, {now.year}).\n"
            f"Perform all date and time calculations (today, yesterday, this month, this year, etc.) strictly based on this date!"
        )
    else:
        day_name = days_uz[now.weekday()]
        month_name = months_uz[now.month - 1]
        return (
            f"📅 Hozirgi aniq vaqt va sana: {now_str} (Hafta kuni: {day_name}, {now.day}-{month_name} {now.year}-yil).\n"
            f"Sana va vaqtga oid barcha hisob-kitoblarni (bugun, kecha, shu oy, shu yil, soat va h.k.) faqat va faqat ushbu hozirgi vaqtga asoslanib bajar!"
        )


def get_system_prompt(language: str = "uz") -> str:
    lang_instruction = "Har doim foydalanuvchiga o'zbek tilida javob ber."
    if language == "ru":
        lang_instruction = "Отвечай пользователю строго на русском языке. Никаких других языков!"
    elif language == "en":
        lang_instruction = "Respond to the user strictly in English. No other languages allowed!"

    time_info = get_current_time_str(language)

    return f"""Sen Telegram akkauntni boshqaruvchi va foydalanuvchining har qanday savollariga javob beruvchi aqlli AI assistantsan. Foydalanuvchi senga buyruq berishi (Telegram akkauntini boshqarish uchun) yoki shunchaki oddiy savollar so'rashi, suhbatlashishi mumkin.

{time_info}

Senda quyidagi funksiyalar mavjud (tools). Har bir buyruqni bajarish uchun tegishli funksiyani chaqir:

## Mavjud funksiyalar:

1. **send_message** - Xabar yuborish (reply_to parametriga message_id berilsa, o'sha xabarga javob (reply) qilib yuboradi)
   - Parametrlar: {{"chat_id": "username yoki ID", "text": "xabar matni", "reply_to": null}}

2. **get_messages** - Chatdan xabarlarni o'qish
   - Parametrlar: {{"chat_id": "username yoki ID", "limit": 20}}

3. **get_unread_messages** - O'qilmagan xabarlarni ko'rish
   - Parametrlar: {{"chat_id": "username yoki ID"}}

4. **forward_message** - Xabarni boshqa chatga forward qilish
   - Parametrlar: {{"from_chat": "manba chat", "to_chat": "manzil chat", "message_ids": [1, 2, 3]}}

5. **delete_messages** - Xabarlarni o'chirish
   - Parametrlar: {{"chat_id": "username yoki ID", "message_ids": [1, 2, 3]}}

6. **edit_message** - Xabarni tahrirlash
   - Parametrlar: {{"chat_id": "username yoki ID", "message_id": 123, "new_text": "yangi matn"}}

7. **pin_message** - Xabarni pin qilish
   - Parametrlar: {{"chat_id": "username yoki ID", "message_id": 123}}

8. **get_dialogs** - Chatlar ro'yxatini olish
   - Parametrlar: {{"limit": 30}}

9. **search_chats** - Chatlarni qidirish
   - Parametrlar: {{"query": "qidiruv so'zi"}}

10. **search_global** - Global qidirish (foydalanuvchilar, kanallar)
    - Parametrlar: {{"query": "qidiruv so'zi"}}

11. **join_chat** - Guruh yoki kanalga qo'shilish
    - Parametrlar: {{"link_or_username": "username yoki invite link"}}

12. **leave_chat** - Guruh yoki kanaldan chiqish
    - Parametrlar: {{"chat_id": "username yoki ID"}}

13. **get_chat_members** - Guruh a'zolarini ko'rish
    - Parametrlar: {{"chat_id": "username yoki ID", "limit": 50}}

14. **get_me** - O'z akkaunt ma'lumotlarini ko'rish
    - Parametrlar: {{}}

15. **get_user_info** - Foydalanuvchi haqida ma'lumot
    - Parametrlar: {{"user_id": "username yoki ID"}}

16. **mark_as_read** - Xabarlarni o'qilgan deb belgilash
    - Parametrlar: {{"chat_id": "username yoki ID"}}

17. **add_contact** - Kontakt qo'shish
    - Parametrlar: {{"phone": "+998...", "first_name": "Ism", "last_name": "Familiya"}}

18. **get_contacts** - Kontaktlar ro'yxati
    - Parametrlar: {{}}

19. **get_bot_token** - @BotFather dan bot API tokenini avtomatik olish
    - Parametrlar: {{"bot_username": "@bot_username"}}

20. **send_and_get_reply** - Chatga yoki botga xabar yuborib javobini olish
    - Parametrlar: {{"chat_id": "username yoki ID", "text": "xabar matni"}}

21. **get_my_bots** - Foydalanuvchi @BotFather orqali yaratgan barcha Telegram botlari ro'yxatini va sonini olish
    - Parametrlar: {{}}

22. **update_profile** - O'z Telegram profil ma'lumotlarini (ism, familiya, bio/about) o'zgartirish
    - Parametrlar: {{"first_name": "ism", "last_name": "familiya", "about": "bio text"}}

23. **update_profile_photo** - O'z Telegram profil rasmini o'zgartirish
    - Parametrlar: {{"file_path": "rasm fayl yo'li"}}

24. **create_group** - Yangi Telegram guruh ochish
    - Parametrlar: {{"title": "guruh nomi", "users": ["@user1", "@user2"]}}

25. **create_channel** - Yangi Telegram kanal yoki superguruh ochish
    - Parametrlar: {{"title": "kanal nomi", "about": "tavsif", "is_megagroup": false}}

26. **kick_chat_member** - Guruh yoki kanaldan a'zoni chiqarib tashlash
    - Parametrlar: {{"chat_id": "username yoki ID", "user_id": "username yoki ID"}}

27. **promote_admin** - Guruh yoki kanalda a'zoga adminlik huquqini berish
    - Parametrlar: {{"chat_id": "username yoki ID", "user_id": "username yoki ID", "custom_title": "Admin"}}

28. **send_reaction** - Xabarga emoji reaksiya qo'yish
    - Parametrlar: {{"chat_id": "username yoki ID", "message_id": 123, "emoji": "👍"}}

29. **create_poll** - Chatda so'rovnoma (Poll) yoki Test (Quiz) yaratish
    - Parametrlar: {{"chat_id": "username yoki ID", "question": "savol", "options": ["Variant 1", "Variant 2"], "is_quiz": false, "correct_option_id": 0}}

30. **update_chat_title** - Guruh yoki kanal nomini/sarlavhasini o'zgartirish
    - Parametrlar: {{"chat_id": "username yoki ID", "new_title": "Yangi nom"}}

31. **update_chat_about** - Guruh yoki kanal tavsifini (about/description) o'zgartirish
    - Parametrlar: {{"chat_id": "username yoki ID", "new_about": "Yangi tavsif"}}

32. **update_chat_photo** - Guruh yoki kanal profil rasmini o'zgartirish
    - Parametrlar: {{"chat_id": "username yoki ID", "file_path": "rasm fayl yo'li"}}

33. **send_sticker** - Chatga Stiker yuborish (sticker parametriga emoji, kalit so'z, file_id yoki fayl yo'li berilishi mumkin, masalan: "👍" yoki "happy")
    - Parametrlar: {{"chat_id": "username yoki ID", "sticker": "emoji yoki kalit so'z yoki file_path"}}

34. **send_gif** - Chatga GIF animatsiyasini yuborish (gif parametriga kalit so'z, file_id yoki fayl yo'li berilishi mumkin, masalan: "funny" yoki "dance")
    - Parametrlar: {{"chat_id": "username yoki ID", "gif": "kalit so'z yoki file_path"}}

35. **request_voice_call** - Foydalanuvchiga Telegram orqali 1-ga-1 Ovozli qo'ng'iroq qilish
    - Parametrlar: {{"user_id": "username yoki ID"}}

36. **create_group_call** - Guruh yoki kanalda Ovozli muloqot (Voice/Video Chat) boshlash
    - Parametrlar: {{"chat_id": "username yoki ID", "title": "Ovozli muloqot"}}

37. **send_file** - Chatga fayl/hujjat yoki rasm yuborish (file_path ga to'g'ridan-to'g'ri URL yoki lokal fayl yo'li beriladi)
    - Parametrlar: {{"chat_id": "username yoki ID", "file_path": "https://.../rasm.jpg yoki fayl yo'li", "caption": "izoh (ixtiyoriy)"}}

38. **unpin_message** - Pin qilingan xabarni yechish (message_id berilmasa, chatdagi barcha pinlar yechiladi)
    - Parametrlar: {{"chat_id": "username yoki ID", "message_id": 123}}

## Javob formati:

Har doim quyidagi JSON formatida javob ber:
```json
{{
    "thinking": "qisqa fikrlash",
    "actions": [
        {{
            "function": "funksiya_nomi",
            "params": {{"parametr": "qiymat"}},
            "description": "foydalanuvchiga ko'rsatiladigan tavsif"
        }}
    ],
    "message": "foydalanuvchiga javob xabari"
}}
```

## Dizayn va HTML Formatlash Qoidalari (JUDA MUHIM):
- Javoblarni judayam chiroyli, tushunarli va ko'zga yoqimli ko'rinishga keltirish uchun Telegram HTML teglari (<b>bold</b>, <i>italic</i>, <code>code</code>, <blockquote>quote</blockquote>) hamda mos emojilardan samarali foydalan:
  • Muhim nomlar, foydalanuvchi nomlari va kalit so'zlarni <b>Bold</b> (qalin) qilib yoz.
  • Natijalar, xulosalar, xabarlar yoki muhim iqtiboslarni <blockquote>Iqtibos bloki</blockquote> shaklida o'rab ber.
  • Username, phone, ID va kodlarni <code>code</code> shaklida ber.
- "shaxsiy", "shaxsiym", "lichka", "lichkam", "shaxsiy chatlar", "PM", "DM" atamalari ishlatilganda — bu "Saved Messages" emas, balki boshqa shaxslar bilan bo'lgan Shaxsiy Chatlar (Direct Messages / Private Chats) hisoblanadi! Shuning uchun 'shaxsiymga kimlar yozgan', 'lichkamdagi xabarlar' so'ralganda, get_dialogs (limit=20) funksiyasini chaqirib, shaxsiy foydalanuvchilar chatlarini (type='user') topib ber!
- Faqat va faqat foydalanuvchi "Saved Messages", "saqlangan xabarlar", "o'zimga yozganlarim" deb aniq aytgandagina chat_id="me" ishlatiladi!
- Agar foydalanuvchi "nima gap", "salom", "qanday gaplar" yoki shunga o'xshash oddiy salomlashish/savollar yuborsa, o'tgan buyruqlar tarixini hisobot qilib sanab bermasdan, oddiy do'stona suhbatdosh sifatida javob ber (masalan: "Hammasi joyida, o'zingizda nima gaplar? Sizga qanday yordam bera olaman?").
- OVOZLI JAVOB (JUDA MUHIM): Sen foydalanuvchiga ovozli (voice) xabar bilan javob bera OLASAN. Agar foydalanuvchi "ovoz bilan yubor", "ovozli xabar bilan gaplash", "gapirib ber", "ovozda javob ber", "menga gapir" kabi so'rasa — HECH QACHON "ovozli xabar yubora olmayman" deb rad etma va bu ishni request_voice_call bilan ham adashtirma. Bunday holatda shunchaki so'ralgan javobni oddiy tarzda faqat "message" maydonida yoz (actions bo'sh [] bo'lsin) — tizim javobingni avtomatik ravishda ovozli xabarga aylantirib yuboradi. Agar foydalanuvchi aniq savol bermay, faqat ovozda gaplashishni so'rasa, do'stona qisqa javob ber (salomlash va qanday yordam kerakligini so'ra).
- Agar foydalanuvchi 'men nechta bot yasaganman', 'botlarim ro'yxati', 'qanday botlarim bor' kabi so'rovlar bersa, har doim get_my_bots funksiyasini chaqir va botlar soni hamda ro'yxatini aniq ayt.
- Agar foydalanuvchi biror bot tokenini so'rasa (masalan: '@bot tokenini ber'), har doim get_bot_token funksiyasini chaqir va javobda faqat token va qisqa izoh ber.
- Agar foydalanuvchi hech qanday Telegram amali bajarishni so'ramagan bo'lsa (masalan: shunchaki oddiy savollar so'rasa, suhbatlashsa, salomlashsa va h.k.), actions massivini butunlay bo'sh [] qoldirib, javobingni faqat message maydonida yoz.
- Agar bir necha amal kerak bo'lsa, actions massiviga ketma-ket yoz
- Agar buyruq noaniq bo'lsa, message da so'ra (actions bo'sh bo'lsin)
- chat_id sifatida username (@username), telefon raqam yoki chat ID ishlatish mumkin
- {lang_instruction}
- Agar funksiya mavjud bo'lmasa, buni message orqali ayt
- "message" maydoni foydalanuvchiga ko'rsatiladigan matn, lekin actions bo'lsa, natija ham qo'shiladi

## Telegram bo'yicha bilim (buni yaxshi bilishing SHART, aks holda amallarni to'g'ri bajara olmaysan):
- chat_id sifatida quyidagilarni ishlatish mumkin: ochiq username (masalan @durov), telefon raqam (+998901234567), raqamli ID (masalan 123456789), yoki faqat o'ziga yozish uchun "me". "Saved Messages" ("saqlangan xabarlar") = "me".
- Chat turlari: shaxsiy suhbat (user), bot, oddiy guruh (group), superguruh (supergroup), kanal (channel). get_dialogs har bir chatning "type" maydonini qaytaradi — kerakli turdagi chatni shundan ajratib ol.
- ID'ni oldindan bilmasang, AVVAL topib ol, KEYIN amalni bajar. Odam yoki chatni topish uchun search_chats/search_global yoki get_dialogs; aniq bir xabarni (message_id) topish uchun get_messages. Bir so'rovda avval "olish", so'ng "bajarish" amallarini actions massiviga ketma-ket yoz.
- Xabarga javob (reply) berish: send_message'da reply_to=message_id ber. Xabarni boshqa chatga uzatish: forward_message.
- Quyidagi amallar uchun senda admin/tegishli huquq bo'lishi kerak; huquq bo'lmasa amal xato qaytaradi va buni foydalanuvchiga muloyim tushuntir: kick_chat_member, promote_admin, update_chat_title, update_chat_about, update_chat_photo, ba'zi guruh/kanallarda pin_message.
- send_file bilan rasm yoki fayl yuborayotganda file_path'ga to'g'ridan-to'g'ri URL berish mumkin (masalan rasm havolasi). Rasm/fayl uchun izoh kerak bo'lsa caption'dan foydalan. Stiker uchun send_sticker, GIF uchun send_gif.
- send_reaction uchun haqiqiy emoji ishlat: 👍 ❤️ 🔥 🎉 😁 😢 👏 kabi.
- Cheklovlar: bitta xabar 4096 belgigacha, media izohi (caption) 1024 belgigacha.
- Foydalanuvchi noaniq gapirsa (masalan "unga yoz", "o'sha xabarni o'chir", "u odamni chiqar") — kim yoki qaysi xabar/chat nazarda tutilganini aniqlashtir yoki avval get_dialogs/get_messages/search bilan topib ol, keyin amal qil.

## Namunalar (natural so'rov → to'g'ri actions):
- "Salimga 'salom' deb yoz" → [{{"function": "send_message", "params": {{"chat_id": "@salim", "text": "salom"}}}}]
- "Kanalimdagi oxirgi 5 ta xabarni o'chir" → avval get_messages bilan id'larni ol, keyin: [{{"function": "get_messages", "params": {{"chat_id": "@mychannel", "limit": 5}}}}, {{"function": "delete_messages", "params": {{"chat_id": "@mychannel", "message_ids": [101, 102, 103, 104, 105]}}}}]
- "@durov kanaliga qo'shil" → [{{"function": "join_chat", "params": {{"link_or_username": "@durov"}}}}]
- "Bu rasmni guruhga yubor: https://site.com/img.jpg" → [{{"function": "send_file", "params": {{"chat_id": "@mygroup", "file_path": "https://site.com/img.jpg", "caption": ""}}}}]
- "Oxirgi xabarimga 🔥 qo'y" → avval get_messages bilan oxirgi message_id ni ol, keyin send_reaction chaqir.
"""


def _build_api_url() -> str:
    """Build the correct API URL for AWS Bedrock Mantle."""
    base_url = getattr(config, "AI_BASE_URL", "").strip() or os.getenv("AI_BASE_URL", "")
    if not base_url or "amazonaws.com" in base_url:
        region = config.AWS_REGION
        base_url = f"https://bedrock-mantle.{region}.api.aws/v1"

    base_url = base_url.rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url
    return f"{base_url}/chat/completions"


async def ask_ai(user_message: str, chat_history: list[dict], language: str = "uz", model: str = None, voice_bytes: bytes = None) -> dict:
    """
    Send a message to the GLM-5 AI via AWS Bedrock Mantle / OpenAI-compatible endpoint.

    Uses Bearer token authentication (OpenAI SDK compatible format).

    Returns:
        dict with keys: thinking, actions (list), message
    """
    if not config.AWS_BEARER_TOKEN:
        return {
            "thinking": "",
            "actions": [],
            "message": "⚠️ AWS Bedrock API kaliti sozlanmagan. .env faylida AWS_BEARER_TOKEN_BEDROCK ni to'ldiring.",
        }

    if voice_bytes:
        # Some API gateways/providers don't allow a system prompt at index 0 when audio chunks are present.
        # We merge the system prompt instructions directly into the user message.
        messages = []
        messages.extend(chat_history[-20:])  # Last 20 messages for context

        import base64
        voice_b64 = base64.b64encode(voice_bytes).decode("utf-8")
        system_instructions = get_system_prompt(language)
        
        user_content = [
            {
                "type": "text",
                "text": f"{system_instructions}\n\nUshbu ovozli xabarda berilgan buyruqni tahlil qiling va tegishli funksiyalarni chaqiring."
            },
            {
                "type": "input_audio",
                "input_audio": {
                    "data": voice_b64,
                    "format": "wav"
                }
            }
        ]
        messages.append({"role": "user", "content": user_content})
    else:
        messages = [{"role": "system", "content": get_system_prompt(language)}]
        messages.extend(chat_history[-20:])  # Last 20 messages for context
        messages.append({"role": "user", "content": user_message})

    selected_model = model or config.AI_MODEL

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {config.AWS_BEARER_TOKEN}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": selected_model,
                "messages": messages,
                "max_tokens": config.AI_MAX_TOKENS,
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            }

            api_url = _build_api_url()
            logger.info(f"Calling AI API: {api_url} | Model: {selected_model}")

            async with session.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"GLM-5 API error {resp.status}: {error_text[:500]}")

                    # Handle common errors
                    if resp.status == 401:
                        return {
                            "thinking": "",
                            "actions": [],
                            "message": "❌ API autentifikatsiya xatoligi. Bearer token noto'g'ri yoki muddati o'tgan.",
                        }
                    elif resp.status == 429:
                        return {
                            "thinking": "",
                            "actions": [],
                            "message": "⏳ API cheklov (rate limit). Biroz kutib qayta urinib ko'ring.",
                        }
                    elif resp.status == 503:
                        return {
                            "thinking": "",
                            "actions": [],
                            "message": "🔧 AI xizmati vaqtincha ishlamayapti. Keyinroq urinib ko'ring.",
                        }

                    return {
                        "thinking": "",
                        "actions": [],
                        "message": f"❌ AI xatolik (HTTP {resp.status}): {error_text[:200]}",
                    }

                data = await resp.json()

                # Extract content from response
                content = ""
                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    if "message" in choice:
                        content = choice["message"].get("content", "")
                    elif "delta" in choice:
                        content = choice["delta"].get("content", "")

                if not content:
                    return {
                        "thinking": "",
                        "actions": [],
                        "message": "⚠️ AI bo'sh javob qaytardi.",
                    }

                try:
                    result = json.loads(content)
                    # Ensure required fields
                    result.setdefault("thinking", "")
                    result.setdefault("actions", [])
                    result.setdefault("message", "")
                    return result
                except json.JSONDecodeError:
                    # AI returned non-JSON response, wrap it
                    return {
                        "thinking": "",
                        "actions": [],
                        "message": content,
                    }

    except aiohttp.ClientConnectorError as e:
        logger.error(f"GLM-5 connection failed: {e}")
        return {
            "thinking": "",
            "actions": [],
            "message": (
                f"❌ <b>AI Serverga ulanib bo'lmadi!</b>\n\n"
                f"⚠️ DNS/Tarmoq xatoligi (getaddrinfo failed).\n"
                f"💡 <b>Sababi:</b> <code>bedrock-mantle.us-east-1.amazonaws.com</code> manzili topilmadi.\n"
                f"<code>.env</code> faylida to'g'ri <code>AI_BASE_URL</code> manzilini ko'rsating."
            ),
        }
    except aiohttp.ClientError as e:
        logger.error(f"GLM-5 request failed: {e}")
        return {
            "thinking": "",
            "actions": [],
            "message": f"❌ AI serverga ulanib bo'lmadi: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Unexpected GLM-5 error: {e}", exc_info=True)
        return {
            "thinking": "",
            "actions": [],
            "message": f"❌ Kutilmagan xatolik: {str(e)}",
        }


async def execute_actions(user_session, actions: list[dict]) -> list[dict]:
    """
    Execute a list of AI-generated actions using the user's Telethon session.

    Args:
        user_session: UserSession instance from session_manager
        actions: List of action dicts from AI response

    Returns:
        List of result dicts
    """
    results = []

    # Map function names to session methods
    function_map = {
        "send_message": user_session.send_message,
        "get_messages": user_session.get_messages,
        "get_unread_messages": user_session.get_unread_messages,
        "forward_message": user_session.forward_message,
        "delete_messages": user_session.delete_messages,
        "edit_message": user_session.edit_message,
        "pin_message": user_session.pin_message,
        "unpin_message": user_session.unpin_message,
        "get_dialogs": user_session.get_dialogs,
        "search_chats": user_session.search_chats,
        "search_global": user_session.search_global,
        "join_chat": user_session.join_chat,
        "leave_chat": user_session.leave_chat,
        "get_chat_members": user_session.get_chat_members,
        "get_me": user_session.get_me,
        "get_user_info": user_session.get_user_info,
        "mark_as_read": user_session.mark_as_read,
        "add_contact": user_session.add_contact,
        "get_contacts": user_session.get_contacts,
        "get_bot_token": user_session.get_bot_token,
        "send_and_get_reply": user_session.send_and_get_reply,
        "get_my_bots": user_session.get_my_bots,
        "update_profile": user_session.update_profile,
        "update_profile_photo": user_session.update_profile_photo,
        "create_group": user_session.create_group,
        "create_channel": user_session.create_channel,
        "kick_chat_member": user_session.kick_chat_member,
        "promote_admin": user_session.promote_admin,
        "send_reaction": user_session.send_reaction,
        "create_poll": user_session.create_poll,
        "update_chat_title": user_session.update_chat_title,
        "update_chat_about": user_session.update_chat_about,
        "update_chat_photo": user_session.update_chat_photo,
        "send_sticker": user_session.send_sticker,
        "send_gif": user_session.send_gif,
        "send_file": user_session.send_file,
        "request_voice_call": user_session.request_voice_call,
        "create_group_call": user_session.create_group_call,
    }

    for action in actions:
        func_name = action.get("function", "")
        params = action.get("params", {})
        description = action.get("description", func_name)

        if func_name not in function_map:
            results.append({
                "action": func_name,
                "description": description,
                "success": False,
                "error": f"Noma'lum funksiya: {func_name}",
            })
            continue

        try:
            func = function_map[func_name]
            result = await func(**params)
            results.append({
                "action": func_name,
                "description": description,
                "success": True,
                "result": result,
            })
        except Exception as e:
            logger.error(f"Action '{func_name}' failed: {e}")
            results.append({
                "action": func_name,
                "description": description,
                "success": False,
                "error": str(e),
            })

    return results


def format_results(ai_response: dict, action_results: list[dict]) -> str:
    """Format AI response and action results for sending to Telegram user with HTML tags."""
    parts = []

    # AI message
    if ai_response.get("message"):
        parts.append(ai_response["message"])

    # Action results
    if action_results:
        parts.append("")  # Empty line
        for r in action_results:
            status = "✅" if r["success"] else "❌"
            parts.append(f"<b>{status} {r['description']}</b>")

            if r["success"] and r.get("result"):
                result = r["result"]
                if isinstance(result, list):
                    # Format list results (messages, dialogs, etc.)
                    if len(result) > 0:
                        formatted = format_list_result(result, r["action"])
                        parts.append(f"<blockquote>{formatted}</blockquote>")
                    else:
                        parts.append("<blockquote>📭 Natija topilmadi</blockquote>")
                elif isinstance(result, dict):
                    if "text" in result:
                        parts.append(f"<blockquote>💬 {html.escape(result.get('text', ''))}</blockquote>")
            elif not r["success"]:
                parts.append(f"<blockquote>⚠️ {html.escape(r.get('error', 'Noma`lum xatolik'))}</blockquote>")

    return "\n".join(parts)


def format_list_result(items: list[dict], action: str) -> str:
    """Format a list of results based on the action type with HTML styling."""
    lines = []
    # How many items each branch actually renders. Defaults to "all" so that
    # branches without a cap (e.g. search results) never show a false remainder.
    display_limit = len(items)

    if action in ("get_messages", "get_unread_messages"):
        display_limit = 15
        for msg in items[:display_limit]:
            sender = html.escape(msg.get("sender", "???"))
            text = html.escape(msg.get("text", "")[:80])
            media = "📎" if msg.get("has_media") else ""
            lines.append(f"• <b>[{msg.get('id')}]</b> <b>{sender}</b>: <i>{text}</i> {media}")

    elif action == "get_dialogs":
        display_limit = 20
        for d in items[:display_limit]:
            type_emoji = {"user": "👤", "group": "👥", "supergroup": "👥", "channel": "📢"}.get(d.get("type"), "💬")
            unread = f" (<b>{d['unread_count']}🔴</b>)" if d.get("unread_count", 0) > 0 else ""
            name = html.escape(d.get("name", ""))
            lines.append(f"• {type_emoji} <b>{name}</b>{unread}")

    elif action in ("search_chats", "search_global"):
        for item in items:
            type_emoji = {"user": "👤", "group": "👥", "channel": "📢"}.get(item.get("type"), "💬")
            username = f" <code>@{html.escape(item['username'])}</code>" if item.get("username") else ""
            name = html.escape(item.get("name", ""))
            lines.append(f"• {type_emoji} <b>{name}</b>{username} (<code>ID: {item['id']}</code>)")

    elif action == "get_chat_members":
        display_limit = 20
        for m in items[:display_limit]:
            bot = " 🤖" if m.get("is_bot") else ""
            username = f" <code>@{html.escape(m['username'])}</code>" if m.get("username") else ""
            name = html.escape(m.get("name", ""))
            lines.append(f"• 👤 <b>{name}</b>{username}{bot}")

    elif action == "get_contacts":
        display_limit = 20
        for c in items[:display_limit]:
            username = f" <code>@{html.escape(c['username'])}</code>" if c.get("username") else ""
            phone = f" 📞<code>{html.escape(c['phone'])}</code>" if c.get("phone") else ""
            name = html.escape(c.get("name", ""))
            lines.append(f"• 👤 <b>{name}</b>{username}{phone}")

    else:
        display_limit = 10
        for item in items[:display_limit]:
            lines.append(f"• {html.escape(json.dumps(item, ensure_ascii=False)[:100])}")

    hidden = len(items) - display_limit
    if hidden > 0:
        lines.append(f"   ... va yana {hidden} ta")

    return "\n".join(lines)


async def polish_text(text: str, language: str = "uz") -> str:
    """
    Polishes transcribed voice text using GLM-5 to make it accurate and clear for bot consumption in the chosen language.
    """
    if not config.AWS_BEARER_TOKEN:
        return text

    lang_name = "o'zbek" if language == "uz" else "rus (Russian)" if language == "ru" else "ingliz (English)"

    system_prompt = (
        f"Sen foydalanuvchining Telegram botiga yo'llagan ovozli xabar transkripsiyasini (Speech-to-Text) "
        f"tahrirlovchi va silliqlovchi assistantsan. Foydalanuvchi gapirgan, "
        f"lekin transkripsiyada xatolar, chala so'zlar yoki fonetik noto'g'ri yozilgan iboralar bo'lishi mumkin. "
        f"Matnni {lang_name} tilida Telegram bot tushunadigan toza, aniq buyruq ko'rinishiga keltir.\n\n"
        f"Vazifang:\n"
        f"1. Matndagi grammatik, imlo xatolarini tuzat va to'liq {lang_name} tilida shakllantir.\n"
        f"2. Matnni ma'nosini o'zgartirmasdan, Telegram bot tushunadigan toza, aniq buyruq ko'rinishiga keltir.\n"
        f"3. Ortiqcha izoh, kirish gap yoki salomlashish qo'shma, faqat va faqat tuzatilgan buyruq matnini qaytar.\n\n"
        f"Masalan:\n"
        f"Kiritilgan matn: 'saven meseg ga salom deb yozvor'\n"
        f"Tuzatilgan matn: 'Saved Messages ga salom yoz'\n\n"
        f"Kiritilgan matn: 'guruhlarni ko'raylikchi'\n"
        f"Tuzatilgan matn: 'Guruhlar ro'yxatini ko'rsat'\n\n"
        f"Kiritilgan matn: 'sheyxga yoz do'stimizga'\n"
        f"Tuzatilgan matn: 'sheyx ga yoz'\n\n"
        f"Kiritilgan matn: 'akkauntni uzib tashla'\n"
        f"Tuzatilgan matn: 'Akkauntni uzish'"
    )

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {config.AWS_BEARER_TOKEN}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": config.AI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                "max_tokens": 1000,
                "temperature": 0.1,
            }

            api_url = _build_api_url()
            async with session.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        choice = data["choices"][0]
                        polished = choice["message"].get("content", "").strip()
                        if polished:
                            if (polished.startswith('"') and polished.endswith('"')) or (polished.startswith("'") and polished.endswith("'")):
                                polished = polished[1:-1].strip()
                            return polished
    except Exception as e:
        logger.error(f"Error polishing text: {e}")
    
    return text


async def synthesize_ai_response(
    user_text: str,
    ai_message: str,
    action_results: list[dict],
    chat_history: list[dict],
    language: str = "uz",
    model: str = None,
    voice_bytes: bytes = None,
) -> str | None:
    """
    Takes the action execution results (data fetched from Telegram, e.g. messages from @BotFather)
    and passes them back to GLM-5 AI to generate a clean, natural, synthesized response
    that directly answers the user's prompt without dumping raw log data.
    """
    if not config.AWS_BEARER_TOKEN:
        return None

    lang_name = "o'zbek" if language == "uz" else "rus (Russian)" if language == "ru" else "ingliz (English)"
    time_info = get_current_time_str(language)

    system_prompt = (
        f"Sen Telegram botiga ulangan va foydalanuvchiga yordam beruvchi TaskGramAiBot va o'ta aqlli sun'iy intellektsan.\n"
        f"{time_info}\n\n"
        f"Foydalanuvchi quyidagi savol/buyruqni berdi:\n"
        f"'{user_text}'\n\n"
        f"Sening so'roving bo'yicha Telegram akkauntdan quyidagi amallar bajarildi va ma'lumotlar olindi:\n"
        f"{json.dumps(action_results, ensure_ascii=False, indent=2)}\n\n"
        f"VAZIFANG (JUDA MUHIM):\n"
        f"1. Olingan ma'lumotlarni chuqur tahlil qil va foydalanuvchining '{user_text}' so'roviga to'g'ri, aniq hamda to'liq javob tayyorla.\n"
        f"2. Hech qanday xom loglar, ID raqamlar, keraksiz xabar kodlari yoki olingan matnlarni shunchaki nusxalab tashlama! Ma'lumotni hisoblab, umumlashtirib, chiroyli ro'yxat yoki xulosa shaklida javob ber.\n"
        f"3. Masalan: agar foydalanuvchi 'men nechta bot yasaganman' deb so'ragan bo'lsa va @BotFather bilan xabarlar olingan bo'lsa, xabarlardan bot nomlarini va miqdorini aniqlab: 'Siz @BotFather orqali X ta bot yaratgansiz: 1. @bot1, 2. @bot2...' deb javob ber.\n"
        f"4. Javobni {lang_name} tilida va Telegram HTML formatida (<b>bold</b>, <i>italic</i>, <code>code</code>, <blockquote>quote</blockquote> va emojilar) yoz.\n"
        f"5. Faqat va faqat tayyor HTML javob matnini qaytar, JSON format emas!"
    )

    selected_model = model or config.AI_MODEL

    try:
        if voice_bytes:
            import base64
            voice_b64 = base64.b64encode(voice_bytes).decode("utf-8")
            user_content = [
                {
                    "type": "text",
                    "text": f"{system_prompt}\n\nOlingan natijalar bo'yicha yakuniy javobni tayyorlang."
                },
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": voice_b64,
                        "format": "wav"
                    }
                }
            ]
            messages = [
                {"role": "user", "content": user_content}
            ]
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Foydalanuvchi so'rovi: {user_text}\nOlingan natijalar bo'yicha yakuniy javobni tayyorla."}
            ]

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {config.AWS_BEARER_TOKEN}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": selected_model,
                "messages": messages,
                "max_tokens": 1500,
                "temperature": 0.3,
            }

            api_url = _build_api_url()
            async with session.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=45),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        choice = data["choices"][0]
                        res = choice["message"].get("content", "").strip()
                        if res:
                            return res
    except Exception as e:
        logger.error(f"Error in synthesize_ai_response: {e}")

    return None

