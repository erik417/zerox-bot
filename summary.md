## Goal
Telegram-бот (Bot.py) на python-telegram-bot + AI (NVIDIA/Cerebras/Groq): генерация кода через много-модельный итеративный цикл (Генератор↔Инспектор), чат-менеджер с ролями/правами, анализ и исправление кода; развёрнут на Hugging Face Spaces

## Constraints & Preferences
- HF Spaces (бесплатно) + Cloudflare Worker как прокси к Telegram API
- NVIDIA NIM (`meta/llama-3.3-70b-instruct`) — 40 RPM, без дневного лимита, PRIMARY
- Cerebras (`gpt-oss-120b`) — 1M TPD, fallback при 429 NVIDIA
- Groq — удалён (10 ключей с 1 аккаунта, все 429)
- Владелец: `OWNER_ID=6734685656`, `OWNER_USERNAME=Er1kos_designer`

## Provider Logic (ask_ollama)
1. NVIDIA → Cerebras → Groq (строгая последовательность)
2. `AI_TIMEOUT=30s` на весь запрос (было 600с)
3. Общий `httpx.AsyncClient` (lazy init) — без SSL handshake на каждый запрос
4. Логи времени ответа каждого провайдера

## Progress
### Done
- Все команды чат-менеджера: уровни 1-10, эмодзи, `/role`, `/strip`, `/resign`, `/call`, `/whoassigned`, `/permissions`, `/unwarn`
- Cloudflare Worker проксирует `api.telegram.org`
- Много-модельный итеративный цикл (Генератор↔Инспектор): `iterative_code_improvement()` — до 2 раундов
- **GENERATOR_PROMPT** + **INSPECTOR_PROMPT** — разные системные промпты
- **LessonManager** — сохраняет баги в `learned_lessons.json`
- **Cerebras reasoning fix**: парсинг `reasoning` поля вместо `content`
- **NVIDIA first**: быстрый безлимитный провайдер на первом месте
- **Dead Groq keys удалены** из HF Secrets
- **`/apikeys`** показывает Cerebras и NVIDIA даже без Groq
- **`AI_TIMEOUT` 600→30s**, общий http-клиент, логи таймингов

## Key Decisions
- **NVIDIA NIM как primary**: 40 RPM, без дневного лимита → решает проблему 429
- **Groq удалён**: 10 ключей одного аккаунта = один лимит 100k TPD, все 429
- **30s таймаут** вместо 600s — быстрый fallback при отказе провайдера
- **Один http-клиент** вместо создания на каждый запрос

## Known Issues
- Нет non-AI fallback когда все провайдеры 429 (TODO)
- Cerebras `gpt-oss-120b` — reasoning модель, иногда возвращает `reasoning` вместо `content`
- `context.user_data` не персистентно

## Relevant Files
- `C:\Users\erikh\Desktop\Новая папка\Bot.py` — основной код (~3083 строк)
- `_worker.js` — Cloudflare Worker
- `requirements.txt`, `Dockerfile`, `start.sh`
- `learned_lessons.json`, `chat_data.json`, `tokens.json` — persist-файлы
