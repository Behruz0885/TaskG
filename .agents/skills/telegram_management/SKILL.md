---
name: telegram_management
description: Guidelines and instructions for managing Telegram accounts using Telethon, Speech-to-Text, and AI handlers.
---

# Telegram Management Skill

This skill contains detailed guidelines, best practices, and implementation instructions for managing Telegram accounts, bot API interactions, session storage, and Speech-to-Text processing.

## 1. Telegram Client Initialization & Security
- **Official Client Spoofing**: To prevent Telegram from flagging logins (avoiding `PhoneCodeExpiredError` or `PhoneCodeInvalidError`), always initialize the `TelegramClient` with official-looking device headers:
  - `device_model = "Desktop"`
  - `system_version = "Windows 11"`
  - `app_version = "4.16.8"`
- **Session Locking**: Ensure that session files are generated correctly, stored, and managed securely.

## 2. Session Storage in Telegram Channel
- **Buffered File Upload**: Do not send raw session strings as plain text messages in the storage channel. Upload them as document attachments with a `.session` extension (e.g. `user_{user_id}.session`).
- **File Retrieval**: To read the session, forward the document message within the channel, download the file bytes, read the content, and delete the temporary forwarded message immediately. This ensures clean session storage without risking API exposure.

## 3. Input Formatting & Verification Codes
- **Plain Verification Codes**: Allow users to enter verification codes easily. Standardize plain numeric strings by stripping spaces and non-digits.
- **Bypassing Telegram Restrictions**: Telegram sometimes invalidates codes sent in plain text to chat. Instruct users to send the verification code with spaces between digits (e.g., `5 4 3 2 1`). The bot must automatically strip whitespace on receipt.

## 4. Voice Message & Speech-to-Text (STT) Processing
- **STT Providers**: Support Groq Whisper, OpenAI Whisper, and Wit.ai API endpoints.
- **Dynamic Polishing**: Once STT transcribes the voice message, use an AI handler (`polish_text`) to correct typos, grammatical errors, and phonetic misspellings (e.g. "saven meseg" to "Saved Messages") in the selected language before passing the command to the main AI executor.
- **Fallback Mechanism**: Always include a free fallback (e.g. Google Speech recognition API) or handle cases where API keys are missing to guarantee voice functionality works out of the box.

## 5. Multi-Language Support & Hard-Locking
- **Language Selection**: Prompt the user to select their communication language (Uzbek, Russian, English) immediately after successful authentication.
- **System Prompt Hard-Locking**: Pass the chosen language code to the AI system prompt generator (`get_system_prompt(language)`). Strictly instruct the AI to respond *only* in that language to prevent it from switching languages during voice command execution.

## 6. HTML Entity Safety & Message Delivery
- **HTML Escaping**: When formatting query results (like chat lists, messages, or contact details) into Telegram HTML format, always escape user-generated strings using `html.escape()` to prevent syntax errors (e.g., unclosed `<` or `>` characters) from crashing the message delivery.
- **Robust Delivery Fallback**: Use a safe message sender wrapper. If sending a message with `parse_mode=ParseMode.HTML` fails, catch the error and retry sending it as plain text to guarantee the user receives the response.
