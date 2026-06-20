import os
import json
import logging
from datetime import date
from typing import Optional

import httpx
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vk_bot")

TOKEN = os.environ.get("VK_TOKEN")
GROUP_ID = os.environ.get("VK_GROUP_ID")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
AI_TIMEOUT = int(os.environ.get("AI_TIMEOUT", "30"))
TOKENS_PER_DAY = int(os.environ.get("TOKENS_PER_DAY", "20"))
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
TOKENS_FILE = "vk_tokens.json"
KNOWN_USERS_FILE = "vk_known_users.json"
BANNED_USERS_FILE = "vk_banned_users.json"

SYSTEM_PROMPT = (
    "Ты — Zerox, русскоязычный AI-помощник в VK. "
    "Отвечай только по-русски, грамотно и без ошибок. "
    "Будь вежливым и полезным. Без мата и оскорблений."
)

class TokenManager:
    def __init__(self):
        self.data: dict = {}
        self._load()

    def _load(self):
        try:
            with open(TOKENS_FILE, encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception:
            self.data = {}

    def _save(self):
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def _today(self) -> str:
        return date.today().isoformat()

    def get_balance(self, user_id: int) -> int:
        uid = str(user_id)
        entry = self.data.get(uid)
        if not entry or entry.get("date") != self._today():
            return TOKENS_PER_DAY
        return entry.get("tokens", 0)

    def spend(self, user_id: int) -> bool:
        uid = str(user_id)
        today = self._today()
        entry = self.data.get(uid)
        if not entry or entry.get("date") != today:
            self.data[uid] = {"date": today, "tokens": TOKENS_PER_DAY - 1}
            self._save()
            return True
        if entry["tokens"] <= 0:
            return False
        entry["tokens"] -= 1
        self._save()
        return True

    def set_tokens(self, user_id: int, amount: int):
        uid = str(user_id)
        today = self._today()
        self.data[uid] = {"date": today, "tokens": amount}
        self._save()

TOKEN_MGR = TokenManager()

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

KNOWN_USERS: dict[str, int] = {}

def _save_known():
    try:
        with open(KNOWN_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(KNOWN_USERS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _load_known():
    global KNOWN_USERS
    try:
        with open(KNOWN_USERS_FILE, encoding="utf-8") as f:
            KNOWN_USERS = json.load(f)
    except Exception:
        KNOWN_USERS = {}

def track_user(user_id: int, username: str = ""):
    key = username.lower() if username else str(user_id)
    if KNOWN_USERS.get(key) != user_id:
        KNOWN_USERS[key] = user_id
        _save_known()

_load_known()

BANNED_USERS: set[int] = set()

def _save_banned():
    try:
        with open(BANNED_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(BANNED_USERS), f)
    except Exception:
        pass

def _load_banned():
    global BANNED_USERS
    try:
        with open(BANNED_USERS_FILE, encoding="utf-8") as f:
            BANNED_USERS = set(json.load(f))
    except Exception:
        BANNED_USERS = set()

def is_banned(user_id: int) -> bool:
    return user_id in BANNED_USERS

def ban_user(user_id: int):
    BANNED_USERS.add(user_id)
    _save_banned()

def unban_user(user_id: int):
    BANNED_USERS.discard(user_id)
    _save_banned()

_load_banned()

def ask_ollama(prompt: str, temperature: float = 0.5, max_tokens: int = 256) -> Optional[str]:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "stop": ["User:", "\n\n---"],
        },
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(AI_TIMEOUT)) as client:
            resp = client.post(OLLAMA_URL, json=payload)
        if resp.status_code != 200:
            return None
        data = resp.json()
        answer = data.get("response", "").strip()
        return answer or None
    except Exception:
        return None

def handle_message_text(vk, user_id, text):
    if not text:
        return
    if is_banned(user_id):
        return
    track_user(user_id, "")

    text_lower = text.lower().strip()

    if text_lower == "/start":
        msg = (
            f"Привет! Я Zerox — твой AI помощник.\n"
            f"У тебя {TOKENS_PER_DAY} вопросов в день.\n"
            f"Просто напиши что-нибудь!"
        )
        vk.messages.send(user_id=user_id, message=msg, random_id=0)
        return

    if text_lower == "/balance":
        bal = TOKEN_MGR.get_balance(user_id)
        msg = f"Твой баланс: {bal} / {TOKENS_PER_DAY} вопросов"
        vk.messages.send(user_id=user_id, message=msg, random_id=0)
        return

    if text_lower.startswith("/grant ") and is_owner(user_id):
        parts = text.split()
        if len(parts) >= 2:
            try:
                amount = int(parts[-1])
                target_id = int(parts[1]) if parts[1].lstrip("-").isdigit() else None
                if target_id:
                    TOKEN_MGR.set_tokens(target_id, amount)
                    vk.messages.send(user_id=user_id, message=f"Выдано {amount} токенов", random_id=0)
                else:
                    vk.messages.send(user_id=user_id, message="Укажи ID пользователя", random_id=0)
            except ValueError:
                vk.messages.send(user_id=user_id, message="Количество должно быть числом.", random_id=0)
        return

    if text_lower.startswith("/banuser ") and is_owner(user_id):
        parts = text.split()
        if len(parts) >= 2:
            try:
                target_id = int(parts[1])
                if target_id == OWNER_ID:
                    vk.messages.send(user_id=user_id, message="Нельзя забанить себя.", random_id=0)
                else:
                    ban_user(target_id)
                    vk.messages.send(user_id=user_id, message=f"Пользователь {target_id} забанен.", random_id=0)
            except ValueError:
                vk.messages.send(user_id=user_id, message="Укажи ID пользователя.", random_id=0)
        return

    if text_lower.startswith("/unbanuser ") and is_owner(user_id):
        parts = text.split()
        if len(parts) >= 2:
            try:
                target_id = int(parts[1])
                unban_user(target_id)
                vk.messages.send(user_id=user_id, message=f"Пользователь {target_id} разбанен.", random_id=0)
            except ValueError:
                vk.messages.send(user_id=user_id, message="Укажи ID пользователя.", random_id=0)
        return

    if text_lower == "/blacklist" and is_owner(user_id):
        if not BANNED_USERS:
            vk.messages.send(user_id=user_id, message="Чёрный список пуст.", random_id=0)
        else:
            names = [str(uid) for uid in sorted(BANNED_USERS)]
            msg = "Чёрный список:\n" + "\n".join(f"• {uid}" for uid in names)
            vk.messages.send(user_id=user_id, message=msg, random_id=0)
        return

    # Check tokens
    if not TOKEN_MGR.spend(user_id):
        vk.messages.send(
            user_id=user_id,
            message=f"У тебя закончились вопросы на сегодня. Лимит: {TOKENS_PER_DAY} в день.",
            random_id=0,
        )
        return

    # Send to AI
    prompt = f"{SYSTEM_PROMPT}\n\nUser: {text}\nAssistant:"
    answer = ask_ollama(prompt, temperature=0.3, max_tokens=256)

    if not answer:
        answer = "Не могу подключиться к модели. Попробуй ещё раз."

    vk.messages.send(user_id=user_id, message=answer, random_id=0)

def main():
    if not TOKEN or not GROUP_ID:
        logger.error("VK_TOKEN and VK_GROUP_ID must be set!")
        return

    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, int(GROUP_ID))

    logger.info("VK bot started")
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            msg = event.object.message
            user_id = msg.get("from_id")
            text = msg.get("text", "")
            if msg.get("out", 0) == 1:
                continue
            handle_message_text(vk, user_id, text)

if __name__ == "__main__":
    main()
