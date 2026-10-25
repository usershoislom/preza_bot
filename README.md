# Preza bot

Telegram-бот: студент пишет тему → получает .pptx на узбекском (латиница).
Генерацию делает [Presenton](https://github.com/presenton/presenton) (REST API) c Gemini.

## Запуск (нужен Docker)
```
cp .env.example .env   # впишите TELEGRAM_BOT_TOKEN и GOOGLE_API_KEY
docker compose up -d --build
```
Пример сообщения боту: `Sun'iy intellekt asoslari, 10 slayd`

Ключи хранятся только в `.env` (в .gitignore).

## Автопереключение при лимитах
Бот держит список бэкендов (`PRESENTON_URLS`): Gemini → Groq (`GROQ_MODEL_1`) → Groq (`GROQ_MODEL_2`).
Если запрос упал (лимит 429, 5xx, таймаут), берётся следующий. Модели Groq подбираются командой
`curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models`.
