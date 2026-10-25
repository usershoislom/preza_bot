import logging
import os
import re

import httpx
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("preza")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
# Бэкенды по порядку: первый — Gemini, остальные — Groq. При ошибке/лимите берётся следующий.
PRESENTON_URLS = [u.strip().rstrip("/") for u in os.getenv("PRESENTON_URLS", "http://localhost:5001").split(",") if u.strip()]
DEFAULT_SLIDES = int(os.getenv("DEFAULT_SLIDES", "8"))
LANGUAGE = "Uzbek (Latin script, o'zbek tili lotin yozuvida)"
INSTRUCTIONS = (
    "Barcha matnni faqat o'zbek tilida, LOTIN yozuvida yozing (kirill emas). "
    "Taqdimot talabalar uchun: aniq, ilmiy, qisqa va tushunarli bo'lsin. "
    "Oxirgi slaydda xulosa va foydalanilgan manbalar bo'lsin."
)

START = (
    "Salom! Men talabalar uchun taqdimot (PPTX) tayyorlab beruvchi botman.\n\n"
    "Mavzuni yozing, masalan:\n"
    "  O'zbekiston tarixi\n"
    "Slaydlar sonini ham ko'rsatishingiz mumkin:\n"
    "  Sun'iy intellekt asoslari, 10 slayd\n\n"
    "Tayyorlash 1–3 daqiqa oladi."
)


def parse_request(text: str) -> tuple[str, int]:
    m = re.search(r"(\d{1,2})\s*(?:slayd|slide|ta slayd|bet)", text, re.I)
    n = DEFAULT_SLIDES
    if m:
        n = max(3, min(20, int(m.group(1))))
        text = (text[: m.start()] + text[m.end():]).strip(" ,.;-")
    return text, n


async def generate(base: str, prompt: str, n: int) -> bytes:
    async with httpx.AsyncClient(timeout=600) as client:
        r = await client.post(
            f"{base}/api/v1/ppt/presentation/generate",
            json={
                "content": prompt,
                "n_slides": n,
                "language": LANGUAGE,
                "instructions": INSTRUCTIONS,
                "template": "general",
                "export_as": "pptx",
            },
        )
        r.raise_for_status()
        path = r.json()["path"]
        url = path if path.startswith("http") else f"{base}/{path.lstrip('/')}"
        f = await client.get(url)
        f.raise_for_status()
        return f.content


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START)


async def make(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    prompt, n = parse_request(update.message.text.strip())
    if len(prompt) < 3:
        await update.message.reply_text("Iltimos, mavzuni batafsilroq yozing.")
        return
    status = await update.message.reply_text(f"⏳ Taqdimot tayyorlanmoqda ({n} slayd)... Biroz kuting.")
    await ctx.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_DOCUMENT)
    content = None
    for base in PRESENTON_URLS:
        try:
            content = await generate(base, prompt, n)
            break
        except Exception:
            log.exception("backend %s failed, trying next", base)
    if content is None:
        await status.edit_text("❌ Xatolik yuz berdi. Keyinroq qayta urinib ko'ring.")
        return
    try:
        name = re.sub(r"[^\w\-]+", "_", prompt)[:40].strip("_") or "taqdimot"
        await update.message.reply_document(content, filename=f"{name}.pptx", caption="✅ Taqdimotingiz tayyor!")
        await status.delete()
    except Exception:
        log.exception("generation failed")
        await status.edit_text("❌ Xatolik yuz berdi. Keyinroq qayta urinib ko'ring.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, make, block=False))
    app.run_polling()


if __name__ == "__main__":
    main()
